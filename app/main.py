"""
AlloPred Web Application - FastAPI Backend
"""

import os
import uuid
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator
import re

from .prediction import compute_attention_scores, scores_to_csv, load_model
from .pdb_utils import get_colored_pdbs

# Initialize FastAPI app
app = FastAPI(
    title="AlloPred",
    description="Allosteric site prediction using ESM1b attention scores",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# In-memory storage for results (in production, use Redis or similar)
results_cache = {}


class PredictionRequest(BaseModel):
    sequence: str
    active_residues: str  # Comma-separated list
    pdb_code: Optional[str] = None

    @field_validator('sequence')
    @classmethod
    def validate_sequence(cls, v):
        v = v.strip().upper()
        # Remove whitespace and newlines
        v = re.sub(r'\s+', '', v)
        # Validate amino acid characters
        valid_aa = set('ACDEFGHIKLMNPQRSTVWY')
        invalid = set(v) - valid_aa
        if invalid:
            raise ValueError(f"Invalid amino acid characters: {invalid}")
        if len(v) < 10:
            raise ValueError("Sequence must be at least 10 amino acids")
        if len(v) > 1022:
            raise ValueError("Sequence must be at most 1022 amino acids (ESM1b limit)")
        return v

    @field_validator('active_residues')
    @classmethod
    def validate_active_residues(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Active residues cannot be empty")
        return v

    @field_validator('pdb_code')
    @classmethod
    def validate_pdb_code(cls, v):
        if v is None or v.strip() == '':
            return None
        v = v.strip().lower()
        if not re.match(r'^[a-z0-9]{4}$', v):
            raise ValueError("PDB code must be exactly 4 alphanumeric characters")
        return v


class PredictionResponse(BaseModel):
    job_id: str
    scores: List[dict]
    sequence_length: int
    active_residues: List[int]
    has_pdb: bool


@app.on_event("startup")
async def startup_event():
    """Pre-load the model on startup."""
    print("Pre-loading ESM1b model...")
    try:
        load_model()
        print("Model loaded successfully")
    except Exception as e:
        print(f"Warning: Could not pre-load model: {e}")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    """Run allosteric site prediction."""
    try:
        # Parse active residues
        active_residues = []
        for part in request.active_residues.split(','):
            part = part.strip()
            if '-' in part:
                # Handle ranges like "10-20"
                start, end = part.split('-')
                active_residues.extend(range(int(start), int(end) + 1))
            else:
                active_residues.append(int(part))

        # Validate active residues are within sequence
        seq_len = len(request.sequence)
        invalid_residues = [r for r in active_residues if r < 1 or r > seq_len]
        if invalid_residues:
            raise HTTPException(
                status_code=400,
                detail=f"Active residues out of range (1-{seq_len}): {invalid_residues}"
            )

        # Compute scores
        result = compute_attention_scores(request.sequence, active_residues)

        # Generate job ID
        job_id = str(uuid.uuid4())[:8]

        # Get PDB files if requested
        pdb_raw = None
        pdb_rank = None
        has_pdb = False

        if request.pdb_code:
            original_pdb, pdb_raw, pdb_rank = get_colored_pdbs(
                request.pdb_code,
                result['scores']
            )
            if pdb_raw is not None:
                has_pdb = True

        # Store results in cache
        results_cache[job_id] = {
            'scores': result['scores'],
            'sequence': request.sequence,
            'active_residues': active_residues,
            'pdb_code': request.pdb_code,
            'pdb_raw': pdb_raw,
            'pdb_rank': pdb_rank
        }

        return PredictionResponse(
            job_id=job_id,
            scores=result['scores'],
            sequence_length=result['sequence_length'],
            active_residues=active_residues,
            has_pdb=has_pdb
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.get("/api/download/csv/{job_id}")
async def download_csv(job_id: str):
    """Download scores as CSV."""
    if job_id not in results_cache:
        raise HTTPException(status_code=404, detail="Job not found")

    scores = results_cache[job_id]['scores']
    csv_content = scores_to_csv(scores)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=allopred_scores_{job_id}.csv"}
    )


@app.get("/api/download/pdb_raw/{job_id}")
async def download_pdb_raw(job_id: str):
    """Download PDB with raw attention scores in B-factor."""
    if job_id not in results_cache:
        raise HTTPException(status_code=404, detail="Job not found")

    pdb_content = results_cache[job_id].get('pdb_raw')
    if pdb_content is None:
        raise HTTPException(status_code=404, detail="PDB file not available")

    pdb_code = results_cache[job_id].get('pdb_code', 'structure')

    return Response(
        content=pdb_content,
        media_type="chemical/x-pdb",
        headers={"Content-Disposition": f"attachment; filename={pdb_code}_raw_scores.pdb"}
    )


@app.get("/api/download/pdb_rank/{job_id}")
async def download_pdb_rank(job_id: str):
    """Download PDB with rank scores in B-factor."""
    if job_id not in results_cache:
        raise HTTPException(status_code=404, detail="Job not found")

    pdb_content = results_cache[job_id].get('pdb_rank')
    if pdb_content is None:
        raise HTTPException(status_code=404, detail="PDB file not available")

    pdb_code = results_cache[job_id].get('pdb_code', 'structure')

    return Response(
        content=pdb_content,
        media_type="chemical/x-pdb",
        headers={"Content-Disposition": f"attachment; filename={pdb_code}_rank_scores.pdb"}
    )


@app.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {"status": "healthy"}
