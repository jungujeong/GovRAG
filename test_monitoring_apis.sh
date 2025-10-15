#!/bin/bash

# RAG 시스템 모니터링 API 테스트 스크립트
# 사용법: ./test_monitoring_apis.sh

API_BASE="http://localhost:8000"

echo "========================================="
echo "RAG 시스템 모니터링 API 테스트"
echo "========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test function
test_api() {
    local name="$1"
    local url="$2"

    echo -e "${YELLOW}테스트:${NC} $name"
    echo "URL: $url"

    response=$(curl -s -w "\n%{http_code}" "$url")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}✓ 성공 (HTTP $http_code)${NC}"
        echo "$body" | python3 -m json.tool 2>/dev/null | head -30
    else
        echo -e "${RED}✗ 실패 (HTTP $http_code)${NC}"
        echo "$body"
    fi
    echo ""
    echo "---"
    echo ""
}

# 1. Health Check
test_api "헬스 체크" "$API_BASE/api/health"

# 2. Statistics
test_api "로그 통계" "$API_BASE/api/admin/logs/statistics"

# 3. Recent Logs
test_api "최근 로그 (5개)" "$API_BASE/api/admin/logs/recent?limit=5"

# 4. Search Logs
test_api "로그 검색" "$API_BASE/api/admin/logs/search?limit=3"

# 5. Quality Issues
test_api "품질 이슈" "$API_BASE/api/admin/logs/quality-issues"

# 6. Performance Issues
test_api "성능 이슈" "$API_BASE/api/admin/logs/performance-issues"

# 7. Trends
test_api "트렌드 분석 (7일)" "$API_BASE/api/admin/logs/trends?days=7"

# 8. System Metrics
test_api "시스템 메트릭" "$API_BASE/api/admin/metrics"

# 9. Config
test_api "시스템 설정" "$API_BASE/api/admin/config"

echo "========================================="
echo "HTML 리포트 생성 테스트"
echo "========================================="
echo ""

echo "리포트 URL: $API_BASE/api/admin/logs/report"
echo "브라우저에서 확인: open $API_BASE/api/admin/logs/report"
echo ""

# 10. Generate Report (save to file)
curl -s "$API_BASE/api/admin/logs/report" > test_report.html
if [ -f "test_report.html" ]; then
    size=$(wc -c < test_report.html)
    if [ "$size" -gt 1000 ]; then
        echo -e "${GREEN}✓ HTML 리포트 생성 성공 (${size} bytes)${NC}"
        echo "파일: test_report.html"
        echo "열기: open test_report.html"
    else
        echo -e "${RED}✗ HTML 리포트 생성 실패 (크기가 너무 작음)${NC}"
    fi
else
    echo -e "${RED}✗ HTML 리포트 파일 생성 실패${NC}"
fi

echo ""
echo "========================================="
echo "테스트 완료!"
echo "========================================="
