#!/bin/bash

# Python 가상환경 활성화
echo "🔧 Starting model server..."

source /home/namu101/myvenv/bin/activate


cd /home/namu101/msga/sh_network_app/model_server

# Run server
echo "✅ Starting FastAPI server (http://localhost:8001)"
echo "📖 API docs: http://localhost:8001/docs"
echo "⏹️  Press Ctrl+C to stop"
echo ""

# 모델 서버 실행. 워커 수는 1개, 포트는 8001번 (기존 앱과 다른 포트 사용!!)
gunicorn -w 1 -k uvicorn.workers.UvicornWorker main:app -b 0.0.0.0:8001