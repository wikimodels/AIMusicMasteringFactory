"""BPM Retimer web dashboard (house pattern: stdlib ThreadingHTTPServer + JSON API).

Serves web/index.html and exposes:
  GET  /api/state                  full snapshot (config, files, progress, errors)
  POST /api/config   {input, output, target_bpm, spread, formats, workers}
  POST /api/scan                   rescan input dir (recursive)
  POST /api/detect                 auto-detect BPM for files missing it
  POST /api/redetect {id}          re-detect one file
  POST /api/override {id, bpm}     manual source BPM for one file
  POST /api/start                  stretch+convert queue (parallel workers)
  POST /api/stop                   request cancel (checked between files)

Run:  poetry run python bmp-retimer/web/server.py   (from repo root)
Open: http://localhost:8003
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent          # bmp-retimer/web
BASE = HERE.parent                              # bmp-retimer
REPO_ROOT = BASE.parent                         # AIMusicMasteringFactory
for p in (str(BASE), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from retimer import (  # noqa: E402
    AUDIO_EXTS,
    FFMPEG_FMT,
    apply_freq_trim_wav,
    convert_wav,
    detect_bpm_file,
    final_bpm_for_track,
    output_name,
    output_name_rate,
    scan_inputs,
    stretch_backend,
    stretch_to_wav,
)

def _audio_duration(path: Path) -> float | None:
    try:
        from tinytag import TinyTag
        tag = TinyTag.get(str(path))
        if tag.duration:
            return round(float(tag.duration), 2)
    except Exception:
        pass
    # fallback via soundfile / librosa quickly
    try:
        import soundfile as sf
        info = sf.info(str(path))
        if info.samplerate and info.frames:
            return round(info.frames / float(info.samplerate), 2)
    except Exception:
        pass
    return None

def _fmt_duration(sec: float | None) -> str:
    if sec is None:
        return "—"
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m}:{s:02d}" if m else f"0:{s:02d}"

def _scan_outputs(output_dir: str | Path) -> list[Path]:
    root = Path(output_dir)
    if not root.is_dir():
        return []
    return sorted([p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTS])

NEW_DEFAULT_INPUT = Path.home() / "Downloads" / "AIMusicTools" / "BPM-Retimer" / "input"
NEW_DEFAULT_OUTPUT = Path.home() / "Downloads" / "AIMusicTools" / "BPM-Retimer" / "output"

PORT = 8003
CONFIG_FILE = BASE / "config.json"
ERROR_LOG = "retimer_errors.log"

DEFAULTS = {
    "input": str(NEW_DEFAULT_INPUT),
    "output": str(NEW_DEFAULT_OUTPUT),
    "target_bpm": 40.0,
    "spread": 1.0,
    "formats": ["wav", "mp3", "m4a", "ogg"],
    "workers": 4,
    "low_cut": 30.0,
    "high_cut": 3000.0,
}

STATUSES = ("queued", "detecting", "stretching", "saving", "done", "error")


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.config = self._load_config()
        self.files: list[dict] = []
        self.outputs: list[dict] = []
        self.running = False
        self.phase = "idle"          # idle | detect | process
        self.stop_requested = False
        self.errors: list[dict] = []  # {file, stage, error}
        self.backend = stretch_backend()
        self.rescan()

    # -- config ---------------------------------------------------------
    def _load_config(self) -> dict:
        cfg = dict(DEFAULTS)
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            for k in DEFAULTS:
                if k in data:
                    cfg[k] = data[k]
            # one-time migration from old repo-local defaults to Downloads
            old_in = str(BASE / "input")
            old_out = str(BASE / "output")
            migrated = False
            if cfg.get("input") == old_in:
                cfg["input"] = str(NEW_DEFAULT_INPUT); migrated = True
            if cfg.get("output") == old_out:
                cfg["output"] = str(NEW_DEFAULT_OUTPUT); migrated = True
            if migrated:
                try:
                    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass
        except (OSError, ValueError):
            pass
        # ensure default dirs exist
        for k in ("input", "output"):
            try:
                Path(cfg[k]).mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        cfg["formats"] = [f for f in cfg.get("formats", ["wav"]) if f in FFMPEG_FMT] or ["wav"]
        return cfg

    def save_config(self, patch: dict) -> dict:
        with self.lock:
            for k in ("input", "output"):
                if k in patch and str(patch[k]).strip():
                    Path(str(patch[k]).strip()).mkdir(parents=True, exist_ok=True)
                    self.config[k] = str(patch[k]).strip()
            if "target_bpm" in patch:
                self.config["target_bpm"] = max(1.0, float(patch["target_bpm"]))
            if "spread" in patch:
                self.config["spread"] = max(0.0, float(patch["spread"]))
            if "formats" in patch:
                fmts = [f for f in patch["formats"] if f in FFMPEG_FMT]
                self.config["formats"] = fmts or ["wav"]
            if "workers" in patch:
                self.config["workers"] = max(1, min(16, int(patch["workers"])))
            if "low_cut" in patch:
                self.config["low_cut"] = max(0.0, min(1000.0, float(patch["low_cut"])))
            if "high_cut" in patch:
                self.config["high_cut"] = max(0.0, min(22000.0, float(patch["high_cut"])))
            CONFIG_FILE.write_text(
                json.dumps(self.config, indent=2, ensure_ascii=False), encoding="utf-8")
            snapshot = dict(self.config)
        self.rescan()
        return snapshot

    # -- queue ----------------------------------------------------------
    def rescan(self):
        with self.lock:
            old = {f["id"]: f for f in self.files}
            cfg = dict(self.config)
        found = scan_inputs(cfg["input"])
        root = Path(cfg["input"])
        files = []
        for p in found:
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                rel = p.name
            prev = old.get(rel, {})
            dur = _audio_duration(p)
            # preserve BPM if already analyzed — so trim doesn't wipe it, but initial load has none
            has_prev = rel in old
            files.append({
                "id": rel,
                "rel": rel,
                "name": p.name,
                "size": p.stat().st_size,
                "status": prev.get("status", "queued") if has_prev and prev.get("status") != "detecting" else "queued",
                "source_bpm": prev.get("source_bpm") if has_prev else None,
                "manual": bool(prev.get("manual", False)) if has_prev else False,
                "final_bpm": prev.get("final_bpm") if has_prev else None,
                "progress": prev.get("progress", 0.0) if has_prev else 0.0,
                "error": None,
                "duration": dur,
                "duration_str": _fmt_duration(dur),
                "audio_url": f"/audio/input/{rel}",
            })
        with self.lock:
            # don't clobber a running job's live rows
            if not self.running:
                self.files = files
            else:
                by_id = {f["id"]: f for f in self.files}
                for f in files:
                    if f["id"] not in by_id:
                        self.files.append(f)
        self._rescan_outputs()

    def _rescan_outputs(self):
        cfg = dict(self.config)
        found = _scan_outputs(cfg["output"])
        root = Path(cfg["output"])
        outs = []
        for p in found:
            try:
                rel = p.relative_to(root).as_posix()
            except ValueError:
                rel = p.name
            dur = _audio_duration(p)
            # try parse BPM from filename like name_40bpm.wav
            m = re.search(r"_(\d+)bpm", p.stem, re.I)
            bpm = int(m.group(1)) if m else None
            # or rate suffix like name_1.5x.wav (no analysis)
            rm = re.search(r"_(\d+(?:\.\d+)?)x", p.stem, re.I)
            rate_tag = (rm.group(1) + "x") if rm and bpm is None else None
            outs.append({
                "rel": rel,
                "name": p.name,
                "size": p.stat().st_size,
                "bpm": bpm,
                "rate_tag": rate_tag,
                "duration": dur,
                "duration_str": _fmt_duration(dur),
                "audio_url": f"/audio/output/{rel}",
            })
        with self.lock:
            self.outputs = outs

    def snapshot(self) -> dict:
        # refresh outputs on each snapshot so cards are always fresh
        try:
            self._rescan_outputs()
        except Exception:
            pass
        with self.lock:
            files = [dict(f) for f in self.files]
            outs = [dict(o) for o in self.outputs]
            done = sum(1 for f in files if f["status"] == "done")
            analyzed = sum(1 for f in files if f.get("source_bpm") is not None)
            erro = sum(1 for f in files if f["status"] == "error")
            # progress: smooth for detect via file progress, else done/analyzed
            if self.phase == "detect":
                prog = (sum(f["progress"] for f in files) / len(files)) if files else 0.0
                # ensure at least analyzed/total visible
                if files and analyzed == len(files):
                    prog = 1.0
            elif self.phase == "process":
                prog = (done / len(files)) if files else 0.0
            else:
                if files and analyzed == len(files):
                    prog = 1.0
                elif files and analyzed>0:
                    prog = analyzed / len(files)
                else:
                    prog = (sum(f["progress"] for f in files) / len(files)) if files else 0.0
            return {
                "config": dict(self.config),
                "files": files,
                "outputs": outs,
                "running": self.running,
                "phase": self.phase,
                "total": len(files),
                "done": done,
                "analyzed": analyzed,
                "errors_count": erro,
                "progress": round(prog, 4),
                "backend": self.backend,
                "errors": list(self.errors)[-50:],
            }

    def _set(self, fid: str, **kw):
        with self.lock:
            for f in self.files:
                if f["id"] == fid:
                    f.update(kw)
                    break

    def _get(self, fid: str):
        with self.lock:
            for f in self.files:
                if f["id"] == fid:
                    return dict(f)
        return None

    def log_error(self, fid: str, stage: str, msg: str):
        entry = {"file": fid, "stage": stage, "error": msg}
        with self.lock:
            self.errors.append(entry)
        try:
            out = Path(self.config["output"])
            out.mkdir(parents=True, exist_ok=True)
            with open(out / ERROR_LOG, "a", encoding="utf-8") as fh:
                fh.write(f"[{stage}] {fid}: {msg}\n")
        except OSError:
            pass

    # -- jobs -----------------------------------------------------------
    def start_detect(self) -> dict:
        with self.lock:
            if self.running:
                return {"ok": False, "error": "job already running"}
            targets = [f["id"] for f in self.files if f["source_bpm"] is None]
            if not targets:
                return {"ok": True, "targets": 0}
            self.running = True
            self.phase = "detect"
            self.stop_requested = False
            workers = self.config["workers"]
        threading.Thread(target=self._run_detect, args=(targets, workers), daemon=True).start()
        return {"ok": True, "targets": len(targets)}

    def _run_detect(self, targets: list[str], workers: int):
        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for fid in targets:
                    if self.stop_requested:
                        break
                    pool.submit(self._detect_one, fid).result()
        finally:
            with self.lock:
                self.running = False
                self.phase = "idle"
                self.stop_requested = False

    def _detect_one(self, fid: str):
        row = self._get(fid)
        if not row:
            return
        src = Path(self.config["input"]) / row["rel"]
        self._set(fid, status="detecting", progress=0.5, error=None)
        try:
            bpm = detect_bpm_file(src)
            self._set(fid, status="queued", source_bpm=round(bpm, 2),
                      progress=1.0, manual=False)
        except Exception as exc:  # noqa: BLE001
            self._set(fid, status="error", progress=0.0, error=f"detect: {exc}")
            self.log_error(fid, "detect", str(exc))

    def clear_bpm(self):
        with self.lock:
            for f in self.files:
                f["source_bpm"] = None
                f["manual"] = False
                f["progress"] = 0.0
                if f["status"] not in ("error", "detecting"):
                    f["status"] = "queued"
                f["error"] = None
        return {"ok": True}

    def start_process(self) -> dict:
        with self.lock:
            if self.running:
                return {"ok": False, "error": "job already running"}
            if not self.files:
                return {"ok": False, "error": "queue is empty (check input dir)"}
            missing = [f["id"] for f in self.files if f["source_bpm"] is None]
            self.running = True
            self.phase = "process"
            self.stop_requested = False
            workers = self.config["workers"]
        for fid in missing:
            self._set(fid, status="error", error="no source BPM (run Detect or set manually)")
            self.log_error(fid, "queue", "no source BPM (run Detect or set manually)")
        threading.Thread(target=self._run_process, args=(workers,), daemon=True).start()
        return {"ok": True, "skipped": len(missing)}

    def _run_process(self, workers: int):
        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futs = []
                for f in list(self.files):
                    if self.stop_requested:
                        break
                    if f["status"] == "error" or f["source_bpm"] is None:
                        continue
                    futs.append(pool.submit(self._process_one, f["id"]))
                for fut in futs:
                    if self.stop_requested:
                        for x in futs:
                            x.cancel()
                        break
                    try:
                        fut.result()
                    except Exception:  # noqa: BLE001 — per-file errors already recorded
                        pass
        finally:
            with self.lock:
                self.running = False
                self.phase = "idle"
                self.stop_requested = False

    def _process_one(self, fid: str):
        row = self._get(fid)
        if not row or row["source_bpm"] is None:
            return
        cfg = dict(self.config)
        src = Path(cfg["input"]) / row["rel"]
        final = final_bpm_for_track(cfg["target_bpm"], cfg["spread"])
        self._process_one_custom(fid, row, src, final, high_cut=0)

    def _process_one_custom(self, fid: str, row: dict, src: Path,
                            rate: float, final_bpm: float | None,
                            low_cut: float = 0, high_cut: float = 0):
        """Per-card processing: rate-based stretch + optional freq trim.

        Source BPM is NOT required: without it we stretch purely by rate
        (ratio = 1/rate) and name the file <stem>_<rate>x.
        """
        cfg = dict(self.config)
        self._set(fid, status="stretching",
                  final_bpm=round(final_bpm, 2) if final_bpm else None,
                  progress=0.25)
        try:
            with tempfile.TemporaryDirectory() as td:
                stretched = Path(td) / "stretched.wav"
                # anchor BPMs only define the ratio; any pair with ratio 1/rate works
                stretch_to_wav(src, stretched, 100.0, 100.0 * rate)
                if (low_cut and low_cut > 0) or (high_cut and high_cut > 0):
                    apply_freq_trim_wav(stretched, low_cut or 0, high_cut or 0)
                self._set(fid, status="saving", progress=0.7)
                out_root = Path(cfg["output"])
                rel_parent = Path(row["rel"]).parent
                stem = Path(row["name"]).stem
                for fmt in cfg["formats"]:
                    if final_bpm:
                        out_path = out_root / rel_parent / output_name(stem, final_bpm, fmt)
                    else:
                        out_path = out_root / rel_parent / output_name_rate(stem, rate, fmt)
                    convert_wav(stretched, out_path, fmt)
            self._set(fid, status="done", progress=1.0, error=None)
        except Exception as exc:  # noqa: BLE001
            self._set(fid, status="error", progress=0.0, error=f"process: {exc}")
            self.log_error(fid, "process", f"{exc} (backend={self.backend})")

    def start_process_one(self, rel: str, rate: float,
                            low_cut: float = 0, high_cut: float = 0) -> dict:
        with self.lock:
            if self.running:
                return {"ok": False, "error": "job already running", "code": 409}
            row = next((f for f in self.files if f["id"] == rel), None)
            if not row:
                return {"ok": False, "error": "unknown file", "code": 404}
            try:
                rate = float(rate)
            except (TypeError, ValueError):
                return {"ok": False, "error": "bad rate", "code": 400}
            if not 0.25 <= rate <= 4:
                return {"ok": False, "error": "rate must be 0.25-4", "code": 400}
            try:
                high_cut = float(high_cut or 0)
            except (TypeError, ValueError):
                return {"ok": False, "error": "bad high_cut", "code": 400}
            if not 0 <= high_cut <= 22000:
                return {"ok": False, "error": "high_cut must be 0-22000", "code": 400}
            try:
                low_cut = float(low_cut or 0)
            except (TypeError, ValueError):
                return {"ok": False, "error": "bad low_cut", "code": 400}
            if not 0 <= low_cut <= 1000:
                return {"ok": False, "error": "low_cut must be 0-1000", "code": 400}
            src_bpm = row.get("source_bpm") or 0
            final = round(float(src_bpm) * rate, 2) if src_bpm else None
            src = Path(self.config["input"]) / row["rel"]
            snapshot_row = dict(row)
            self.running = True
            self.phase = "process"
            self.stop_requested = False
        threading.Thread(
            target=self._run_process_one,
            args=(rel, snapshot_row, src, rate, final, low_cut, high_cut),
            daemon=True,
        ).start()
        out = {"ok": True, "rate": rate}
        if final:
            out["final_bpm"] = final
        return out

    def _run_process_one(self, fid: str, row: dict, src: Path,
                         rate: float, final_bpm: float | None,
                         low_cut: float, high_cut: float):
        try:
            self._process_one_custom(fid, row, src, rate, final_bpm, low_cut, high_cut)
        finally:
            with self.lock:
                self.running = False
                self.phase = "idle"
                self.stop_requested = False


STORE = Store()


class Handler(BaseHTTPRequestHandler):
    server_version = "BpmRetimerWeb/1.0"

    def log_message(self, fmt, *args):
        pass

    # -- helpers ---------------------------------------------------------
    def _send_bytes(self, data: bytes, ctype: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, obj, status: int = 200):
        self._send_bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                         "application/json", status)

    def _read_json(self) -> dict:
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _send_static(self, name: str):
        p = HERE / name
        if not p.is_file():
            return self._send_bytes(b"not found", "text/plain", 404)
        self._send_bytes(
            p.read_bytes(),
            mimetypes.guess_type(name)[0] or "application/octet-stream")

    def _serve_audio(self, root: Path, rel: str):
        # security: block traversal
        safe_rel = rel.lstrip("/")
        p = (root / safe_rel)
        try:
            rp = p.resolve()
            rr = root.resolve()
            if not str(rp).startswith(str(rr)):
                return self._send_bytes(b"forbidden", "text/plain", 403)
            if not rp.is_file():
                return self._send_bytes(b"not found", "text/plain", 404)
            ctype = mimetypes.guess_type(str(rp))[0] or "application/octet-stream"
            # fix for common types
            if rp.suffix.lower() == ".m4a":
                ctype = "audio/mp4"
            size = rp.stat().st_size
            range_hdr = self.headers.get("Range")
            if range_hdr:
                m = re.match(r"bytes=(\d*)-(\d*)", range_hdr)
                if m:
                    s = m.group(1); e = m.group(2)
                    start = int(s) if s else 0
                    end = int(e) if e else size - 1
                    end = min(end, size - 1)
                    if start >= size:
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{size}")
                        self.end_headers()
                        return
                    length = end - start + 1
                    self.send_response(206)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(length))
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    with open(rp, "rb") as f:
                        f.seek(start)
                        shutil.copyfileobj(f, self.wfile)
                    return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            with open(rp, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
        except Exception as exc:  # noqa: BLE001
            self._send_bytes(f"error: {exc}".encode(), "text/plain", 500)

    def _open_folder(self, path: str | Path) -> dict:
        p = Path(path)
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        try:
            if os.name == "nt":
                os.startfile(str(p))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
            return {"ok": True, "path": str(p)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def _clear_folder(self, path: str | Path) -> dict:
        p = Path(path)
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        deleted = 0
        # delete all files recursively, keep the root folder itself
        for child in sorted(p.rglob("*"), reverse=True):
            try:
                if child.is_file() or child.is_symlink():
                    child.unlink()
                    deleted += 1
                elif child.is_dir():
                    try:
                        child.rmdir()
                    except OSError:
                        pass
            except OSError:
                pass
        # queue must reflect cleared input
        cfg_input = Path(STORE.config["input"])
        try:
            if p.resolve() == cfg_input.resolve():
                STORE.rescan()
        except OSError:
            STORE.rescan()
        return {"ok": True, "deleted": deleted, "path": str(p)}

    def _handle_trim(self, rel: str, root: Path) -> dict:
        # raw WAV bytes in request body, overwrite file
        rel = __import__("urllib.parse", fromlist=["unquote"]).unquote(rel)
        # block traversal
        safe_rel = rel.lstrip("/")
        p = (root / safe_rel)
        try:
            rp = p.resolve()
            rr = root.resolve()
            if not str(rp).startswith(str(rr)):
                return {"ok": False, "error": "forbidden"}
            if not rp.is_file():
                return {"ok": False, "error": "file not found"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        # save BPM to restore after rescan (so trim doesn't wipe it)
        saved_bpm = None
        saved_manual = False
        try:
            if Path(STORE.config["input"]).resolve() == root.resolve():
                for ff in STORE.files:
                    if ff.get("rel") == safe_rel:
                        saved_bpm = ff.get("source_bpm")
                        saved_manual = ff.get("manual", False)
                        break
        except Exception:
            pass
        try:
            data = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if not data:
                return {"ok": False, "error": "empty body"}
            if len(data) < 44 or data[0:4] != b"RIFF":
                pass
            with open(rp, "wb") as f:
                f.write(data)
            # refresh queues
            try:
                STORE.rescan()
            except Exception:
                pass
            try:
                STORE._rescan_outputs()
            except Exception:
                pass
            # restore BPM without re-analyzing
            if saved_bpm is not None:
                try:
                    with STORE.lock:
                        for ff in STORE.files:
                            if ff.get("rel") == safe_rel:
                                ff["source_bpm"] = saved_bpm
                                ff["manual"] = saved_manual
                                ff["progress"] = 1.0
                                ff["status"] = "queued"
                                break
                except Exception:
                    pass
            return {"ok": True, "filename": rp.name, "rel": safe_rel}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def _handle_rename(self, rel: str, new_name: str, root: Path) -> dict:
        rel = rel.lstrip("/")
        new_name = (new_name or "").strip()
        if not rel or not new_name:
            return {"ok": False, "error": "name required"}
        # take only basename, block traversal
        new_base = Path(new_name).name.strip()
        if not new_base:
            return {"ok": False, "error": "invalid name"}
        # keep extension if not provided
        old_path = root / rel
        try:
            rp = old_path.resolve()
            rr = root.resolve()
            if not str(rp).startswith(str(rr)):
                return {"ok": False, "error": "forbidden"}
            if not rp.is_file():
                return {"ok": False, "error": "file not found"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        # preserve extension if new name has none
        if "." not in new_base:
            new_base = new_base + rp.suffix
        # sanitize: replace path separators, control chars
        new_base = new_base.replace("/", "_").replace("\\", "_")
        if len(new_base) > 180:
            new_base = new_base[:180]
        new_path = rp.parent / new_base
        if new_path.exists():
            return {"ok": False, "error": "file already exists"}
        try:
            rp.rename(new_path)
            try:
                STORE.rescan()
            except Exception:
                pass
            try:
                STORE._rescan_outputs()
            except Exception:
                pass
            # compute new rel
            try:
                new_rel = new_path.relative_to(rr).as_posix()
            except ValueError:
                new_rel = new_base
            return {"ok": True, "old": rel, "new": new_rel, "filename": new_base}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def _handle_delete(self, rel: str, root: Path) -> dict:
        rel = rel.lstrip("/")
        if not rel:
            return {"ok": False, "error": "rel required"}
        p = root / rel
        try:
            rp = p.resolve()
            rr = root.resolve()
            if not str(rp).startswith(str(rr)):
                return {"ok": False, "error": "forbidden"}
            if not rp.is_file():
                return {"ok": False, "error": "file not found"}
            rp.unlink()
            # remove empty parent dirs (but keep root)
            try:
                parent = rp.parent
                while parent != rr and parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
            except OSError:
                pass
            try:
                STORE.rescan()
            except Exception:
                pass
            try:
                STORE._rescan_outputs()
            except Exception:
                pass
            return {"ok": True, "deleted": rel}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def _handle_upload(self, ctype: str) -> dict:
        """Parse multipart/form-data, save file parts to input dir. Returns {ok, saved:[], errors:[]}."""
        m = re.search(r"boundary=([^;]+)", ctype)
        if not m:
            return {"ok": False, "error": "missing multipart boundary"}
        boundary = m.group(1).strip().strip('"').encode()
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if not raw:
            return {"ok": False, "error": "empty upload"}
        dest = Path(STORE.config["input"])
        try:
            dest.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        saved: list[str] = []
        errors: list[str] = []
        for chunk in raw.split(b"--" + boundary):
            if not chunk or chunk in (b"\r\n", b"--\r\n", b"--"):
                continue
            head, sep, body = chunk.partition(b"\r\n\r\n")
            if sep != b"\r\n\r\n":
                continue
            body = body.rstrip(b"\r\n")
            disp = ""
            for line in head.split(b"\r\n"):
                if line.lower().startswith(b"content-disposition:"):
                    disp = line.decode("utf-8", "replace")
                    break
            name = None
            filename = None
            for token in disp.split(";"):
                token = token.strip()
                if token.startswith("filename="):
                    filename = token[len("filename="):].strip('"')
                elif token.startswith("name="):
                    name = token[len("name="):].strip('"')
            if filename is None:
                continue  # non-file field
            filename = filename.strip().strip('"').strip()
            if not filename:
                continue
            # security: keep only basename; block directory traversal
            filename = Path(filename).name
            if not filename:
                continue
            ext = Path(filename).suffix.lower()
            if ext and ext not in AUDIO_EXTS:
                errors.append(f"{filename}: unsupported extension {ext}")
                continue
            if not body:
                errors.append(f"{filename}: empty file")
                continue
            out = dest / filename
            # de-dupe: file (2).wav
            if out.exists():
                stem, suffix = out.stem, out.suffix
                i = 2
                while out.exists() and i < 1000:
                    out = dest / f"{stem} ({i}){suffix}"
                    i += 1
            try:
                out.write_bytes(body)
                saved.append(out.name)
            except OSError as exc:
                errors.append(f"{filename}: {exc}")
        STORE.rescan()
        if saved:
            return {"ok": True, "saved": saved, "errors": errors}
        return {"ok": False, "error": "; ".join(errors) or "no files saved"}

    # -- routes -----------------------------------------------------------
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            return self._send_static("index.html")
        if path.lstrip("/") in ("app.js", "style.css", "favicon.ico", "favicon.svg", "favicon.png"):
            return self._send_static(path.lstrip("/"))
        if path.startswith("/audio/input/"):
            rel = path[len("/audio/input/"):]
            rel = __import__("urllib.parse", fromlist=["unquote"]).unquote(rel)
            return self._serve_audio(Path(STORE.config["input"]), rel)
        if path.startswith("/audio/output/"):
            rel = path[len("/audio/output/"):]
            rel = __import__("urllib.parse", fromlist=["unquote"]).unquote(rel)
            return self._serve_audio(Path(STORE.config["output"]), rel)
        if path == "/api/state":
            return self._send_json({"ok": True, **STORE.snapshot()})
        return self._send_bytes(b"not found", "text/plain", 404)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        # raw trim endpoints — handle before JSON parsing
        if path.startswith("/api/trim/input/"):
            rel = path[len("/api/trim/input/"):]
            res = self._handle_trim(rel, Path(STORE.config["input"]))
            code = 200 if res.get("ok") else 400
            return self._send_json(res, code)
        if path.startswith("/api/trim/output/"):
            rel = path[len("/api/trim/output/"):]
            res = self._handle_trim(rel, Path(STORE.config["output"]))
            code = 200 if res.get("ok") else 400
            return self._send_json(res, code)
        # multipart endpoints (upload) — don't try to JSON-parse the body
        if path == "/api/upload":
            res = self._handle_upload(self.headers.get("Content-Type", ""))
            code = 200 if res.get("ok") else 400
            return self._send_json(res, code)
        try:
            body = self._read_json()
        except ValueError:
            return self._send_json({"ok": False, "error": "invalid JSON body"}, 400)
        if path == "/api/config":
            try:
                cfg = STORE.save_config(body)
                return self._send_json({"ok": True, "config": cfg})
            except (ValueError, OSError) as exc:
                return self._send_json({"ok": False, "error": str(exc)}, 400)
        if path == "/api/scan":
            STORE.rescan()
            return self._send_json({"ok": True, **STORE.snapshot()})
        if path == "/api/detect":
            return self._send_json(STORE.start_detect())
        if path == "/api/redetect":
            fid = body.get("id", "")
            row = STORE._get(fid)
            if not row:
                return self._send_json({"ok": False, "error": "unknown file id"}, 404)
            STORE._set(fid, source_bpm=None, manual=False, error=None)
            if STORE.running:
                return self._send_json({"ok": False, "error": "job running, try later"}, 409)
            STORE.running = True
            STORE.phase = "detect"
            threading.Thread(target=self._oneshot_detect, args=(fid,), daemon=True).start()
            return self._send_json({"ok": True})
        if path == "/api/override":
            fid, bpm = body.get("id", ""), body.get("bpm")
            try:
                bpm = float(bpm)
                assert bpm > 0
            except (TypeError, ValueError, AssertionError):
                return self._send_json({"ok": False, "error": "bpm must be > 0"}, 400)
            if not STORE._get(fid):
                return self._send_json({"ok": False, "error": "unknown file id"}, 404)
            STORE._set(fid, source_bpm=round(bpm, 2), manual=True, error=None,
                       status="queued", progress=0.15)
            return self._send_json({"ok": True})
        if path == "/api/start":
            return self._send_json(STORE.start_process())
        if path == "/api/stop":
            with STORE.lock:
                STORE.stop_requested = True
            return self._send_json({"ok": True})
        if path == "/api/open_input":
            return self._send_json(self._open_folder(STORE.config["input"]))
        if path == "/api/open_output":
            return self._send_json(self._open_folder(STORE.config["output"]))
        if path == "/api/clear_input":
            return self._send_json(self._clear_folder(STORE.config["input"]))
        if path == "/api/clear_output":
            return self._send_json(self._clear_folder(STORE.config["output"]))
        if path == "/api/clear_bpm":
            return self._send_json(STORE.clear_bpm())
        if path == "/api/rename":
            kind = (body.get("kind") or "").strip()
            rel = (body.get("rel") or body.get("id") or body.get("old") or "").strip()
            new_name = (body.get("newName") or body.get("new_name") or body.get("name") or "").strip()
            if kind not in ("input", "output"):
                return self._send_json({"ok": False, "error": "kind must be input or output"}, 400)
            root = Path(STORE.config["input"]) if kind == "input" else Path(STORE.config["output"])
            res = self._handle_rename(rel, new_name, root)
            code = 200 if res.get("ok") else 400
            return self._send_json(res, code)
        if path == "/api/delete":
            kind = (body.get("kind") or "").strip()
            rel = (body.get("rel") or body.get("id") or "").strip()
            if kind not in ("input", "output"):
                return self._send_json({"ok": False, "error": "kind must be input or output"}, 400)
            root = Path(STORE.config["input"]) if kind == "input" else Path(STORE.config["output"])
            res = self._handle_delete(rel, root)
            code = 200 if res.get("ok") else 400
            return self._send_json(res, code)
        if path == "/api/process_one":
            rel = (body.get("rel") or body.get("id") or "").strip()
            res = STORE.start_process_one(rel, body.get("rate", 1.0),
                                          body.get("low_cut", 0),
                                          body.get("high_cut", 0))
            code = res.pop("code", 200 if res.get("ok") else 400)
            return self._send_json(res, code)
        return self._send_bytes(b"not found", "text/plain", 404)

    @staticmethod
    def _oneshot_detect(fid: str):
        try:
            STORE._detect_one(fid)
        finally:
            with STORE.lock:
                STORE.running = False
                STORE.phase = "idle"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://localhost:{args.port}"
    print(f"[*] BPM Retimer web at {url}  (engine: {STORE.backend})")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
