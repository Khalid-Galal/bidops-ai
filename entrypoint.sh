#!/usr/bin/env bash
# BidOps AI container entrypoint.
#
# If Hugging Face persistent storage is mounted (a writable /data volume,
# enabled via Space Settings -> Persistent storage), keep ALL runtime state
# there -- database, uploads, vector index, package/deliverable artifacts --
# so projects survive restarts, rebuilds, and Space sleep.
#
# Without the volume this falls back to the container-local data/ directory,
# which is ephemeral: exactly the previous behavior, no configuration needed.
set -e

APP_DATA="/home/user/app/data"

if [ -d /data ] && [ -w /data ]; then
    mkdir -p /data/bidops
    # The app writes CWD-relative data/ paths; route them onto the volume.
    rm -rf "$APP_DATA"
    ln -sfn /data/bidops "$APP_DATA"
    # Route every ML model cache onto the volume too: models download at most
    # once per volume lifetime instead of being baked into the image (which
    # made it too big to schedule) or re-downloaded on every restart.
    # Env names verified against the pinned packages: HF_HOME (huggingface_hub:
    # sentence-transformers embedding + NLI cross-encoder + docling HF snapshots),
    # DOCLING_CACHE_DIR (docling AppSettings env_prefix DOCLING_ + cache_dir),
    # EASYOCR_MODULE_PATH (easyocr's preferred override).
    mkdir -p /data/caches/hf /data/caches/docling /data/caches/easyocr
    export HF_HOME=/data/caches/hf
    export DOCLING_CACHE_DIR=/data/caches/docling
    export EASYOCR_MODULE_PATH=/data/caches/easyocr
    echo "Persistent storage detected: data/ -> /data/bidops, model caches -> /data/caches (state survives restarts)"
else
    mkdir -p "$APP_DATA"
    echo "No persistent storage volume: data/ is ephemeral (resets on restart/rebuild)"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 7860
