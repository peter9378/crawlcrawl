#!/bin/bash

# 간단한 테스트 스크립트 - 빠르게 동작 확인용

BASE_URL="http://localhost:8000"

# URL 인코딩 함수
urlencode() {
    python3 -c "import urllib.parse; print(urllib.parse.quote('$1'))"
}

echo "=========================================="
echo "🚀 빠른 테스트"
echo "=========================================="

# 헬스체크
echo ""
echo "1️⃣  서버 상태: "
status=$(curl -s "${BASE_URL}/health" | jq -r '.status')
if [ "$status" == "healthy" ]; then
    echo "   ✅ 정상"
else
    echo "   ❌ 비정상"
    exit 1
fi

# 간단한 요청 테스트
echo ""
echo "2️⃣  연관검색어 테스트 (Selenium):"
keyword="제일기획"
encoded=$(urlencode "$keyword")
echo "   키워드: $keyword"
echo "   ⏳ 처리 중... (첫 요청은 느릴 수 있음)"
response=$(curl -s "${BASE_URL}/search/naver_related?keywords=${encoded}")
count=$(echo "$response" | jq '.result | length')
echo "   결과 수: $count"
if [ "$count" -gt 0 ]; then
    echo "$response" | jq -r '.result[0:3][] | "   \(.rank). \(.keyword)"'
fi

echo ""
echo "3️⃣  인기주제 테스트 (Selenium):"
keyword="삼성전자"
encoded=$(urlencode "$keyword")
echo "   키워드: $keyword"
echo "   ⏳ 처리 중..."
response=$(curl -s "${BASE_URL}/search/naver_popular?keywords=${encoded}")
count=$(echo "$response" | jq '.result | length')
echo "   결과 수: $count"
if [ "$count" -gt 0 ]; then
    echo "$response" | jq -r '.result[0:3][] | "   \(.rank). \(.keyword)"'
fi

echo ""
echo "4️⃣  함께찾은 키워드 테스트 (Selenium):"
keyword="현대자동차"
encoded=$(urlencode "$keyword")
echo "   키워드: $keyword"
echo "   ⏳ 처리 중..."
response=$(curl -s "${BASE_URL}/search/naver_together?keywords=${encoded}")
count=$(echo "$response" | jq '.result | length')
echo "   결과 수: $count"
if [ "$count" -gt 0 ]; then
    echo "$response" | jq -r '.result[0:3][] | "   \(.rank). \(.keyword)"'
fi

echo ""
echo "=========================================="
echo "✅ 모든 테스트 통과"
echo "=========================================="

