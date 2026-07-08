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
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('MoritzLaurer/mDeBERTa-v3-base-mnli-xnli')"

# Bake the heavy PDF-parsing models so the first tender ingest does not download
# ~2GB over the network on an ephemeral Space. Both caches land under HOME
# (already /home/user here): docling -> ~/.cache/docling/models, easyocr ->
# ~/.EasyOCR, which is exactly where pdf_parser.py reads them at runtime.
# If the build ever times out, comment these two lines out -- the app will
# lazy-download the models on first PDF parse instead.
RUN python -c "from docling.utils.model_downloader import download_models; download_models()"
RUN python -c "import easyocr; easyocr.Reader(['en', 'ar'], gpu=False)"

# Application code (app/ package + config/rules.default.json).
COPY --chown=user:user . .

EXPOSE 7860
# entrypoint.sh routes data/ onto the persistent /data volume when the HF
# persistent-storage add-on is enabled; otherwise data/ stays ephemeral.
CMD ["bash", "entrypoint.sh"]
