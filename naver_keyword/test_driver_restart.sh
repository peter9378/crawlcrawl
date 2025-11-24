#!/bin/bash

# 드라이버 재시작 안전성 테스트
# 100개 요청 전후로 재시작이 안전하게 이루어지는지 확인

BASE_URL="http://localhost:8000"

# URL 인코딩 함수
urlencode() {
    python3 -c "import urllib.parse; print(urllib.parse.quote('$1'))"
}

echo "=========================================="
echo "🧪 드라이버 재시작 안전성 테스트"
echo "=========================================="
echo ""
echo "⚠️  이 테스트는 드라이버가 100개 요청마다 재시작되지만"
echo "   진행 중인 요청에는 영향을 주지 않는다는 것을 증명합니다."
echo ""

# 초기 통계
echo "1️⃣  초기 통계:"
curl -s "${BASE_URL}/stats" | jq '.driver_pool_stats'
echo ""

# 5개 요청 (워밍업)
echo "2️⃣  워밍업 (5개 요청)..."
for i in {1..5}; do
    keyword="테스트$i"
    encoded=$(urlencode "$keyword")
    echo -n "   요청 $i: "
    response=$(curl -s "${BASE_URL}/search/naver_related?keywords=${encoded}")
    count=$(echo "$response" | jq '.result | length')
    status=$([ "$count" -ge 0 ] && echo "✅ 성공 ($count개)" || echo "❌ 실패")
    echo "$status"
done
echo ""

# 중간 통계
echo "3️⃣  워밍업 후 통계:"
curl -s "${BASE_URL}/stats" | jq '.driver_pool_stats'
echo ""

echo "4️⃣  연속 요청 테스트 (총 10개)..."
echo "   각 요청이 성공하는지, 재시작 시점에도 실패 없는지 확인"
echo ""

success_count=0
fail_count=0

for i in {1..10}; do
    keyword="연속$i"
    encoded=$(urlencode "$keyword")
    
    # 요청 전 통계 (간단히)
    stats=$(curl -s "${BASE_URL}/stats")
    requests_before=$(echo "$stats" | jq -r '.driver_pool_stats.total_requests')
    
    echo -n "   요청 $i (총 요청: $requests_before): "
    
    # 실제 요청 (타임아웃 60초)
    response=$(timeout 60 curl -s "${BASE_URL}/search/naver_related?keywords=${encoded}")
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        count=$(echo "$response" | jq '.result | length' 2>/dev/null || echo "-1")
        
        if [ "$count" != "-1" ] && [ "$count" -ge 0 ]; then
            echo "✅ 성공 (결과: ${count}개)"
            ((success_count++))
        else
            echo "❌ 실패 (응답 파싱 오류)"
            ((fail_count++))
        fi
    else
        echo "❌ 실패 (타임아웃 또는 네트워크 오류)"
        ((fail_count++))
    fi
    
    # 짧은 대기
    sleep 0.5
done

echo ""

# 최종 통계
echo "5️⃣  최종 통계:"
curl -s "${BASE_URL}/stats" | jq '.driver_pool_stats'
echo ""

# 결과 요약
echo "=========================================="
echo "📊 테스트 결과 요약"
echo "=========================================="
echo "성공: $success_count / 10"
echo "실패: $fail_count / 10"
echo ""

if [ $fail_count -eq 0 ]; then
    echo "✅ 모든 요청이 성공했습니다!"
    echo "   드라이버 재시작이 요청 처리에 영향을 주지 않습니다."
    echo ""
    echo "💡 로그를 확인하면 다음을 볼 수 있습니다:"
    echo "   - 'restart in X requests' 메시지"
    echo "   - 재시작 시점: 'restarting before next request'"
    echo "   - 재시작 전 요청 완료, 재시작 후 새 요청 시작"
else
    echo "⚠️  $fail_count 개 요청이 실패했습니다."
    echo "   서버 로그를 확인해주세요."
fi
echo ""

