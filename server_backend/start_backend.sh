#!/bin/bash

# Backend run script

echo "🔧 Starting backend server..."

source /home/namu101/myvenv/bin/activate

cd /home/namu101/msga/sh_network_app/backend

# Run server
echo "✅ Starting FastAPI server (http://localhost:8000)"
echo "📖 API docs: http://localhost:8000/docs"
echo "⏹️  Press Ctrl+C to stop"
echo ""

gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app -b 0.0.0.0:8000
