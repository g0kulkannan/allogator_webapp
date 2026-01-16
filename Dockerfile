FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV TORCH_HOME=/app/models
ENV PYTHONUNBUFFERED=1

# Pre-download ESM1b model weights (this caches in the image)
RUN python -c "import esm; esm.pretrained.esm1b_t33_650M_UR50S()"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
