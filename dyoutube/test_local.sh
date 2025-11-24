#!/bin/bash

# 로컬 서버 테스트 스크립트
# 서버가 실행 중일 때 다른 터미널에서 실행

BASE_URL="http://localhost:8000"

# URL 인코딩 함수
urlencode() {
    python3 -c "import urllib.parse; print(urllib.parse.quote('$1'))"
}

# 결과 출력 함수
print_result() {
    local response="$1"
    local keyword=$(echo "$response" | jq -r '.keyword')
    local count=$(echo "$response" | jq '.result | length')
    
    echo "   📌 키워드: $keyword"
    echo "   📊 결과 수: $count"
    
    if [ "$count" -gt 0 ]; then
        echo "   📋 결과:"
        echo "$response" | jq -r '.result[] | "      \(.videoType | ascii_upcase) | \(.title[:60])..."' | head -5
        if [ "$count" -gt 5 ]; then
            echo "      ... (총 $count 개)"
        fi
    else
        echo "   ⚠️  결과 없음"
    fi
}

echo "=========================================="
echo "🧪 dyoutube 로컬 서버 테스트"
echo "=========================================="
echo ""

# 루트 엔드포인트
echo "0️⃣  루트 엔드포인트 확인..."
curl -s "${BASE_URL}/" | jq '.service, .version, .features'
echo ""

# 헬스체크
echo "1️⃣  헬스체크 테스트..."
curl -s "${BASE_URL}/health" | jq .
echo ""

# 통계
echo "2️⃣  초기 통계 확인..."
curl -s "${BASE_URL}/stats" | jq .
echo ""

# 테스트 엔드포인트
echo "3️⃣  테스트 엔드포인트..."
curl -s "${BASE_URL}/test" | jq .
echo ""

# 유튜브 검색 테스트 - 첫 번째 (드라이버 생성)
echo "4️⃣  유튜브 검색 테스트 - 첫 번째 요청 (드라이버 생성 - 느림)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

keyword="파이썬 강의"
limit=5
encoded=$(urlencode "$keyword")
echo "   🔍 테스트: $keyword (limit: $limit)"
echo "   ⏱️  측정 시작..."
result=$(time curl -s "${BASE_URL}/search/list?keywords=${encoded}&limit=${limit}" 2>&1)
response=$(echo "$result" | tail -1)
print_result "$response"
echo ""

# 유튜브 검색 테스트 - 두 번째 (드라이버 재사용)
echo "5️⃣  유튜브 검색 테스트 - 두 번째 요청 (드라이버 재사용 - 빠름!)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

keyword="자바스크립트 튜토리얼"
limit=3
encoded=$(urlencode "$keyword")
echo "   🔍 테스트: $keyword (limit: $limit)"
echo "   ⏱️  측정 시작..."
result=$(time curl -s "${BASE_URL}/search/list?keywords=${encoded}&limit=${limit}" 2>&1)
response=$(echo "$result" | tail -1)
print_result "$response"
echo ""

# 유튜브 검색 테스트 - 세 번째 (드라이버 재사용)
echo "6️⃣  유튜브 검색 테스트 - 세 번째 요청 (드라이버 재사용 - 빠름!)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

keyword="웹 개발"
limit=4
encoded=$(urlencode "$keyword")
echo "   🔍 테스트: $keyword (limit: $limit)"
echo "   ⏱️  측정 시작..."
result=$(time curl -s "${BASE_URL}/search/list?keywords=${encoded}&limit=${limit}" 2>&1)
response=$(echo "$result" | tail -1)
print_result "$response"
echo ""

# 영어 키워드 테스트
echo "7️⃣  영어 키워드 테스트"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

keyword="machine learning"
limit=3
encoded=$(urlencode "$keyword")
echo "   🔍 테스트: $keyword (limit: $limit)"
echo "   ⏱️  측정 시작..."
result=$(time curl -s "${BASE_URL}/search/list?keywords=${encoded}&limit=${limit}" 2>&1)
response=$(echo "$result" | tail -1)
print_result "$response"
echo ""

# 한글 + 영어 혼합 테스트
echo "8️⃣  한글+영어 혼합 키워드 테스트"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

keyword="React 강의"
limit=3
encoded=$(urlencode "$keyword")
echo "   🔍 테스트: $keyword (인코딩: $encoded)"
echo "   ⏱️  측정 시작..."
result=$(time curl -s "${BASE_URL}/search/list?keywords=${encoded}&limit=${limit}" 2>&1)
response=$(echo "$result" | tail -1)
print_result "$response"
echo ""

# Shorts 검색 테스트
echo "9️⃣  Shorts 키워드 테스트"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

keyword="요리 레시피"
limit=5
encoded=$(urlencode "$keyword")
echo "   🔍 테스트: $keyword (limit: $limit)"
echo "   ⏱️  측정 시간..."
result=$(time curl -s "${BASE_URL}/search/list?keywords=${encoded}&limit=${limit}" 2>&1)
response=$(echo "$result" | tail -1)
print_result "$response"
echo ""

# 최종 통계
echo "🔟  최종 통계 (드라이버 풀 사용 현황)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s "${BASE_URL}/stats" | jq '.driver_pool_stats'
echo ""

echo "=========================================="
echo "✅ 테스트 완료"
echo "=========================================="
echo ""
echo "💡 팁:"
echo "   - 첫 Selenium 요청은 5-10초 소요 (드라이버 생성)"
echo "   - 이후 요청은 더 빠른 응답 (드라이버 재사용)"
echo "   - 100개 요청마다 드라이버 자동 재시작"
echo "   - /stats 엔드포인트에서 드라이버 풀 통계 확인 가능"
echo ""
echo "📌 다른 테스트:"
echo "   - bash test_simple.sh     # 빠른 테스트"
echo "   - bash test_error.sh       # 에러 처리 테스트"
echo ""

