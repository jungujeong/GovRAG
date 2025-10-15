#!/bin/bash

# macOS 파일 시스템 충돌로 생성된 중복 디렉토리 정리 스크립트
#
# 문제: Vite/npm이 node_modules를 동시에 접근할 때 macOS가 자동으로
#       "dirname 2", "dirname 3" 등의 중복 디렉토리 생성
# 해결: 이 스크립트로 주기적 정리

echo "🧹 Cleaning up duplicate node_modules directories..."

# 중복 파일 검색
DUPLICATES=$(find node_modules -name "* [0-9]" -o -name "* [0-9][0-9]" 2>/dev/null)
COUNT=$(echo "$DUPLICATES" | grep -c "^" 2>/dev/null)

if [ "$COUNT" -gt 0 ]; then
    echo "Found $COUNT duplicate directories:"
    echo "$DUPLICATES" | head -10
    if [ "$COUNT" -gt 10 ]; then
        echo "... and $((COUNT - 10)) more"
    fi

    # 삭제
    find node_modules -name "* [0-9]" -type d -exec rm -rf {} + 2>/dev/null || true
    find node_modules -name "* [0-9][0-9]" -type d -exec rm -rf {} + 2>/dev/null || true

    echo "✅ Cleanup complete!"
else
    echo "✅ No duplicates found. node_modules is clean!"
fi
