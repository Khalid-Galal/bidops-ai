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
    echo "Persistent storage detected: data/ -> /data/bidops (state survives restarts)"
else
    mkdir -p "$APP_DATA"
    echo "No persistent storage volume: data/ is ephemeral (resets on restart/rebuild)"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 7860
