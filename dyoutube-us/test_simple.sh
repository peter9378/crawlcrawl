#!/bin/bash

# 간단한 테스트 스크립트 - 빠르게 동작 확인용

BASE_URL="http://localhost:8000"

# URL 인코딩 함수
urlencode() {
    python3 -c "import urllib.parse; print(urllib.parse.quote('$1'))"
}

echo "=========================================="
echo "🚀 dyoutube 빠른 테스트"
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

# 테스트 엔드포인트
echo ""
echo "2️⃣  테스트 엔드포인트:"
response=$(curl -s "${BASE_URL}/test")
result=$(echo "$response" | jq -r '.result')
if [ "$result" == "test success" ]; then
    echo "   ✅ 정상"
else
    echo "   ❌ 비정상"
    exit 1
fi

# 간단한 유튜브 검색 테스트
echo ""
echo "3️⃣  유튜브 검색 테스트 (Selenium 드라이버 풀):"
keyword="파이썬 강의"
limit=3
encoded=$(urlencode "$keyword")
echo "   키워드: $keyword"
echo "   제한: $limit개"
echo "   ⏳ 처리 중... (첫 요청은 드라이버 생성으로 느릴 수 있음)"
response=$(curl -s "${BASE_URL}/search/list?keywords=${encoded}&limit=${limit}")
count=$(echo "$response" | jq '.result | length')
echo "   결과 수: $count"
if [ "$count" -gt 0 ]; then
    echo "   📹 동영상 제목:"
    echo "$response" | jq -r '.result[0:3][] | "      - \(.title)"'
fi

echo ""
echo "=========================================="
echo "✅ 모든 테스트 통과"
echo "=========================================="
echo ""
echo "💡 팁:"
echo "   - 첫 Selenium 요청은 5-10초 소요 (드라이버 생성)"
echo "   - 이후 요청은 더 빨라짐 (드라이버 재사용)"
echo ""

