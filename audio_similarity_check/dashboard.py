#!/usr/bin/env python3
"""
Audio Similarity Dashboard — Flask web UI with detailed logging.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, Response, jsonify, render_template, request, send_file
from flask_cors import CORS

# --- Setup logging ---
logger = logging.getLogger("dashboard")

# Suppress verbose numba debug logging
logging.getLogger("numba").setLevel(logging.WARNING)
logging.getLogger("numba.core.ssa").setLevel(logging.WARNING)
logging.getLogger("numba.core.bytecode").setLevel(logging.WARNING)

# Import similarity engine
import sys
sys.path.insert(0, str(Path(__file__).parent))

from catalog_similarity import (
    analyze_files,
    load_config,
    NewTrackReport,
    ComparisonResult,
    ArrayOps,
    audio_files,
)

app = Flask(__name__)
CORS(app)

# ============================================================
# STATE MANAGEMENT
# ============================================================

class JobStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Job:
    def __init__(self, job_id: str, catalog_paths: List[str], new_track: Optional[str] = None, rebuild_all: bool = False):
        self.job_id = job_id
        self.catalog_paths = catalog_paths
        self.new_track = new_track
        self.rebuild_all = rebuild_all
        self.status = JobStatus.PENDING
        self.progress = 0
        self.message = "Ожидание запуска..."
        self.result: Optional[NewTrackReport] = None
        self.results: List[ComparisonResult] = []
        self.error: Optional[str] = None
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self._event_queue: queue.Queue = queue.Queue()

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "catalog_paths": self.catalog_paths,
            "new_track": self.new_track,
            "rebuild_all": self.rebuild_all,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "has_result": self.result is not None or len(self.results) > 0,
        }

jobs: Dict[str, Job] = {}
config = load_config()
ops = ArrayOps(use_gpu=config.get("use_gpu", False))

logger.info(f"Config loaded: {config}")

# ============================================================
# WORKER THREAD
# ============================================================

def run_job(job: Job) -> None:
    logger.info(f"[JOB {job.job_id}] Starting with paths: {job.catalog_paths}")
    job.status = JobStatus.RUNNING
    job.started_at = time.time()
    job.message = "Инициализация..."
    job._event_queue.put(("progress", job.to_dict()))

    def progress_cb(current, total, message, percent):
        job.progress = percent
        job.message = f"{message} [{current}/{total}]"
        job._event_queue.put(("progress", job.to_dict()))
        logger.debug(f"[JOB {job.job_id}] Progress: {percent}% - {message} [{current}/{total}]")

    try:
        # Collect all audio files from catalog paths
        all_files = []
        for path_str in job.catalog_paths:
            path = Path(path_str)
            logger.info(f"[JOB {job.job_id}] Scanning path: {path}")
            if path.exists():
                extensions = set(config["audio_extensions"])
                files = audio_files(path, extensions)
                logger.info(f"[JOB {job.job_id}] Path {path}: found {len(files)} files")
                for f in files:
                    job.message = f"Сканирование: {f.name}"
                    job._event_queue.put(("progress", job.to_dict()))
                    logger.debug(f"[JOB {job.job_id}] Found file: {f}")
                all_files.extend(files)
                job.message = f"Найдено файлов: {len(all_files)}"
                job._event_queue.put(("progress", job.to_dict()))
            else:
                logger.warning(f"[JOB {job.job_id}] Path does not exist: {path_str}")
                job.message = f"Путь не существует: {path_str}"
                job._event_queue.put(("progress", job.to_dict()))

        if not all_files:
            logger.warning(f"[JOB {job.job_id}] No audio files found in any path")
            job.status = JobStatus.FAILED
            job.error = "Не найдено аудиофайлов в указанных путях"
            job._event_queue.put(("progress", job.to_dict()))
            return

        logger.info(f"[JOB {job.job_id}] Total files to process: {len(all_files)}")

        # Use first file's parent as cache root
        cache_root = all_files[0].parent
        logger.info(f"[JOB {job.job_id}] Cache root: {cache_root}")

        job.message = "Запуск анализа..."
        job._event_queue.put(("progress", job.to_dict()))

        if job.new_track:
            logger.info(f"[JOB {job.job_id}] Mode: NEW TRACK -> {job.new_track}")
            result = analyze_files(
                files=all_files,
                new_track=Path(job.new_track),
                config=config,
                cache_root=cache_root,
                progress_callback=progress_cb,
            )
            job.result = result
            job.results = result.results
        elif job.rebuild_all:
            logger.info(f"[JOB {job.job_id}] Mode: REBUILD ALL")
            results = analyze_files(
                files=all_files,
                rebuild_all=True,
                config=config,
                cache_root=cache_root,
                progress_callback=progress_cb,
            )
            job.results = results
        else:
            logger.warning(f"[JOB {job.job_id}] Neither new_track nor rebuild_all")
            job.status = JobStatus.FAILED
            job.error = "Укажите --new трек или --rebuild-all"
            job._event_queue.put(("progress", job.to_dict()))
            return

        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.message = "Готово"
        job.finished_at = time.time()
        job._event_queue.put(("progress", job.to_dict()))
        job._event_queue.put(("complete", job.to_dict()))
        logger.info(f"[JOB {job.job_id}] Completed successfully in {time.time() - job.started_at:.1f}s")

    except Exception as e:
        logger.exception(f"[JOB {job.job_id}] FAILED: {e}")
        job.status = JobStatus.FAILED
        job.error = str(e)
        job.message = f"Ошибка: {e}"
        job.finished_at = time.time()
        job._event_queue.put(("progress", job.to_dict()))

# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def index():
    logger.debug("GET / - serving index.html")
    return render_template("index.html")


@app.route("/api/paths", methods=["GET"])
def get_paths():
    logger.debug("GET /api/paths")
    paths = []
    env_paths = os.getenv("CATALOG_PATHS", "")
    if env_paths:
        paths = [p.strip() for p in env_paths.split(";") if p.strip()]
    return jsonify({"paths": paths})


@app.route("/api/paths", methods=["POST"])
def save_paths():
    logger.info("POST /api/paths")
    data = request.get_json()
    paths = data.get("paths", [])
    valid_paths = []
    for p in paths:
        path = Path(p).resolve()
        if path.exists():
            valid_paths.append(str(path))
            logger.info(f"  Valid path: {path}")
        else:
            logger.warning(f"  Invalid path: {p}")
            return jsonify({"error": f"Путь не существует: {p}"}), 400

    env_path = Path("D:/GitHub/AIMusicMasteringFactory/.env")
    env_content = ""
    if env_path.exists():
        env_content = env_path.read_text(encoding="utf-8")

    lines = [l for l in env_content.splitlines() if not l.startswith("CATALOG_PATHS=")]
    lines.append(f"CATALOG_PATHS={';'.join(valid_paths)}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(f"Saved {len(valid_paths)} paths to .env")

    return jsonify({"paths": valid_paths})


@app.route("/api/jobs", methods=["POST"])
def create_job():
    logger.info("POST /api/jobs")
    try:
        data = request.get_json()
        logger.info(f"Job request: {data}")
        catalog_paths = data.get("catalog_paths", [])
        new_track = data.get("new_track")
        rebuild_all = data.get("rebuild_all", False)

        if not catalog_paths:
            logger.warning("No catalog paths provided")
            return jsonify({"error": "Укажите хотя бы один путь к каталогу"}), 400

        if not new_track and not rebuild_all:
            logger.warning("Neither new_track nor rebuild_all specified")
            return jsonify({"error": "Укажите новый трек (new_track) или включите rebuild_all"}), 400

        if new_track and not Path(new_track).exists():
            logger.warning(f"New track not found: {new_track}")
            return jsonify({"error": f"Файл не найден: {new_track}"}), 400

        job_id = str(uuid.uuid4())[:8]
        job = Job(job_id, catalog_paths, new_track, rebuild_all)
        jobs[job_id] = job

        thread = threading.Thread(target=run_job, args=(job,), daemon=True)
        thread.start()

        logger.info(f"Job {job_id} started")
        return jsonify({"job_id": job_id, "status": "started"})
    except Exception as e:
        logger.exception("Error in create_job")
        return jsonify({"error": f"Server error: {e}"}), 500


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job(job_id: str):
    logger.debug(f"GET /api/jobs/{job_id}")
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job.to_dict())


@app.route("/api/jobs/<job_id>/events")
def job_events(job_id: str):
    logger.debug(f"SSE /api/jobs/{job_id}/events")
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    def event_stream():
        yield f"data: {json.dumps(job.to_dict())}\n\n"
        while job.status in (JobStatus.PENDING, JobStatus.RUNNING):
            try:
                event_type, data = job._event_queue.get(timeout=1)
                yield f"data: {json.dumps(data)}\n\n"
                if event_type == "complete":
                    break
            except queue.Empty:
                yield f"data: {json.dumps(job.to_dict())}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/jobs/<job_id>/results", methods=["GET"])
def get_results(job_id: str):
    logger.debug(f"GET /api/jobs/{job_id}/results")
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.result:
        # Add exact duplicates as EXACT results for UI display
        exact_results = []
        for group in job.result.exact_duplicates:
            for i in range(1, len(group)):
                exact_results.append({
                    "track_a": group[0],
                    "track_b": group[i],
                    "fused_similarity": 1.0,
                    "chroma_similarity": 1.0,
                    "tempo_ratio": 1.0,
                    "segment_pair": (0, 0),
                    "classification": "EXACT",
                    "red_threshold": 0.0,
                    "yellow_threshold": 0.0,
                })
        all_results = [r.__dict__ for r in job.result.results] + exact_results

        return jsonify({
            "mode": "new_track",
            "new_track": job.result.new_track,
            "catalog_size": job.result.catalog_size,
            "baseline_pairs": job.result.baseline_pairs,
            "baseline_median": job.result.baseline_median,
            "thresholds": job.result.thresholds,
            "results": all_results,
            "exact_duplicates": job.result.exact_duplicates,
            "elapsed_seconds": job.result.elapsed_seconds,
        })
    elif job.results:
        return jsonify({
            "mode": "rebuild_all",
            "results": [r.__dict__ for r in job.results],
            "exact_duplicates": getattr(job, 'exact_duplicates', []),
        })
    else:
        return jsonify({"error": "Results not ready"}), 404


@app.route("/api/jobs/<job_id>/export", methods=["GET"])
def export_results(job_id: str):
    logger.info(f"Export CSV for job {job_id}")
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    import pandas as pd
    from io import StringIO, BytesIO

    if job.result:
        df = pd.DataFrame([r.__dict__ for r in job.result.results])
    elif job.results:
        df = pd.DataFrame([r.__dict__ for r in job.results])
    else:
        return jsonify({"error": "No results to export"}), 404

    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    csv_buffer.seek(0)

    return Response(
        BytesIO(csv_buffer.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=similarity_report_{job_id}.csv"}
    )


@app.route("/api/scan", methods=["POST"])
def scan_path():
    logger.info("POST /api/scan")
    data = request.get_json()
    path_str = data.get("path", "")
    path = Path(path_str)

    logger.info(f"Scanning path: {path}")
    if not path.exists():
        logger.warning(f"Path not found: {path}")
        return jsonify({"exists": False, "error": "Путь не существует"})

    extensions = set(config["audio_extensions"])
    files = audio_files(path, extensions)

    logger.info(f"Scan result: {len(files)} files, extensions: {{f.suffix.lower() for f in files}}")

    return jsonify({
        "exists": True,
        "path": str(path.resolve()),
        "file_count": len(files),
        "extensions": sorted(list({f.suffix.lower() for f in files})),
        "sample_files": [f.name for f in files[:10]],
    })


@app.route("/api/audio/<path:track_name>")
def serve_audio(track_name: str):
    """Serve audio file by track name (searches in all known catalog paths)."""
    logger.info(f"Audio request: {track_name}")
    # Search in all catalog paths from jobs
    for job in jobs.values():
        for path_str in job.catalog_paths:
            path = Path(path_str)
            if path.exists():
                for ext in config["audio_extensions"]:
                    candidate = path / track_name
                    if candidate.exists():
                        logger.debug(f"Serving audio: {candidate}")
                        return send_file(candidate, mimetype=f"audio/{candidate.suffix[1:]}")
                    # Try recursive search
                    for found in path.rglob(track_name):
                        if found.is_file() and found.suffix.lower() in config["audio_extensions"]:
                            logger.debug(f"Serving audio (recursive): {found}")
                            return send_file(found, mimetype=f"audio/{found.suffix[1:]}")
    logger.warning(f"Audio not found: {track_name}")
    return jsonify({"error": "Audio file not found"}), 404


@app.route("/api/folder/<path:track_name>")
def get_folder(track_name: str):
    """Return folder path for a track."""
    logger.info(f"Folder request: {track_name}")
    for job in jobs.values():
        for path_str in job.catalog_paths:
            path = Path(path_str)
            if path.exists():
                for ext in config["audio_extensions"]:
                    candidate = path / track_name
                    if candidate.exists():
                        logger.debug(f"Folder for {track_name}: {candidate.parent}")
                        return jsonify({"path": str(candidate.parent.resolve())})
                    for found in path.rglob(track_name):
                        if found.is_file() and found.suffix.lower() in config["audio_extensions"]:
                            logger.debug(f"Folder (recursive) for {track_name}: {found.parent}")
                            return jsonify({"path": str(found.parent.resolve())})
    logger.warning(f"Folder not found for: {track_name}")
    return jsonify({"error": "Track not found"}), 404


@app.route("/api/open-folder/<path:track_name>", methods=["POST"])
def open_folder(track_name: str):
    """Open folder in Windows Explorer (server-side)."""
    logger.info(f"Open folder request: {track_name}")
    for job in jobs.values():
        for path_str in job.catalog_paths:
            path = Path(path_str)
            if path.exists():
                for ext in config["audio_extensions"]:
                    candidate = path / track_name
                    if candidate.exists():
                        folder = candidate.parent.resolve()
                        logger.info(f"Opening folder in Explorer: {folder}")
                        try:
                            import subprocess
                            subprocess.Popen(['explorer', '/select,', str(candidate.resolve())])
                            return jsonify({"success": True, "path": str(folder)})
                        except Exception as e:
                            logger.error(f"Failed to open folder: {e}")
                            return jsonify({"success": False, "error": str(e)}), 500
                    for found in path.rglob(track_name):
                        if found.is_file() and found.suffix.lower() in config["audio_extensions"]:
                            folder = found.parent.resolve()
                            logger.info(f"Opening folder (recursive) in Explorer: {folder}")
                            try:
                                import subprocess
                                subprocess.Popen(['explorer', '/select,', str(found.resolve())])
                                return jsonify({"success": True, "path": str(folder)})
                            except Exception as e:
                                logger.error(f"Failed to open folder: {e}")
                                return jsonify({"success": False, "error": str(e)}), 500
    logger.warning(f"Folder not found for: {track_name}")
    return jsonify({"success": False, "error": "Track not found"}), 404


@app.route("/api/open-output", methods=["POST"])
def open_output_folder():
    """Open the output folder in Windows Explorer."""
    logger.info("Open output folder request")
    try:
        import subprocess
        output_dir = Path(config.get("output_dir", "D:/GitHub/AIMusicMasteringFactory/audio_similarity_check/output"))
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Opening output folder in Explorer: {output_dir}")
        subprocess.Popen(['explorer', str(output_dir)])
        return jsonify({"success": True, "path": str(output_dir)})
    except Exception as e:
        logger.error(f"Failed to open output folder: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True, use_reloader=False)