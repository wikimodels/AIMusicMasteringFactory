#!/usr/bin/env python3
"""
CATALOG AUDIO SIMILARITY CHECKER v4 — detailed logging, progress callback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

try:
    import cupy as cp
    HAS_CUPY = True
except ImportError:
    cp = None
    HAS_CUPY = False

import librosa
import pandas as pd
from tqdm import tqdm

# ============================================================
# CONFIG
# ============================================================

DEFAULT_CONFIG = {
    "audio_extensions": [".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"],
    "sr": 22050,
    "segment_duration": 30,
    "n_segments": 5,
    "n_fft": 4096,
    "hop_length": 512,
    "n_mels": 128,
    "n_mfcc": 20,
    "top_k": 10,
    "cache_dirname": ".features_cache",
    "config_version": "4.0",
    "red_percentile": 99.0,
    "yellow_percentile": 95.0,
    "min_pairs_for_calibration": 30,
    "workers": 0,
    "use_gpu": False,
    "log_level": "INFO",
    "early_exit_threshold": 0.995,
    "no_cache": False,
}

CONFIG_PATHS = [
    Path("similarity_config.yaml"),
    Path("similarity_config.json"),
    Path.home() / ".config" / "audio_similarity" / "config.yaml",
    Path.home() / ".config" / "audio_similarity" / "config.json",
]


# ============================================================
# LOGGING SETUP
# ============================================================

def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%H:%M:%S",
    )
    warnings.filterwarnings("ignore", category=UserWarning, module="librosa")
    # Suppress verbose numba debug logging
    logging.getLogger("numba").setLevel(logging.WARNING)
    logging.getLogger("numba.core.ssa").setLevel(logging.WARNING)
    logging.getLogger("numba.core.bytecode").setLevel(logging.WARNING)


def load_config(cli_overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    for path in CONFIG_PATHS:
        if path.exists():
            try:
                if path.suffix == ".yaml":
                    import yaml
                    with open(path) as f:
                        file_config = yaml.safe_load(f) or {}
                else:
                    with open(path) as f:
                        file_config = json.load(f)
                config.update(file_config)
                logging.getLogger("config").info(f"Loaded config from {path}")
                break
            except Exception as e:
                logging.getLogger("config").warning(f"Failed to load config from {path}: {e}")

    if cli_overrides:
        config.update({k: v for k, v in cli_overrides.items() if v is not None})
    return config


def save_config_template(path: Path) -> None:
    import yaml
    with open(path, "w") as f:
        yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False)
    print(f"Config template saved to {path}")


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass(frozen=True)
class SegmentFeatures:
    fused: np.ndarray
    chroma_raw: np.ndarray
    tempo: float

    def __post_init__(self):
        assert self.fused.dtype == np.float32
        assert self.chroma_raw.dtype == np.float32
        assert self.fused.ndim == 1
        assert self.chroma_raw.ndim == 1
        assert self.chroma_raw.shape == (12,)


@dataclass(frozen=True)
class TrackFeatures:
    file_hash: str
    duration: float
    segments: Tuple[SegmentFeatures, ...]

    @property
    def n_segments(self) -> int:
        return len(self.segments)


@dataclass(frozen=True)
class ComparisonResult:
    track_a: str
    track_b: str
    fused_similarity: float
    chroma_similarity: float
    tempo_ratio: float
    segment_pair: Tuple[int, int]
    classification: str = ""
    red_threshold: float = 0.0
    yellow_threshold: float = 0.0


@dataclass(frozen=True)
class NewTrackReport:
    new_track: str
    catalog_size: int
    baseline_pairs: int
    baseline_median: Optional[float]
    thresholds: Dict[str, float]
    results: List[ComparisonResult]
    exact_duplicates: List[List[str]]
    elapsed_seconds: float


# ============================================================
# UTILS
# ============================================================

def file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def audio_files(folder: Path, extensions: set[str]) -> List[Path]:
    """Recursively find audio files, Unicode-safe on Windows."""
    import os
    result = []
    ext_set = {e.lower() for e in extensions}

    def scan_dir(path: Path):
        try:
            for name in os.listdir(path):
                try:
                    full = os.path.join(path, name)
                    if os.path.isfile(full):
                        if Path(name).suffix.lower() in ext_set:
                            result.append(Path(full))
                    elif os.path.isdir(full):
                        scan_dir(Path(full))
                except (OSError, UnicodeError):
                    continue
        except (OSError, UnicodeError):
            pass

    scan_dir(folder)
    return sorted(result)


def make_cache_key(config: Dict[str, Any], file_hash_str: str) -> str:
    relevant = {
        "config_version": config["config_version"],
        "sr": config["sr"],
        "segment_duration": config["segment_duration"],
        "n_segments": config["n_segments"],
        "n_fft": config["n_fft"],
        "hop_length": config["hop_length"],
        "n_mels": config["n_mels"],
        "n_mfcc": config["n_mfcc"],
    }
    config_hash = hashlib.md5(json.dumps(relevant, sort_keys=True).encode()).hexdigest()[:16]
    return f"{file_hash_str}_{config_hash}"


# ============================================================
# AUDIO LOADING / SEGMENTS
# ============================================================

def load_audio(path: Path, sr: int) -> np.ndarray:
    logger = logging.getLogger("audio")
    logger.debug(f"Loading audio: {path}")
    y, _ = librosa.load(str(path), sr=sr, mono=True)
    y = y - np.mean(y)
    peak = np.max(np.abs(y))
    if peak > 0:
        y = y / peak
    logger.debug(f"  Loaded: {len(y)/sr:.1f}s, peak={peak:.4f}")
    return y.astype(np.float32)


def get_segments(y: np.ndarray, sr: int, segment_duration: int, n_segments: int) -> List[np.ndarray]:
    segment_samples = int(segment_duration * sr)
    if len(y) <= segment_samples:
        return [y]
    max_start = len(y) - segment_samples
    positions = np.linspace(0, max_start, n_segments).astype(int)
    segments = []
    for pos in positions:
        segment = y[pos:pos + segment_samples]
        if len(segment) > sr * 5:
            segments.append(segment)
    return segments


# ============================================================
# ARRAY OPS (GPU/CPU)
# ============================================================

class ArrayOps:
    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu and HAS_CUPY
        self.xp = cp if self.use_gpu else np
        logging.getLogger("arrayops").info(f"ArrayOps: {'GPU (CuPy)' if self.use_gpu else 'CPU (NumPy)'}")

    def asarray(self, a, dtype=np.float32):
        arr = self.xp.asarray(a, dtype=dtype)
        if self.use_gpu and not isinstance(arr, cp.ndarray):
            arr = cp.asarray(arr)
        return arr

    def to_numpy(self, a) -> np.ndarray:
        if self.use_gpu and isinstance(a, cp.ndarray):
            return cp.asnumpy(a)
        return np.asarray(a)

    def normalize(self, v: np.ndarray) -> np.ndarray:
        v = self.asarray(v, dtype=np.float32)
        norm = self.xp.linalg.norm(v)
        if norm < 1e-10:
            return self.xp.zeros_like(v)
        return v / norm

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        a = self.normalize(a)
        b = self.normalize(b)
        return float(self.xp.dot(a, b))

    def dot(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(self.xp.dot(self.asarray(a), self.asarray(b)))

    def roll(self, a: np.ndarray, shift: int) -> np.ndarray:
        return self.xp.roll(self.asarray(a), shift)

    def percentile(self, a: np.ndarray, q: float) -> float:
        return float(self.xp.percentile(self.asarray(a), q))

    def median(self, a: np.ndarray) -> float:
        return float(self.xp.median(self.asarray(a)))

    def mean(self, a: np.ndarray) -> float:
        return float(self.xp.mean(self.asarray(a)))

    def std(self, a: np.ndarray) -> float:
        return float(self.xp.std(self.asarray(a)))

    def concatenate(self, arrays: List[np.ndarray]) -> np.ndarray:
        return self.xp.concatenate([self.asarray(a) for a in arrays])

    def zeros(self, shape: int, dtype=np.float32) -> np.ndarray:
        return self.xp.zeros(shape, dtype=dtype)


# ============================================================
# FEATURE EXTRACTION
# ============================================================

def extract_fused_vector(y: np.ndarray, sr: int, ops: ArrayOps, config: Dict[str, Any]) -> SegmentFeatures:
    n_fft = config["n_fft"]
    hop_length = config["hop_length"]
    n_mels = config["n_mels"]
    n_mfcc = config["n_mfcc"]

    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop_length))

    mel = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=n_fft, hop_length=hop_length, n_mels=n_mels)
    mel_db = librosa.power_to_db(mel, ref=np.max)
    mel_vec = ops.normalize(np.concatenate([mel_db.mean(axis=1), mel_db.std(axis=1)]))

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc, n_fft=n_fft, hop_length=hop_length)
    mfcc_vec = ops.normalize(np.concatenate([mfcc.mean(axis=1), mfcc.std(axis=1)]))

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)
    chroma_vec = ops.normalize(chroma.mean(axis=1))

    harmonic = librosa.effects.harmonic(y)
    tonnetz = librosa.feature.tonnetz(y=harmonic, sr=sr)
    tonnetz_vec = ops.normalize(tonnetz.mean(axis=1))

    centroid = librosa.feature.spectral_centroid(S=S, sr=sr)
    bandwidth = librosa.feature.spectral_bandwidth(S=S, sr=sr)
    rolloff = librosa.feature.spectral_rolloff(S=S, sr=sr)
    contrast = librosa.feature.spectral_contrast(S=S, sr=sr)
    spectral_vec = ops.normalize(ops.concatenate([
        [centroid.mean(), centroid.std()],
        [bandwidth.mean(), bandwidth.std()],
        [rolloff.mean(), rolloff.std()],
        contrast.mean(axis=1), contrast.std(axis=1),
    ]))

    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    tempo, _ = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, hop_length=hop_length)
    tempo = float(np.asarray(tempo).reshape(-1)[0])
    rhythm_vec = ops.normalize(onset_env[:min(len(onset_env), 1000)])
    rhythm_fixed = ops.zeros(1000)
    rhythm_fixed[:len(rhythm_vec)] = rhythm_vec

    fused = ops.concatenate([mel_vec, mfcc_vec, chroma_vec, tonnetz_vec, spectral_vec, rhythm_fixed])
    fused = ops.normalize(fused).astype(np.float32)

    return SegmentFeatures(
        fused=fused,
        chroma_raw=ops.normalize(chroma.mean(axis=1)).astype(np.float32),
        tempo=tempo,
    )


def extract_track_features(y: np.ndarray, sr: int, config: Dict[str, Any], ops: ArrayOps) -> List[SegmentFeatures]:
    segments = get_segments(y, sr, config["segment_duration"], config["n_segments"])
    return [extract_fused_vector(seg, sr, ops, config) for seg in segments]


# ============================================================
# CACHING
# ============================================================

def cache_path(catalog_root: Path, cache_dirname: str, cache_key: str) -> Path:
    cache_dir = catalog_root / cache_dirname
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / f"{cache_key}.npz"


def save_features_cache(path: Path, track_features: TrackFeatures) -> None:
    n_seg = track_features.n_segments
    fused_array = np.stack([s.fused for s in track_features.segments])
    chroma_array = np.stack([s.chroma_raw for s in track_features.segments])
    tempo_array = np.array([s.tempo for s in track_features.segments], dtype=np.float32)

    np.savez_compressed(
        path,
        fused=fused_array,
        chroma=chroma_array,
        tempo=tempo_array,
        duration=np.float32(track_features.duration),
        file_hash=track_features.file_hash,
    )


def load_features_cache(path: Path) -> Optional[TrackFeatures]:
    try:
        data = np.load(path, allow_pickle=False)
        fused = data["fused"]
        chroma = data["chroma"]
        tempo = data["tempo"]
        duration = float(data["duration"])
        file_hash_str = str(data["file_hash"])

        segments = tuple(
            SegmentFeatures(
                fused=fused[i].astype(np.float32),
                chroma_raw=chroma[i].astype(np.float32),
                tempo=float(tempo[i]),
            )
            for i in range(len(fused))
        )
        return TrackFeatures(file_hash=file_hash_str, duration=duration, segments=segments)
    except Exception as e:
        logging.getLogger("cache").debug(f"Cache miss {path}: {e}")
        return None


def load_or_compute_features(
    audio_path: Path,
    catalog_root: Path,
    config: Dict[str, Any],
    ops: ArrayOps,
) -> TrackFeatures:
    logger = logging.getLogger("features")
    use_cache = not config.get("no_cache", False)
    h = file_hash(audio_path)

    cpath = None
    if use_cache:
        cache_key = make_cache_key(config, h)
        # cache_path() creates the ".features_cache" dir as a side effect,
        # so only call it when caching is actually enabled -- otherwise
        # --no-cache would still leave an empty folder behind.
        cpath = cache_path(catalog_root, config["cache_dirname"], cache_key)
        cached = load_features_cache(cpath)
        if cached is not None:
            logger.debug(f"Cache HIT: {audio_path.name}")
            return cached

    logger.info(f"Computing features: {audio_path.name}")
    y = load_audio(audio_path, config["sr"])
    seg_features = extract_track_features(y, config["sr"], config, ops)
    duration = len(y) / config["sr"]

    track_features = TrackFeatures(file_hash=h, duration=duration, segments=tuple(seg_features))

    if use_cache:
        save_features_cache(cpath, track_features)
        logger.debug(f"Cache SAVED: {cpath}")

    return track_features


# ============================================================
# SIMILARITY
# ============================================================

def chroma_similarity(chroma_a: np.ndarray, chroma_b: np.ndarray, ops: ArrayOps) -> float:
    a = ops.normalize(chroma_a)
    b = ops.normalize(chroma_b)
    best = 0.0
    for shift in range(12):
        sim = ops.dot(a, ops.roll(b, shift))
        if sim > best:
            best = sim
    return best


def compare_tracks_fast(
    track_a: TrackFeatures,
    track_b: TrackFeatures,
    ops: ArrayOps,
    early_exit: float = 0.995,
) -> Tuple[float, float, float, Tuple[int, int]]:
    logger = logging.getLogger("compare")
    best_fused = 0.0
    best_chroma = 0.0
    best_tempo_ratio = 0.0
    best_pair = (0, 0)

    for i, sa in enumerate(track_a.segments):
        for j, sb in enumerate(track_b.segments):
            fused_sim = ops.cosine_similarity(sa.fused, sb.fused)

            logger.debug(f"segment pair ({i},{j}) fused_sim={fused_sim:.4f}")

            if fused_sim > best_fused:
                best_fused = fused_sim
                best_pair = (i, j)
                if best_fused >= early_exit:
                    best_chroma = chroma_similarity(sa.chroma_raw, sb.chroma_raw, ops)
                    ta, tb = sa.tempo, sb.tempo
                    if ta > 0 and tb > 0:
                        r1 = min(ta, tb) / max(ta, tb)
                        r2 = min(ta, tb * 2) / max(ta, tb * 2)
                        r3 = min(ta, tb / 2) / max(ta, tb / 2)
                        best_tempo_ratio = max(r1, r2, r3)
                    return best_fused, best_chroma, best_tempo_ratio, best_pair

            chroma_sim = chroma_similarity(sa.chroma_raw, sb.chroma_raw, ops)
            if chroma_sim > best_chroma:
                best_chroma = max(best_chroma, chroma_sim)

            ta, tb = sa.tempo, sb.tempo
            if ta > 0 and tb > 0:
                r1 = min(ta, tb) / max(ta, tb)
                r2 = min(ta, tb * 2) / max(ta, tb * 2)
                r3 = min(ta, tb / 2) / max(ta, tb / 2)
                best_tempo_ratio = max(best_tempo_ratio, r1, r2, r3)

    return best_fused, best_chroma, best_tempo_ratio, best_pair


# ============================================================
# PARALLEL BASELINE
# ============================================================

def _compare_pair_worker(args: Tuple[TrackFeatures, TrackFeatures, str, str, Dict[str, Any], float]) -> Tuple[str, str, float, float, float, Tuple[int, int]]:
    track_a, track_b, name_a, name_b, config_dict, early_exit = args
    ops = ArrayOps(use_gpu=config_dict.get("use_gpu", False))
    fused, chroma, tempo_ratio, pair = compare_tracks_fast(track_a, track_b, ops, early_exit)
    return name_a, name_b, fused, chroma, tempo_ratio, pair


def build_baseline_parallel(
    all_tracks: Dict[str, TrackFeatures],
    config: Dict[str, Any],
    ops: ArrayOps,
) -> Tuple[np.ndarray, List[ComparisonResult]]:
    logger = logging.getLogger("baseline")
    names = list(all_tracks.keys())
    n = len(names)
    if n < 2:
        return np.array([]), []

    work_items = []
    for i in range(n):
        for j in range(i + 1, n):
            work_items.append((
                all_tracks[names[i]],
                all_tracks[names[j]],
                names[i],
                names[j],
                config,
                config.get("early_exit_threshold", 0.995),
            ))

    logger.info(f"Computing baseline: {len(work_items)} pairs with {config.get('workers', 0) or 'auto'} workers")
    scores = []
    results = []
    workers = config.get("workers", 0) or None

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_compare_pair_worker, item): item for item in work_items}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Baseline pairs", unit="pair"):
            name_a, name_b, fused, chroma, tempo_ratio, pair = future.result()
            scores.append(fused)
            results.append(ComparisonResult(
                track_a=name_a, track_b=name_b,
                fused_similarity=fused, chroma_similarity=chroma,
                tempo_ratio=tempo_ratio, segment_pair=pair,
            ))

    logger.info(f"Baseline done: {len(scores)} pairs, median={np.median(scores):.3f}" if scores else "Baseline empty")
    return np.array(scores, dtype=np.float32), results


def build_baseline_serial(
    all_tracks: Dict[str, TrackFeatures],
    config: Dict[str, Any],
    ops: ArrayOps,
) -> Tuple[np.ndarray, List[ComparisonResult]]:
    logger = logging.getLogger("baseline")
    names = list(all_tracks.keys())
    scores = []
    results = []
    for i in tqdm(range(len(names)), desc="Baseline pairs", unit="track"):
        for j in range(i + 1, len(names)):
            fused, chroma, tempo_ratio, pair = compare_tracks_fast(
                all_tracks[names[i]], all_tracks[names[j]], ops,
                config.get("early_exit_threshold", 0.995)
            )
            scores.append(fused)
            results.append(ComparisonResult(
                track_a=names[i], track_b=names[j],
                fused_similarity=fused, chroma_similarity=chroma,
                tempo_ratio=tempo_ratio, segment_pair=pair,
            ))
    return np.array(scores, dtype=np.float32), results


# ============================================================
# CLASSIFICATION
# ============================================================

def find_exact_duplicates(files: List[Path]) -> List[List[str]]:
    hashes: Dict[str, List[str]] = {}
    for path in files:
        try:
            h = file_hash(path)
            hashes.setdefault(h, []).append(path.name)
        except Exception as e:
            logging.getLogger("dupes").warning(f"Hash failed for {path.name}: {e}")
    return [names for names in hashes.values() if len(names) > 1]


def classify_score(score: float, baseline: np.ndarray, config: Dict[str, Any]) -> Tuple[str, float, float]:
    if len(baseline) >= config["min_pairs_for_calibration"]:
        red_thr = np.percentile(baseline, config["red_percentile"])
        yellow_thr = np.percentile(baseline, config["yellow_percentile"])
    else:
        mean = baseline.mean() if len(baseline) > 1 else 0.5
        std = baseline.std() if len(baseline) > 1 else 0.15
        red_thr = mean + 3 * std
        yellow_thr = mean + 2 * std

    if score >= red_thr:
        return "RED", float(red_thr), float(yellow_thr)
    if score >= yellow_thr:
        return "YELLOW", float(red_thr), float(yellow_thr)
    return "GREEN", float(red_thr), float(yellow_thr)


# ============================================================
# MAIN ANALYSIS (with progress callback)
# ============================================================

def analyze_files(
    files: List[Path],
    new_track: Optional[Path] = None,
    rebuild_all: bool = False,
    config: Optional[Dict[str, Any]] = None,
    cache_root: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    progress_callback: Optional[callable] = None,
) -> Union[NewTrackReport, List[ComparisonResult]]:
    logger = logging.getLogger("analyze")
    logger.info(f"analyze_files: {len(files)} files, new_track={new_track}, rebuild_all={rebuild_all}")

    if config is None:
        config = load_config()

    ops = ArrayOps(use_gpu=config.get("use_gpu", False))
    start_time = time.time()

    if new_track:
        new_path = new_track.resolve()
        files = [f for f in files if f.resolve() != new_path]

    if not files:
        logger.warning("File list is empty.")
        if new_track:
            return NewTrackReport(
                new_track=str(new_track), catalog_size=0, baseline_pairs=0,
                baseline_median=None, thresholds={"red": 0, "yellow": 0},
                results=[], exact_duplicates=[], elapsed_seconds=0
            )
        return []

    logger.info(f"Catalog: {len(files)} files from multiple paths")

    # Determine cache root: explicit argument > config > first file's parent.
    #
    # FIX: `analyze_catalog` now always passes an explicit cache_root
    # (the catalog folder, unless overridden by config/CLI), so the
    # `files[0].parent` fallback below is only hit when analyze_files is
    # called directly without a cache_root. Previously `analyze_catalog`
    # passed None here, which silently switched every CLI run from
    # "cache lives in the catalog root" to "cache lives wherever the
    # first (sorted) file happens to be" -- an unpredictable regression
    # for catalogs with subfolders.
    if cache_root is None:
        cache_dir_cfg = config.get("cache_dir")
        if cache_dir_cfg:
            cache_root = Path(cache_dir_cfg)
            logger.info(f"Cache root from config: {cache_root}")
        else:
            cache_root = files[0].parent
            logger.info(f"Cache root (fallback to first file parent): {cache_root}")
    else:
        cache_root = Path(cache_root)
        logger.info(f"Cache root: {cache_root}")
    cache_root.mkdir(parents=True, exist_ok=True)

    # Determine output directory: explicit argument > config > cache_root.
    #
    # FIX: the previous default built a path from `Path(__file__).parent`,
    # i.e. relative to wherever this script FILE happens to be installed,
    # not relative to the catalog being analyzed. That's surprising at
    # best (reports end up somewhere the user isn't looking) and can
    # outright crash with PermissionError if the script lives in a
    # read-only location (e.g. an installed package directory). Default
    # to cache_root instead, which keeps the old, predictable behavior of
    # writing reports into the catalog itself unless the user opts into
    # something else via config or --output-dir.
    if output_dir is None:
        output_dir_cfg = config.get("output_dir")
        output_dir = Path(output_dir_cfg) if output_dir_cfg else cache_root
        logger.info(f"Output dir: {output_dir}")
    else:
        output_dir = Path(output_dir)
        logger.info(f"Output dir (explicit): {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Exact duplicates - find but DO NOT exclude from comparison.
    #
    # FIX: previously this collapsed every duplicate group into one flat
    # `exact_dup_names` set and then flagged ANY pair touching a name in
    # that set as EXACT (fused_similarity forced to 1.0) — including pairs
    # against completely unrelated tracks. Now we track *which* duplicate
    # group each file belongs to, and only force EXACT when both sides of
    # the pair belong to the SAME group.
    exact_dups = find_exact_duplicates(files)
    dup_group_of: Dict[str, int] = {}
    if exact_dups:
        logger.warning(f"Exact duplicates found: {exact_dups}")
        for gid, group in enumerate(exact_dups):
            for name in group:
                dup_group_of[name] = gid
        logger.info(f"Marked {len(dup_group_of)} files across {len(exact_dups)} duplicate group(s)")

    # Load features (ALL files, including exact duplicates)
    logger.info("Loading features...")
    all_tracks: Dict[str, TrackFeatures] = {}
    total = len(files)
    for i, path in enumerate(files):
        if progress_callback:
            progress_callback(i, total, f"Loading features: {path.name}", int((i / total) * 50))
        try:
            all_tracks[path.name] = load_or_compute_features(path, cache_root, config, ops)
        except Exception as e:
            logger.error(f"Failed to process {path.name}: {e}")
    if progress_callback:
        progress_callback(total, total, "Features loaded", 50)
    logger.info(f"Features loaded for {len(all_tracks)} tracks")

    # NEW TRACK MODE
    if new_track:
        logger.info(f"Checking new track: {new_path.name}")
        new_features = load_or_compute_features(new_path, cache_root, config, ops)

        logger.info("Building baseline distribution...")
        if progress_callback:
            progress_callback(0, 1, "Building baseline...", 55)
        baseline_scores, _ = (build_baseline_parallel if len(all_tracks) > 50 else build_baseline_serial)(
            all_tracks, config, ops
        )
        if progress_callback:
            progress_callback(1, 1, "Baseline ready", 60)
        logger.info(f"Baseline pairs: {len(baseline_scores)}" + (f", median={np.median(baseline_scores):.3f}" if len(baseline_scores) else ""))

        if len(baseline_scores) < config["min_pairs_for_calibration"]:
            logger.warning(f"Only {len(baseline_scores)} baseline pairs (< {config['min_pairs_for_calibration']}); using fallback thresholds.")

        results = []
        track_items = list(all_tracks.items())
        for i, (name, track) in enumerate(track_items):
            if progress_callback:
                progress_callback(i, len(track_items), f"Comparing: {name}", 60 + int((i / len(track_items)) * 35))
            fused, chroma, tempo_ratio, pair = compare_tracks_fast(
                new_features, track, ops, config.get("early_exit_threshold", 0.995)
            )
            level, red_thr, yellow_thr = classify_score(fused, baseline_scores, config)
            if fused > 0.8:
                logger.info(f"HIGH SIMILARITY (new vs catalog): {new_path.name} <-> {name} = {fused:.4f} ({level})")
            results.append(ComparisonResult(
                track_a=new_path.name, track_b=name,
                fused_similarity=fused, chroma_similarity=chroma,
                tempo_ratio=tempo_ratio, segment_pair=pair,
                classification=level, red_threshold=red_thr, yellow_threshold=yellow_thr
            ))
        if progress_callback:
            progress_callback(len(track_items), len(track_items), "Comparison complete", 95)

        results.sort(key=lambda x: x.fused_similarity, reverse=True)

        elapsed = time.time() - start_time
        report = NewTrackReport(
            new_track=str(new_path),
            catalog_size=len(files),
            baseline_pairs=len(baseline_scores),
            baseline_median=float(np.median(baseline_scores)) if len(baseline_scores) else None,
            thresholds={"red": results[0].red_threshold, "yellow": results[0].yellow_threshold} if results else {"red": 0, "yellow": 0},
            results=results[:config["top_k"]],
            exact_duplicates=exact_dups,
            elapsed_seconds=elapsed,
        )

        with open(output_dir / f"{new_path.stem}_similarity_report.json", "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, ensure_ascii=False, indent=2, default=str)
        pd.DataFrame([asdict(r) for r in results]).to_csv(
            output_dir / f"{new_path.stem}_similarity_report.csv",
            index=False, encoding="utf-8-sig"
        )

        if progress_callback:
            progress_callback(1, 1, "Complete", 100)

        return report

    # FULL CATALOG REBUILD
    logger.info("Full catalog rebuild: computing all pairwise similarities...")
    if progress_callback:
        progress_callback(0, 1, "Building baseline...", 55)
    baseline_scores, results = build_baseline_parallel(all_tracks, config, ops)
    if progress_callback:
        progress_callback(1, 1, "Baseline ready", 60)

    total_results = len(results)
    for idx, r in enumerate(results):
        if progress_callback and idx % 10 == 0:
            progress_callback(idx, total_results, "Classifying...", 60 + int((idx / total_results) * 35))

        # FIX: only force EXACT when BOTH tracks in the pair belong to the
        # SAME duplicate group. Previously any pair touching a track that
        # was *anyone's* duplicate got forced to similarity 1.0, which
        # meant one duplicate file in the catalog could make totally
        # unrelated tracks show up as "EXACT" matches.
        group_a = dup_group_of.get(r.track_a)
        group_b = dup_group_of.get(r.track_b)
        if group_a is not None and group_a == group_b:
            level = "EXACT"
            red_thr = 0.0
            yellow_thr = 0.0
            # Force similarity to 1.0 only for the genuine duplicate pair
            fused_sim = 1.0
            chroma_sim = 1.0
            tempo_ratio = 1.0
            logger.warning(f"EXACT pair: {r.track_a} <-> {r.track_b} (similarity forced to 1.0)")
        else:
            level, red_thr, yellow_thr = classify_score(r.fused_similarity, baseline_scores, config)
            fused_sim = r.fused_similarity
            chroma_sim = r.chroma_similarity
            tempo_ratio = r.tempo_ratio
            if fused_sim > 0.8:
                logger.info(f"HIGH SIMILARITY: {r.track_a} <-> {r.track_b} = {fused_sim:.4f} ({level})")

        # FIX: write back by position (idx), not by re-searching the list
        # with `.index(r)`. ComparisonResult is a frozen dataclass compared
        # by value, so `.index(r)` can match the wrong element whenever two
        # entries happen to be field-for-field equal, and it also turns
        # this loop into O(n^2) for no reason.
        results[idx] = ComparisonResult(
            track_a=r.track_a, track_b=r.track_b,
            fused_similarity=fused_sim, chroma_similarity=chroma_sim,
            tempo_ratio=tempo_ratio, segment_pair=r.segment_pair,
            classification=level, red_threshold=red_thr, yellow_threshold=yellow_thr
        )

    results.sort(key=lambda x: x.fused_similarity, reverse=True)

    if progress_callback:
        progress_callback(len(results), len(results), "Classifying complete", 95)

    pd.DataFrame([asdict(r) for r in results]).to_csv(
        output_dir / "catalog_similarity_report.csv", index=False, encoding="utf-8-sig"
    )
    with open(output_dir / "catalog_similarity_report.json", "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, ensure_ascii=False, indent=2, default=str)

    if progress_callback:
        progress_callback(1, 1, "Complete", 100)

    logger.info(f"Full rebuild done in {time.time() - start_time:.1f}s. Reports saved to {output_dir}")
    return results


# ============================================================
# LEGACY analyze_catalog (for CLI)
# ============================================================

def analyze_catalog(
    catalog: Path,
    new_track: Optional[Path] = None,
    rebuild_all: bool = False,
    config: Optional[Dict[str, Any]] = None,
) -> Union[NewTrackReport, List[ComparisonResult]]:
    if config is None:
        config = load_config()
    ops = ArrayOps(use_gpu=config.get("use_gpu", False))
    extensions = set(config["audio_extensions"])
    files = audio_files(catalog, extensions)

    # FIX: default cache_root/output_dir to the catalog itself (matching
    # the tool's long-standing behavior) unless config/CLI explicitly
    # overrides them. Previously this passed cache_root=None, which
    # dropped the catalog root and fell back to an unpredictable
    # "first file's parent" location instead.
    cache_root = Path(config["cache_dir"]) if config.get("cache_dir") else catalog
    output_dir = Path(config["output_dir"]) if config.get("output_dir") else None
    return analyze_files(files, new_track, rebuild_all, config, cache_root, output_dir)


# ============================================================
# CLI
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Self-calibrating audio similarity checker v4",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--catalog", required=True, type=Path, help="Catalog folder")
    parser.add_argument("--new", type=Path, help="New track to check")
    parser.add_argument("--rebuild-all", action="store_true", help="Full O(n^2) catalog rebuild")
    parser.add_argument("--config", type=Path, help="Config file (YAML/JSON)")
    parser.add_argument("--init-config", type=Path, help="Create config template at path")
    parser.add_argument("--cache-dir", type=Path, help="Feature cache directory (overrides config)")
    parser.add_argument("--output-dir", type=Path, help="Directory for report output files (overrides config)")
    parser.add_argument("--workers", type=int, help="Parallel workers (0=auto)")
    parser.add_argument("--use-gpu", action="store_true", help="Use CuPy if available")
    parser.add_argument("--top-k", type=int, help="Top K results to show/save")
    parser.add_argument("--red-percentile", type=float, help="Red threshold percentile")
    parser.add_argument("--yellow-percentile", type=float, help="Yellow threshold percentile")
    parser.add_argument("--min-pairs", type=int, help="Min pairs for percentile calibration")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Log level")
    # FIX: default=None (not the implicit False) so that when the flag is
    # omitted, the CLI-overrides merge (`if v is not None`) leaves any
    # "no_cache: true" set in a config file alone instead of always
    # stomping it back to False.
    parser.add_argument("--no-cache", action="store_true", default=None, help="Disable feature caching (features are recomputed every run, no .features_cache folder is created)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.init_config:
        save_config_template(args.init_config)
        return

    cli_overrides = {k: v for k, v in vars(args).items() if v is not None and k not in ("catalog", "new", "rebuild_all", "config", "init_config", "cache_dir", "output_dir")}
    config = load_config(cli_overrides)
    setup_logging(config.get("log_level", "INFO"))

    catalog = args.catalog.resolve()
    if not catalog.exists():
        logging.error(f"Catalog not found: {catalog}")
        sys.exit(1)

    # Pass cache_dir/output_dir from CLI if provided (these override config)
    if args.cache_dir:
        config["cache_dir"] = str(args.cache_dir.resolve())
    if args.output_dir:
        config["output_dir"] = str(args.output_dir.resolve())

    if args.new:
        new_path = args.new.resolve()
        if not new_path.exists():
            logging.error(f"New track not found: {new_path}")
            sys.exit(1)
        analyze_catalog(catalog, new_track=new_path, config=config)
    elif args.rebuild_all:
        analyze_catalog(catalog, rebuild_all=True, config=config)
    else:
        logging.error("Specify --new <track> or --rebuild-all")
        sys.exit(1)


if __name__ == "__main__":
    main()