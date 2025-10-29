#!/bin/bash
# start.sh — startup script for Flask on Railway

echo "🚀 Installing dependencies..."
pip install -r requirements.txt

echo "✅ Starting Flask app with Gunicorn..."
exec gunicorn app:app --bind 0.0.0.0:${PORT:-5000}
