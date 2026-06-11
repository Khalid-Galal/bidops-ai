# BidOps AI -- Hugging Face Docker Space image.
# A FastAPI tender-operations app. HF Spaces serve the app on port 7860 and run
# the container as a non-root user with UID 1000.
FROM python:3.11-slim

# System libraries needed by some Python deps:
#  - libgl1 / libglib2.0-0: OpenCV (easyocr / docling image handling)
#  - libgomp1: OpenMP runtime used by torch / onnxruntime
# (WeasyPrint/GTK is intentionally NOT installed -- PDF export degrades to 501;
#  Excel export works.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Run as the UID 1000 user HF expects.
RUN useradd -m -u 1000 user
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1 \
    # Warm the embedding model at startup (it is baked into the image below, so
    # this loads from cache rather than downloading -- /ready flips to warm).
    BIDOPS_WARMUP_MODELS_ON_STARTUP=true \
    # The free-tier rotation keys use flash; override via a Space variable.
    BIDOPS_GEMINI_MODEL=gemini-2.5-flash

WORKDIR /home/user/app

# Install CPU-only torch FIRST so the heavy CUDA build is never pulled in as a
# transitive dependency of sentence-transformers / docling / easyocr.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision \
        --index-url https://download.pytorch.org/whl/cpu

# Python dependencies (kept as its own layer for build caching).
COPY --chown=user:user requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Bake the embedding + NLI models into the image so an ephemeral Space does not
# re-download ~1.5GB on every restart. If the build ever times out, comment
# these two lines out -- the app will lazy-download them on first use instead.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')"
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/nli-deberta-v3-xsmall')"

# Application code (app/ package + config/rules.default.json).
COPY --chown=user:user . .

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
