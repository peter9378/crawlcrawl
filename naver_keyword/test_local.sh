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
        echo "$response" | jq -r '.result[] | "      \(.rank). \(.keyword)"' | head -5
        if [ "$count" -gt 5 ]; then
            echo "      ... (총 $count 개)"
        fi
    else
        echo "   ⚠️  결과 없음"
    fi
}

echo "=========================================="
echo "🧪 로컬 서버 테스트"
echo "=========================================="
echo ""

# 헬스체크
echo "1️⃣  헬스체크 테스트..."
curl -s "${BASE_URL}/health" | jq .
echo ""

# 통계
echo "2️⃣  초기 통계 확인..."
curl -s "${BASE_URL}/stats" | jq .
echo ""

# 연관검색어 테스트
echo "3️⃣  연관검색어 테스트 (Selenium 드라이버 풀 사용)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

keyword="제일기획"
encoded=$(urlencode "$keyword")
echo "   🔍 테스트: $keyword"
echo "   ⏱️  측정 시작..."
result=$(time curl -s "${BASE_URL}/search/naver_related?keywords=${encoded}" 2>&1)
response=$(echo "$result" | tail -1)
print_result "$response"
echo ""

# 인기주제 테스트
echo "4️⃣  인기주제 테스트 (Selenium 드라이버 풀 사용)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

keyword="삼성전자"
encoded=$(urlencode "$keyword")
echo "   🔍 테스트: $keyword"
echo "   ⏱️  측정 시작..."
result=$(time curl -s "${BASE_URL}/search/naver_popular?keywords=${encoded}" 2>&1)
response=$(echo "$result" | tail -1)
print_result "$response"
echo ""

# 함께찾은 키워드 테스트
echo "5️⃣  함께찾은 키워드 테스트 (Selenium 드라이버 풀 사용)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "   🔥 첫 번째 요청 (드라이버 생성 - 느림)"
keyword="현대자동차"
encoded=$(urlencode "$keyword")
echo "   🔍 테스트: $keyword"
echo "   ⏱️  측정 시작..."
result=$(time curl -s "${BASE_URL}/search/naver_together?keywords=${encoded}" 2>&1)
response=$(echo "$result" | tail -1)
print_result "$response"
echo ""

echo "   ⚡ 두 번째 요청 (드라이버 재사용 - 빠름!)"
keyword="LG전자"
encoded=$(urlencode "$keyword")
echo "   🔍 테스트: $keyword"
echo "   ⏱️  측정 시작..."
result=$(time curl -s "${BASE_URL}/search/naver_together?keywords=${encoded}" 2>&1)
response=$(echo "$result" | tail -1)
print_result "$response"
echo ""

echo "   ⚡ 세 번째 요청 (드라이버 재사용 - 빠름!)"
keyword="SK하이닉스"
encoded=$(urlencode "$keyword")
echo "   🔍 테스트: $keyword"
echo "   ⏱️  측정 시작..."
result=$(time curl -s "${BASE_URL}/search/naver_together?keywords=${encoded}" 2>&1)
response=$(echo "$result" | tail -1)
print_result "$response"
echo ""

# 한글 테스트
echo "   🇰🇷 한글 키워드 테스트 (URL 인코딩)"
keyword="인공지능 기술"
encoded=$(urlencode "$keyword")
echo "   🔍 테스트: $keyword (인코딩: $encoded)"
echo "   ⏱️  측정 시작..."
result=$(time curl -s "${BASE_URL}/search/naver_together?keywords=${encoded}" 2>&1)
response=$(echo "$result" | tail -1)
print_result "$response"
echo ""

# 최종 통계
echo "6️⃣  최종 통계 (드라이버 풀 사용 현황)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s "${BASE_URL}/stats" | jq '.driver_pool_stats'
echo ""

echo "=========================================="
echo "✅ 테스트 완료"
echo "=========================================="
echo ""
echo "💡 팁:"
echo "   - 첫 Selenium 요청은 7-10초 소요 (드라이버 생성)"
echo "   - 이후 요청은 2-3초로 빨라짐 (드라이버 재사용)"
echo "   - 100개 요청마다 드라이버 자동 재시작"
echo ""

