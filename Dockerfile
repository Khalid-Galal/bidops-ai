# BidOps AI -- Hugging Face Docker Space image.
# A FastAPI tender-operations app. HF Spaces serve the app on port 7860 and run
# the container as a non-root user with UID 1000.
FROM python:3.11-slim

# System libraries needed by some Python deps:
#  - libgl1 / libglib2.0-0: OpenCV (easyocr / docling image handling)
#  - libgomp1: OpenMP runtime used by torch / onnxruntime
#  - libpango-1.0-0 / libpangoft2-1.0-0 / libharfbuzz-subset0 / fontconfig:
#    WeasyPrint's native text-rendering stack (no GTK needed on WeasyPrint>=61).
#    With these present pdf_export.py's capability probe succeeds and PDF export
#    returns 200 instead of degrading to 501.
#  - fonts-dejavu-core / fonts-noto-core: Latin + Arabic (Noto Naskh) glyphs so
#    tender deliverables (which include Arabic) render correctly. Debian ships
#    Naskh inside fonts-noto-core; there is no fonts-noto-naskh-arabic package.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz-subset0 \
        fontconfig \
        fonts-dejavu-core \
        fonts-noto-core \
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
    # Cap free-tier LLM/API usage: token-bucket limiter on (safety valve).
    BIDOPS_RATE_LIMIT_ENABLED=true \
    # The free-tier rotation keys use flash; override via a Space variable.
    BIDOPS_GEMINI_MODEL=gemini-2.5-flash

WORKDIR /home/user/app

# Install CPU-only torch FIRST so the heavy CUDA build is never pulled in as a
# transitive dependency of sentence-transformers / docling / easyocr.
# MUST match requirements.txt's torch pin exactly: `torch==X.Y.Z` is satisfied
# by the X.Y.Z+cpu wheel, so pip leaves it alone -- but ANY version mismatch
# makes the requirements install "correct" it from PyPI, which is the CUDA
# build (+~8GB of nvidia wheels; wedged the Space in APP_STARTING once).
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.12.0 torchvision \
        --index-url https://download.pytorch.org/whl/cpu

# Python dependencies (kept as its own layer for build caching).
COPY --chown=user:user requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# NO models are baked into the image. A fully-baked image (~+4GB: embedding,
# multilingual NLI, docling layout/table, easyocr en+ar) made HF's free-tier
# scheduler refuse to place the container ("unable to schedule" / wedged in
# APP_STARTING). Instead entrypoint.sh routes all model caches onto the
# persistent /data volume, so each model downloads at most once per volume
# lifetime and every later restart/rebuild warms from disk -- same effect as
# baking, without the image weight. Without a volume the caches are ephemeral
# and re-download per restart (degraded but functional).

# Application code (app/ package + config/rules.default.json).
COPY --chown=user:user . .

EXPOSE 7860
# entrypoint.sh routes data/ onto the persistent /data volume when the HF
# persistent-storage add-on is enabled; otherwise data/ stays ephemeral.
CMD ["bash", "entrypoint.sh"]
