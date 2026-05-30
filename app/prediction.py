"""
AlloGator - attention-based allosteric residue scoring.

Implements the scoring procedure from Kannan et al., Cell Systems:
for a single input sequence, take the mean attention map across all heads
and layers of a protein language model, sum each residue's attention to
the active-site residues, exclude residues sequence-adjacent to the active
site, and rank the remainder. Higher rank = more likely allosteric.

The model-specific work (loading, tokenization, attention extraction) lives
in backends.py; this module is backend-agnostic. Loaded backends are cached
with an LRU cap so a small instance keeps at most one model resident.
"""

import gc
import os
import threading
from collections import OrderedDict
from typing import Dict, List, Optional

import numpy as np
from scipy.stats import rankdata

from .backends import build_backend
from .models import DEFAULT_MODEL_KEY, ModelSpec, get_spec

# How many distinct models may be resident at once. These models are large
# (ESM-1b ~2.6 GB, ProtT5-XL ~3 GB, ESM++ ~2.4 GB), so default to 1 on a
# small instance. Override with ALLOGATOR_MAX_MODELS.
MAX_RESIDENT_MODELS = int(os.environ.get("ALLOGATOR_MAX_MODELS", "1"))

# LRU cache of key -> loaded backend. Guarded by a lock because FastAPI may
# call in from multiple threads.
_loaded: "OrderedDict[str, object]" = OrderedDict()
_load_lock = threading.Lock()


def load_backend(model_key: Optional[str] = None):
    """
    Load (or fetch from cache) the backend for a model key. Returns
    (backend, spec). Thread-safe; evicts the least-recently-used backend
    once MAX_RESIDENT_MODELS is exceeded and frees its memory.
    """
    spec: ModelSpec = get_spec(model_key)
    key = spec.key

    with _load_lock:
        if key in _loaded:
            _loaded.move_to_end(key)
            return _loaded[key], spec

        print(f"Loading model '{spec.name}' ({spec.params}, backend={spec.backend})...")
        backend = build_backend(spec)
        _loaded[key] = backend
        _loaded.move_to_end(key)
        print(f"Model '{spec.name}' ready.")

        while len(_loaded) > MAX_RESIDENT_MODELS:
            old_key, _ = _loaded.popitem(last=False)
            print(f"Evicting model '{old_key}' to free memory")
            _free_memory()

        return backend, spec


def _free_memory() -> None:
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def preload_default() -> None:
    """Warm the recommended model at startup (best-effort)."""
    load_backend(DEFAULT_MODEL_KEY)


def parse_active_residues(raw: str) -> List[int]:
    """
    Parse a comma-separated active-site spec into a sorted, de-duplicated
    list of 1-indexed residue numbers. Supports ranges like '10-20'.
    """
    residues = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            start, end = int(start.strip()), int(end.strip())
            if start > end:
                start, end = end, start
            residues.update(range(start, end + 1))
        else:
            residues.add(int(part))
    return sorted(residues)


def compute_attention_scores(
    sequence: str,
    active_residues: List[int],
    model_key: Optional[str] = None,
) -> Dict:
    """
    Compute per-residue allosteric scores for one sequence.

    Returns a dict with model info, sequence_length, active_residues, and a
    list of score dicts (residue, amino_acid, raw_score, rank_score, is_top).
    """
    backend, spec = load_backend(model_key)

    final_attention = backend.attention(sequence)  # (L, L), special tokens removed
    n = final_attention.shape[0]
    active_set = set(active_residues)

    scores = []
    for resi in range(len(sequence)):
        residue_num = resi + 1  # 1-indexed

        # Exclude the active site itself and residues sequence-adjacent to it
        # (within +/-1), matching the paper's procedure.
        if residue_num in active_set:
            continue
        if any(abs(residue_num - ar) < 2 for ar in active_residues):
            continue
        if resi >= n:
            continue

        raw_score = 0.0
        for ar in active_residues:
            if 0 <= ar - 1 < n:
                raw_score += float(final_attention[ar - 1, resi])

        scores.append({
            "residue": residue_num,
            "amino_acid": sequence[resi],
            "raw_score": raw_score,
        })

    if scores:
        raw_vals = [s["raw_score"] for s in scores]
        ranks = rankdata(raw_vals, method="average")
        percentiles = (ranks / len(ranks)) * 100.0
        for s, p in zip(scores, percentiles):
            s["rank_score"] = float(p)
            s["is_top"] = bool(p >= 90.0)  # top decile, the paper's enrichment band

    return {
        "model": spec.to_public(),
        "sequence_length": len(sequence),
        "active_residues": active_residues,
        "scores": scores,
    }


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------
def scores_to_csv(result: Dict) -> str:
    """CSV with a small header block describing the run, then the table."""
    model = result.get("model", {})
    active = result.get("active_residues", [])
    lines = [
        "# AlloGator allosteric residue scores",
        f"# model,{model.get('name', '')}",
        f"# active_site_residues,{' '.join(map(str, active))}",
        f"# sequence_length,{result.get('sequence_length', '')}",
        "residue,amino_acid,raw_score,rank_percentile,top_decile",
    ]
    for s in sorted(result["scores"], key=lambda x: x["rank_score"], reverse=True):
        lines.append(
            f"{s['residue']},{s['amino_acid']},{s['raw_score']:.6f},"
            f"{s['rank_score']:.2f},{int(s.get('is_top', False))}"
        )
    return "\n".join(lines) + "\n"


def scores_to_json(result: Dict) -> Dict:
    """Full result as a JSON-serializable dict (scores sorted by rank)."""
    ranked = sorted(result["scores"], key=lambda x: x["rank_score"], reverse=True)
    return {
        "model": result.get("model", {}),
        "sequence_length": result.get("sequence_length"),
        "active_residues": result.get("active_residues", []),
        "scores": ranked,
    }
