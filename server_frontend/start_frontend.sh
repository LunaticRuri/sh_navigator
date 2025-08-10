#!/bin/bash

# 프론트엔드 실행 스크립트

echo "🌐 프론트엔드 서버 시작 중..."

# 프로젝트 디렉토리로 이동
cd "$(dirname "$0")"

# HTTP 서버 실행
echo "✅ 프론트엔드 서버를 실행합니다 (http://localhost:8080)"
echo "⏹️  종료하려면 Ctrl+C를 눌러주세요"
echo ""

python3 -m http.server 8080
