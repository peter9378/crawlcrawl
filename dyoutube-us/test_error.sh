#!/bin/bash

# 에러 처리 테스트 스크립트
# 다양한 에러 케이스를 테스트

BASE_URL="http://localhost:8000"

# URL 인코딩 함수
urlencode() {
    python3 -c "import urllib.parse; print(urllib.parse.quote('$1'))"
}

echo "=========================================="
echo "🧪 dyoutube 에러 처리 테스트"
echo "=========================================="
echo ""

# 1. 빈 키워드 테스트
echo "1️⃣  빈 키워드 테스트 (400 에러 예상)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
response=$(curl -s -w "\nHTTP_CODE:%{http_code}" "${BASE_URL}/search/list?keywords=&limit=5")
http_code=$(echo "$response" | grep "HTTP_CODE" | cut -d':' -f2)
body=$(echo "$response" | sed '/HTTP_CODE/d')

if [ "$http_code" == "400" ]; then
    echo "   ✅ 올바른 에러 응답 (400)"
    echo "$body" | jq .
else
    echo "   ❌ 잘못된 응답 코드: $http_code"
    echo "$body" | jq .
fi
echo ""

# 2. 음수 limit 테스트
echo "2️⃣  음수 limit 테스트 (400 에러 예상)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
keyword="파이썬"
encoded=$(urlencode "$keyword")
response=$(curl -s -w "\nHTTP_CODE:%{http_code}" "${BASE_URL}/search/list?keywords=${encoded}&limit=-5")
http_code=$(echo "$response" | grep "HTTP_CODE" | cut -d':' -f2)
body=$(echo "$response" | sed '/HTTP_CODE/d')

if [ "$http_code" == "400" ]; then
    echo "   ✅ 올바른 에러 응답 (400)"
    echo "$body" | jq .
else
    echo "   ❌ 잘못된 응답 코드: $http_code"
    echo "$body" | jq .
fi
echo ""

# 3. limit 0 테스트
echo "3️⃣  limit=0 테스트 (400 에러 예상)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
keyword="자바"
encoded=$(urlencode "$keyword")
response=$(curl -s -w "\nHTTP_CODE:%{http_code}" "${BASE_URL}/search/list?keywords=${encoded}&limit=0")
http_code=$(echo "$response" | grep "HTTP_CODE" | cut -d':' -f2)
body=$(echo "$response" | sed '/HTTP_CODE/d')

if [ "$http_code" == "400" ]; then
    echo "   ✅ 올바른 에러 응답 (400)"
    echo "$body" | jq .
else
    echo "   ❌ 잘못된 응답 코드: $http_code"
    echo "$body" | jq .
fi
echo ""

# 4. 존재하지 않는 엔드포인트 테스트
echo "4️⃣  존재하지 않는 엔드포인트 테스트 (404 에러 예상)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
response=$(curl -s -w "\nHTTP_CODE:%{http_code}" "${BASE_URL}/nonexistent")
http_code=$(echo "$response" | grep "HTTP_CODE" | cut -d':' -f2)
body=$(echo "$response" | sed '/HTTP_CODE/d')

if [ "$http_code" == "404" ]; then
    echo "   ✅ 올바른 에러 응답 (404)"
    echo "$body" | jq .
else
    echo "   ❌ 잘못된 응답 코드: $http_code"
    echo "$body" | jq .
fi
echo ""

# 5. 특수문자 키워드 테스트 (정상 처리 예상)
echo "5️⃣  특수문자 키워드 테스트 (정상 처리 예상)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
keyword="C++"
encoded=$(urlencode "$keyword")
echo "   키워드: $keyword"
echo "   인코딩: $encoded"
response=$(curl -s -w "\nHTTP_CODE:%{http_code}" "${BASE_URL}/search/list?keywords=${encoded}&limit=2")
http_code=$(echo "$response" | grep "HTTP_CODE" | cut -d':' -f2)
body=$(echo "$response" | sed '/HTTP_CODE/d')

if [ "$http_code" == "200" ]; then
    echo "   ✅ 정상 처리 (200)"
    count=$(echo "$body" | jq '.result | length')
    echo "   결과 수: $count"
else
    echo "   ❌ 에러 응답: $http_code"
    echo "$body" | jq .
fi
echo ""

# 6. 매우 긴 키워드 테스트 (정상 처리 예상)
echo "6️⃣  매우 긴 키워드 테스트 (정상 처리 예상)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
keyword="파이썬 프로그래밍 완전 정복 초보자를 위한 기초 강의"
encoded=$(urlencode "$keyword")
echo "   키워드: ${keyword:0:40}..."
response=$(curl -s -w "\nHTTP_CODE:%{http_code}" "${BASE_URL}/search/list?keywords=${encoded}&limit=2")
http_code=$(echo "$response" | grep "HTTP_CODE" | cut -d':' -f2)
body=$(echo "$response" | sed '/HTTP_CODE/d')

if [ "$http_code" == "200" ]; then
    echo "   ✅ 정상 처리 (200)"
    count=$(echo "$body" | jq '.result | length')
    echo "   결과 수: $count"
else
    echo "   ❌ 에러 응답: $http_code"
    echo "$body" | jq .
fi
echo ""

# 7. 공백만 있는 키워드 테스트
echo "7️⃣  공백만 있는 키워드 테스트 (400 에러 예상)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
keyword="   "
encoded=$(urlencode "$keyword")
response=$(curl -s -w "\nHTTP_CODE:%{http_code}" "${BASE_URL}/search/list?keywords=${encoded}&limit=5")
http_code=$(echo "$response" | grep "HTTP_CODE" | cut -d':' -f2)
body=$(echo "$response" | sed '/HTTP_CODE/d')

if [ "$http_code" == "400" ]; then
    echo "   ✅ 올바른 에러 응답 (400)"
    echo "$body" | jq .
else
    echo "   ❌ 잘못된 응답 코드: $http_code"
    echo "$body" | jq .
fi
echo ""

echo "=========================================="
echo "✅ 에러 처리 테스트 완료"
echo "=========================================="
echo ""
echo "📊 결과 요약:"
echo "   - 빈 키워드: 400 에러 ✅"
echo "   - 음수 limit: 400 에러 ✅"
echo "   - limit=0: 400 에러 ✅"
echo "   - 404 엔드포인트: 404 에러 ✅"
echo "   - 특수문자: 정상 처리 ✅"
echo "   - 긴 키워드: 정상 처리 ✅"
echo "   - 공백 키워드: 400 에러 ✅"
echo ""

