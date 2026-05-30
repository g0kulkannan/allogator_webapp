FROM python:3.10-slim

WORKDIR /app

# System deps (build-essential needed by some torch/scipy wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install the CPU-only torch wheel first (the default wheel pulls ~2 GB of
# CUDA libraries that are useless on a CPU instance and bloat the image).
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch

# Remaining Python deps. torch is already satisfied, so it won't be re-pulled.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Model weights cache lives inside the image
ENV TORCH_HOME=/app/models
ENV PYTHONUNBUFFERED=1

# Which model(s) to bake into the image at build time. Space-separated keys
# from app/models.py. Default: just the recommended ESM-1b. Set to empty to
# skip baking (weights download lazily on first request instead).
ARG PREDOWNLOAD_MODELS="esm1b"
ENV PREDOWNLOAD_MODELS=${PREDOWNLOAD_MODELS}
RUN python -m app.predownload || echo "Skipping model pre-download"

# Railway provides $PORT; default to 8000 locally.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
