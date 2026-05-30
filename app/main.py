"""
AlloGator - FastAPI backend.

Allosteric residue prediction from a single protein sequence using protein
language-model attention (Kannan et al., Cell Systems). Exposes model and
example metadata, a prediction endpoint, and CSV / JSON / FASTA / PDB
downloads.
"""

import os
import re
import threading
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator

from . import cache
from .examples import get_example, list_examples
from .models import DEFAULT_MODEL_KEY, get_spec, list_public_models
from .pdb_utils import get_colored_pdbs
from .prediction import (
    compute_attention_scores,
    loaded_model_keys,
    parse_active_residues,
    preload_default,
    scores_to_csv,
    scores_to_json,
    start_idle_reaper,
)

VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Start the server immediately. Loading a model is heavy (~2.6 GB) and must
    never block the server from binding its port, or Railway's proxy reports
    "Application failed to respond". The recommended model is therefore warmed
    in a background thread, and only if ALLOGATOR_WARM_ON_START is truthy;
    otherwise it loads lazily on the first prediction.
    """
    if os.environ.get("ALLOGATOR_WARM_ON_START", "").lower() in ("1", "true", "yes"):
        def _warm():
            try:
                print("Warming recommended model in background...")
                preload_default()
                print("Recommended model ready.")
            except Exception as e:
                print(f"Warning: background model warm failed: {e}")
        threading.Thread(target=_warm, daemon=True).start()
    # Periodically unload idle models so an unused service drops its RAM.
    start_idle_reaper()
    yield


app = FastAPI(
    title="AlloGator",
    description="Allosteric residue prediction from a single sequence using "
                "protein language-model attention (Kannan et al., Cell Systems).",
    version="2.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")


class PredictionRequest(BaseModel):
    sequence: str
    active_residues: str
    model: Optional[str] = DEFAULT_MODEL_KEY
    pdb_code: Optional[str] = None

    @field_validator("sequence")
    @classmethod
    def _validate_sequence(cls, v: str) -> str:
        v = re.sub(r"\s+", "", v.strip().upper())
        # Strip a FASTA header if the user pasted one.
        if v.startswith(">"):
            v = "".join(line for line in v.split("\n") if not line.startswith(">"))
        invalid = set(v) - VALID_AA
        if invalid:
            raise ValueError(f"Invalid amino-acid characters: {sorted(invalid)}")
        if len(v) < 10:
            raise ValueError("Sequence must be at least 10 amino acids.")
        if len(v) > 1022:
            raise ValueError("Sequence must be at most 1022 amino acids (ESM limit).")
        return v

    @field_validator("active_residues")
    @classmethod
    def _validate_active(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Active-site residues cannot be empty.")
        return v.strip()

    @field_validator("pdb_code")
    @classmethod
    def _validate_pdb(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        v = v.strip().lower()
        if not re.match(r"^[a-z0-9]{4}$", v):
            raise ValueError("PDB code must be exactly 4 alphanumeric characters.")
        return v


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/models")
async def get_models():
    """List available models and which one is recommended."""
    return {"models": list_public_models(), "default": DEFAULT_MODEL_KEY}


@app.get("/api/examples")
async def get_examples():
    """List bundled example proteins (metadata only)."""
    return {"examples": list_examples()}


@app.get("/api/examples/{example_id}")
async def get_example_detail(example_id: str):
    """Full example, including sequence, for populating the form."""
    try:
        e = get_example(example_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Example not found.")
    return e


@app.post("/api/predict")
async def predict(request: PredictionRequest):
    """Run allosteric residue prediction for one sequence."""
    try:
        # Validate model selection early for a clean error message.
        try:
            get_spec(request.model)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        active_residues = parse_active_residues(request.active_residues)
        if not active_residues:
            raise HTTPException(status_code=400, detail="No valid active-site residues parsed.")

        seq_len = len(request.sequence)
        out_of_range = [r for r in active_residues if r < 1 or r > seq_len]
        if out_of_range:
            raise HTTPException(
                status_code=400,
                detail=f"Active-site residues out of range (1-{seq_len}): {out_of_range}",
            )

        # Model load + inference is CPU-heavy and blocking; run it off the
        # event loop so /health and other requests stay responsive.
        result = await run_in_threadpool(
            compute_attention_scores,
            request.sequence, active_residues, request.model,
        )

        job_id = uuid.uuid4().hex[:8]

        pdb_raw = pdb_rank = None
        has_pdb = False
        pdb_error = None
        if request.pdb_code:
            _, pdb_raw, pdb_rank = await run_in_threadpool(
                get_colored_pdbs,
                request.pdb_code, result["scores"], active_residues,
            )
            has_pdb = pdb_raw is not None
            if not has_pdb:
                pdb_error = (
                    f"Could not retrieve structure '{request.pdb_code}'. "
                    "Scores are still available below."
                )

        # Persist for downloads (disk-backed so it survives worker restarts).
        cache.save(
            job_id,
            {
                "json": {
                    **scores_to_json(result),
                    "pdb_code": request.pdb_code,
                },
                "pdb_raw": pdb_raw,
                "pdb_rank": pdb_rank,
            },
        )

        ranked = sorted(result["scores"], key=lambda s: s["rank_score"], reverse=True)
        return {
            "job_id": job_id,
            "model": result["model"],
            "sequence_length": seq_len,
            "active_residues": active_residues,
            "scores": ranked,
            "top_residues": [s["residue"] for s in ranked[:10]],
            "has_pdb": has_pdb,
            "pdb_code": request.pdb_code,
            "pdb_error": pdb_error,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------
def _require_job(job_id: str) -> dict:
    data = cache.load_json(job_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Job not found or expired.")
    return data


@app.get("/api/download/csv/{job_id}")
async def download_csv(job_id: str):
    data = _require_job(job_id)
    csv_content = scores_to_csv(data)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="allogator_{job_id}.csv"'},
    )


@app.get("/api/download/json/{job_id}")
async def download_json(job_id: str):
    data = _require_job(job_id)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="allogator_{job_id}.json"'},
    )


@app.get("/api/download/fasta/{job_id}")
async def download_fasta(job_id: str):
    """Top predicted residues as a small annotated FASTA-style text file."""
    data = _require_job(job_id)
    ranked = data.get("scores", [])
    model = data.get("model", {}).get("name", "")
    active = " ".join(map(str, data.get("active_residues", [])))
    lines = [
        f"# AlloGator top predicted allosteric residues",
        f"# model: {model}",
        f"# active-site residues: {active}",
        "# rank\tresidue\taa\trank_percentile",
    ]
    for i, s in enumerate(ranked[:25], 1):
        lines.append(f"{i}\t{s['residue']}\t{s['amino_acid']}\t{s['rank_score']:.1f}")
    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="allogator_top_{job_id}.txt"'},
    )


@app.get("/api/download/pdb_raw/{job_id}")
async def download_pdb_raw(job_id: str):
    _require_job(job_id)
    pdb = cache.load_pdb(job_id, "pdb_raw")
    if pdb is None:
        raise HTTPException(status_code=404, detail="No structure available for this job.")
    return Response(
        content=pdb,
        media_type="chemical/x-pdb",
        headers={"Content-Disposition": f'attachment; filename="allogator_raw_{job_id}.pdb"'},
    )


@app.get("/api/download/pdb_rank/{job_id}")
async def download_pdb_rank(job_id: str):
    _require_job(job_id)
    pdb = cache.load_pdb(job_id, "pdb_rank")
    if pdb is None:
        raise HTTPException(status_code=404, detail="No structure available for this job.")
    return Response(
        content=pdb,
        media_type="chemical/x-pdb",
        headers={"Content-Disposition": f'attachment; filename="allogator_rank_{job_id}.pdb"'},
    )


@app.get("/health")
async def health_check():
    # Stays fast and model-free so Railway's healthcheck always passes; also
    # reports which models are currently resident in RAM for diagnostics.
    return {"status": "healthy", "loaded_models": loaded_model_keys()}
