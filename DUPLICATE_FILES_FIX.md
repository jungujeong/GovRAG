# macOS 파일 시스템 충돌 문제 해결 (중복 파일 생성)

## 문제 상황

**증상**: 프로젝트 전체에 " 2", " 3", " 4" suffix가 붙은 중복 파일/디렉토리 대량 생성
- `frontend/node_modules`: 649개 중복 디렉토리
- `frontend/`: `package-lock 2.json`, `package-lock 3.json`
- 루트: `.backend 2.pid`, `.backend 3.pid`, `.backend 4.pid`, `.frontend 2.pid` 등

## 근본 원인

### 1. macOS Save Conflict
macOS는 여러 프로세스가 동시에 같은 파일/디렉토리를 쓰려고 할 때 자동으로 " 2", " 3" suffix를 붙여 저장합니다.

### 2. 중복 start.sh 실행
`start.sh`가 lockfile 없이 여러 번 실행되어:
```bash
echo "$BACKEND_PID" > .backend.pid    # 충돌 발생 → .backend 2.pid 생성
echo "$FRONTEND_PID" > .frontend.pid  # 충돌 발생 → .frontend 2.pid 생성
```

### 3. npm/Vite 동시 접근
- `npm install` 중 다른 프로세스가 node_modules 접근
- Vite가 package-lock.json 수정 시도
- Vite가 node_modules 감시 중 충돌

### 4. Vite 설정 문제
- `node_modules`를 watch 대상에 포함
- HMR(Hot Module Replacement) 중 파일 충돌

## 해결 방법

### Step 1: 모든 프로세스 종료
```bash
killall -9 node uvicorn
./stop.sh
```

### Step 2: 중복 파일 일괄 삭제
```bash
# 루트 디렉토리 PID 파일
rm -f ".backend 2.pid" ".backend 3.pid" ".backend 4.pid"
rm -f ".frontend 2.pid" ".frontend 3.pid" ".frontend 4.pid"

# frontend 디렉토리
cd frontend
rm -f "package-lock 2.json" "package-lock 3.json"
rm -f vite.config.js.timestamp-*.mjs

# node_modules 중복 디렉토리 (649개)
find node_modules -maxdepth 1 -name "* [0-9]" -type d -exec rm -rf {} + 2>/dev/null || true
```

### Step 3: node_modules 완전 재설치
```bash
cd frontend
rm -rf node_modules package-lock.json .vite
source ~/.nvm/nvm.sh
nvm use 18
npm cache clean --force
npm install
```

### Step 4: start.sh에 Lockfile 추가
```bash
#!/bin/bash

# Lockfile to prevent multiple instances
LOCKFILE="/tmp/rag_chatbot.lock"

if [ -f "$LOCKFILE" ]; then
    echo "❌ 시스템이 이미 실행 중입니다. (lockfile: $LOCKFILE)"
    echo "   강제 재시작하려면: rm $LOCKFILE && ./start.sh"
    exit 1
fi

# Create lockfile
touch "$LOCKFILE"

# Cleanup on exit
trap "rm -f $LOCKFILE" EXIT

# ... rest of start.sh
```

### Step 5: PID 파일 원자적 쓰기
```bash
# Before:
echo "$BACKEND_PID" > .backend.pid

# After (atomic write):
echo "$BACKEND_PID" > .backend.pid.tmp && mv -f .backend.pid.tmp .backend.pid
```

### Step 6: Vite 설정 최적화
```javascript
// vite.config.js
export default defineConfig({
  server: {
    watch: {
      ignored: [
        '**/node_modules/**',
        '**/.git/**',
        '**/dist/**',
        '**/.vite/**',
        '**/* [0-9]',           // Ignore macOS conflict duplicates
        '**/* [0-9][0-9]'
      ],
      usePolling: false,
      interval: 1000
    }
  },
  optimizeDeps: {
    exclude: ['node_modules/**/* [0-9]']
  }
})
```

### Step 7: 자동 정리 스크립트
```bash
# frontend/cleanup_duplicates.sh
#!/bin/bash
echo "🧹 Cleaning up duplicate node_modules directories..."
find node_modules -name "* [0-9]" -type d -exec rm -rf {} + 2>/dev/null || true
echo "✅ Cleanup complete!"
```

```json
// package.json
{
  "scripts": {
    "cleanup": "bash cleanup_duplicates.sh",
    "postinstall": "npm run cleanup"
  }
}
```

## 예방 조치

### 1. 중복 실행 방지
- 항상 `./stop.sh` 후 `./start.sh` 실행
- Lockfile로 중복 시작 차단

### 2. Vite 감시 범위 제한
- node_modules 감시 제외
- 중복 파일 패턴 감시 제외

### 3. 주기적 정리
```bash
# 매일 실행 (cron)
0 3 * * * cd /path/to/project && ./frontend/cleanup_duplicates.sh
```

### 4. Git Ignore
```gitignore
# .gitignore
**/node_modules/* [0-9]
**/node_modules/* [0-9][0-9]
**/*.pid
**/package-lock [0-9].json
```

## 검증

### 중복 파일 확인
```bash
# 루트
ls -la | grep -E "\..*[0-9]"

# Frontend
ls -la frontend/ | grep -E " [0-9]"

# node_modules (최대 깊이 1)
find frontend/node_modules -maxdepth 1 -name "* [0-9]" | wc -l
```

결과: 모두 0이어야 함

## 장기 해결책

### 1. Docker 사용 고려
파일 시스템 충돌을 격리

### 2. pnpm 사용 고려
Symlink 기반으로 node_modules 충돌 최소화

### 3. 프로세스 관리자 사용
- PM2
- systemd
- supervisord

## 참고

- macOS Save Conflict: https://support.apple.com/en-us/HT201730
- Vite watch options: https://vitejs.dev/config/server-options.html#server-watch
