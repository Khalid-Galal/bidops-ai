#!/bin/bash
# Startup script for production deployment on Render.com

set -e  # Exit on error

echo "🚀 Starting BidOps AI Backend..."

# Initialize database tables if not exists
echo "📦 Initializing database..."
python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())" || echo "⚠️  Database may already be initialized"

# Create admin user if not exists
echo "👤 Checking admin user..."
python create_admin.py || echo "⚠️  Admin user may already exist"

# Start the application
echo "✅ Starting uvicorn server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
