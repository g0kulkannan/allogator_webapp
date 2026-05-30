# AlloGator — web app

Predict allosteric residues from a **single protein sequence** using protein
language-model attention. Given a sequence and its active-site residues,
AlloGator scores every other residue by how strongly the model attends from it
to the active site; high-attention, non-contacting residues tend to be
allosteric.

Method and benchmarks: Kannan et al., *Single-Sequence, Structure-Free
Allosteric Residue Prediction with Protein Language Models*, Cell Systems
(in revision). Code & data: <https://github.com/g0kulkannan/allogator>.

---

## What it does

- **The paper's four models.** ESM-1b (recommended — highest median per-protein
  AUROC in the paper), ESM-2 650M, ProtT5-XL, and ESM++ (an open ESM-C
  re-implementation). Models load lazily and an LRU cap (default **one** model
  resident) keeps the container within memory on a small instance.
- **Clear scores.** Results lead with the **rank percentile** (the paper's
  headline metric), flag the top decile, and show a per-residue plot, a 3D
  structure view, and a sortable/filterable table.
- **Easy downloads.** CSV (with a run header), JSON, a top-residues TSV, and
  PDB files whose B-factor column carries the score (rank- and raw-colored) for
  one-command coloring in PyMOL / ChimeraX / Mol*.
- **One-click examples.** DPP4, ACE2, and *B. longum* L-LDH from the paper,
  pre-filled with their UniProt active sites.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# open http://localhost:8000
```

The first prediction downloads the selected model's weights (~30–60 s for
ESM-1b); later runs reuse the cached model.

## Deploy on Railway

The repo is Railway-ready (`railway.json` + `Dockerfile`).

1. Create a new Railway project from this repo.
2. It builds the Docker image and starts the server on `$PORT` automatically.
3. Health checks hit `/health`.

By default the image **bakes in ESM-1b** at build time so the first request is
fast. To change which model(s) are pre-downloaded, set the build arg:

```
PREDOWNLOAD_MODELS="esm1b"   # space-separated keys, or "" to skip
```

Only ESM-1b is baked in by default. ProtT5-XL and ESM++ are large; they
download on first use (the first request that selects them is slow, then
they're cached).

### Useful environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ALLOGATOR_MAX_MODELS` | `1` | Max models resident in memory at once (LRU eviction). Keep at `1` on a small instance. |
| `ALLOGATOR_IDLE_UNLOAD_SECONDS` | `900` | Unload models from RAM after this many seconds with no predictions; the next request reloads on demand. `0` disables. |
| `ALLOGATOR_WARM_ON_START` | unset | If truthy, warm ESM-1b in a background thread at boot (never blocks startup). Leave unset to load lazily. |
| `ALLOGATOR_CACHE_DIR` | system temp | Where job results / generated PDBs are stored. |
| `ALLOGATOR_CACHE_TTL` | `21600` | Job retention in seconds (6 h). |
| `ALLOGATOR_CACHE_MAX` | `200` | Max stored jobs before oldest are pruned. |
| `PORT` | `8000` | Server port (Railway sets this). |

> Memory note: each model is large (ESM-1b ~2.6 GB, ESM-2 650M ~2.6 GB,
> ProtT5-XL ~3 GB, ESM++ ~2.4 GB in fp32). With `ALLOGATOR_MAX_MODELS=1`
> only one is resident at a time; switching models evicts and frees the
> previous one, so peak RAM stays around a single model's footprint plus
> overhead. The server itself binds its port immediately and `/health`
> stays fast and model-free, so the app never fails Railway's healthcheck
> while a model is loading. `GET /health` also reports `loaded_models` so
> you can see what is currently resident.

### Idle unloading

By default the service unloads a model after 15 minutes of no predictions,
returning to a small idle footprint; the next prediction transparently
reloads it (slower, then fast again while in use). Tune the window with
`ALLOGATOR_IDLE_UNLOAD_SECONDS`, or set it to `0` to keep models resident.

### Persisting model weights across restarts (Railway volume)

Railway's container filesystem is ephemeral, so by default ProtT5 / ESM++
weights re-download after every redeploy or restart. To cache them
permanently, attach a **Volume** and point the model caches at it:

1. In the Railway service, add a Volume mounted at e.g. `/data`.
2. Set these variables so weights land on the volume:
   ```
   HF_HOME=/data/hf          # ProtT5 + ESM++ (HuggingFace) weights
   TORCH_HOME=/data/torch    # ESM-1b / ESM-2 (fair-esm) weights
   ```
3. Redeploy. The first user to pick each model pays the download once; it
   persists on the volume thereafter.

This is the lighter-weight alternative to baking all four models into the
image via `PREDOWNLOAD_MODELS` (which makes a much larger, slower-building
image but gives instant cold starts).

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/models` | GET | Available models + the recommended default. |
| `/api/examples` | GET | Bundled example proteins (metadata). |
| `/api/examples/{id}` | GET | Full example incl. sequence. |
| `/api/predict` | POST | Run a prediction. |
| `/api/download/{csv,json,fasta}/{job}` | GET | Score downloads. |
| `/api/download/{pdb_rank,pdb_raw}/{job}` | GET | Score-colored structures. |
| `/health` | GET | Health check. |

`POST /api/predict` body:

```json
{
  "sequence": "MKT...",
  "active_residues": "630, 708, 740",
  "model": "esm1b",
  "pdb_code": "1QHA"
}
```

`active_residues` is a comma-separated, 1-indexed list; ranges like `124-126`
are allowed. `model` and `pdb_code` are optional.

## Project layout

```
app/
  main.py          FastAPI app, endpoints, validation
  models.py        model registry (keys, descriptions) — dependency-free
  backends.py      per-model loading + attention extraction (esm/prott5/esm++)
  prediction.py    backend-agnostic scoring + lazy, LRU-capped loading
  pdb_utils.py     PDB fetch + B-factor annotation
  examples.py      bundled paper proteins
  cache.py         disk-backed job cache for downloads
  predownload.py   build-time weight pre-download
  templates/index.html
static/
  css/style.css
  js/app.js
Dockerfile, railway.json, requirements.txt
```

## Notes

- Sequences are treated as **monomers** (single chain); benchmarking was on
  single-chain sequences. Max length 1022 aa (ESM positional-embedding limit).
- Active-site residues anchor the attention sum; residues sequence-adjacent to
  them (±1) are excluded from scoring, matching the paper.
