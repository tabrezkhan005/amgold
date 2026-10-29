# AmGold API — CPU PyTorch + DINOv2 weights baked in at build time.
# Build context: backend/  (Railway Root Directory = backend)
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf \
    TRANSFORMERS_CACHE=/opt/hf

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

# Bake model weights into the image (no download at startup).
ARG MODEL_NAME=facebook/dinov2-small
ENV MODEL_NAME=${MODEL_NAME}
RUN python -c "from transformers import AutoImageProcessor, AutoModel; \
    m='${MODEL_NAME}'; \
    AutoImageProcessor.from_pretrained(m); \
    AutoModel.from_pretrained(m); \
    print('model_cached', m)"

COPY . .

# One Uvicorn worker; Railway injects $PORT.
ENV PORT=8000 \
    LOAD_EMBEDDER=true
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
