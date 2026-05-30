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

# Model weights cache location. Point this at a mounted volume on Railway
# (e.g. TORCH_HOME=/data/torch) to persist weights across restarts.
ENV TORCH_HOME=/app/models
ENV PYTHONUNBUFFERED=1

# Weights are NOT baked into the image (that produced a multi-GB image that
# could fail to deploy). ESM-1b downloads lazily on the first prediction and
# is then cached. To bake it in instead, set PREDOWNLOAD_MODELS at build time
# and uncomment the predownload step below.
# ARG PREDOWNLOAD_MODELS="esm1b"
# ENV PREDOWNLOAD_MODELS=${PREDOWNLOAD_MODELS}
# RUN python -m app.predownload || echo "Skipping model pre-download"

# Railway injects $PORT at runtime and routes its public proxy to it. Expose
# the same default so port auto-detection isn't misled. Locally, $PORT is
# unset and the app falls back to 8080.
EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
