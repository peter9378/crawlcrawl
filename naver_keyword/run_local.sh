#!/bin/bash

# 로컬 테스트 실행 스크립트
# Docker 빌드 없이 바로 gunicorn으로 테스트

set -e

echo "=========================================="
echo "🚀 로컬 테스트 시작"
echo "=========================================="

# 1. Python 버전 확인
echo ""
echo "1️⃣  Python 버전 확인..."
python3 --version

# 2. 가상환경 확인/생성
if [ ! -d "venv" ]; then
    echo ""
    echo "2️⃣  가상환경 생성 중..."
    python3 -m venv venv
    echo "✅ 가상환경 생성 완료"
else
    echo ""
    echo "2️⃣  기존 가상환경 사용"
fi

# 3. 가상환경 활성화
echo ""
echo "3️⃣  가상환경 활성화..."
source venv/bin/activate

# 4. 의존성 설치
echo ""
echo "4️⃣  의존성 설치 중..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✅ 의존성 설치 완료"

# 5. Chrome 확인
echo ""
echo "5️⃣  Chrome 설치 확인..."
if [ -d "/Applications/Google Chrome.app" ]; then
    echo "✅ Chrome 설치 확인됨"
else
    echo "⚠️  Chrome이 설치되지 않았습니다."
    echo "   Chrome을 설치해주세요: https://www.google.com/chrome/"
    exit 1
fi

# 6. Gunicorn 실행
echo ""
echo "=========================================="
echo "🎉 Gunicorn 서버 시작"
echo "=========================================="
echo ""
echo "📍 주소: http://localhost:8000"
echo "📍 엔드포인트:"
echo "   - GET http://localhost:8000/health"
echo "   - GET http://localhost:8000/stats"
echo "   - GET http://localhost:8000/search/naver_related?keywords=제일기획"
echo "   - GET http://localhost:8000/search/naver_popular?keywords=제일기획"
echo "   - GET http://localhost:8000/search/naver_together?keywords=제일기획"
echo ""
echo "🛑 종료: Ctrl+C"
echo "=========================================="
echo ""

# gunicorn 실행 (로컬 포트 8000 사용)
gunicorn app:app \
    --workers 1 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile - \
    --log-level info

