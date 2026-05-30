"""
Tiny disk-backed result cache.

Prediction results (scores + any generated PDB files) are written to a temp
directory keyed by job id, so the download endpoints keep working even if the
in-memory dict is lost (worker restart, multiple workers). Entries are pruned
by age and count to bound disk use on a small Railway volume.
"""

import json
import os
import tempfile
import time
from typing import Dict, Optional

CACHE_DIR = os.environ.get(
    "ALLOGATOR_CACHE_DIR", os.path.join(tempfile.gettempdir(), "allogator_jobs")
)
MAX_AGE_SECONDS = int(os.environ.get("ALLOGATOR_CACHE_TTL", str(6 * 3600)))
MAX_ENTRIES = int(os.environ.get("ALLOGATOR_CACHE_MAX", "200"))

os.makedirs(CACHE_DIR, exist_ok=True)


def _job_path(job_id: str, name: str) -> str:
    return os.path.join(CACHE_DIR, f"{job_id}__{name}")


def save(job_id: str, payload: Dict) -> None:
    """Persist a job. `payload` may contain 'json' (dict) and PDB strings."""
    _prune()
    if "json" in payload:
        with open(_job_path(job_id, "result.json"), "w") as f:
            json.dump(payload["json"], f)
    for name in ("pdb_raw", "pdb_rank"):
        if payload.get(name):
            with open(_job_path(job_id, f"{name}.pdb"), "w") as f:
                f.write(payload[name])


def load_json(job_id: str) -> Optional[Dict]:
    path = _job_path(job_id, "result.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_pdb(job_id: str, which: str) -> Optional[str]:
    path = _job_path(job_id, f"{which}.pdb")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return f.read()


def _prune() -> None:
    """Drop entries older than the TTL, then enforce a max file count."""
    now = time.time()
    try:
        files = [os.path.join(CACHE_DIR, f) for f in os.listdir(CACHE_DIR)]
    except FileNotFoundError:
        os.makedirs(CACHE_DIR, exist_ok=True)
        return
    for path in files:
        try:
            if now - os.path.getmtime(path) > MAX_AGE_SECONDS:
                os.remove(path)
        except OSError:
            pass
    # Enforce count cap (oldest first).
    try:
        files = sorted(
            (os.path.join(CACHE_DIR, f) for f in os.listdir(CACHE_DIR)),
            key=os.path.getmtime,
        )
    except FileNotFoundError:
        return
    while len(files) > MAX_ENTRIES:
        try:
            os.remove(files.pop(0))
        except OSError:
            files.pop(0) if files else None
