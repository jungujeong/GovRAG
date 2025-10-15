# 긴급 복구 가이드

## 현재 상황

`frontend/node_modules`가 649개의 중복 디렉토리로 인해 완전히 손상되었습니다.
권한 문제와 파일 시스템 충돌로 인해 자동 복구가 불가능합니다.

## 즉시 수행해야 할 작업

### 1. Finder에서 수동 삭제 (가장 확실한 방법)

```bash
# Terminal에서:
open /Users/yummongi/Desktop/claude_rag_gpt5/frontend
```

Finder 창이 열리면:
1. `node_modules` 폴더를 **휴지통으로 드래그**
2. 휴지통 비우기 (Cmd+Shift+Delete)
3. 다시 Terminal로 돌아가기

### 2. 시스템 완전 정리

```bash
cd /Users/yummongi/Desktop/claude_rag_gpt5

# 1. 모든 프로세스 종료
killall -9 node uvicorn 2>/dev/null || true

# 2. Lockfile 제거
rm -f /tmp/rag_chatbot.lock

# 3. 중복 PID 파일 제거
rm -f ".backend 2.pid" ".backend 3.pid" ".backend 4.pid"
rm -f ".frontend 2.pid" ".frontend 3.pid" ".frontend 4.pid"

# 4. Frontend 중복 파일 제거
cd frontend
rm -f "package-lock 2.json" "package-lock 3.json"
rm -f vite.config.js.timestamp-*.mjs
```

### 3. 깨끗한 재설치

```bash
cd /Users/yummongi/Desktop/claude_rag_gpt5/frontend

# node_modules가 Finder에서 삭제되었는지 확인
ls -la | grep node_modules
# 결과: 아무것도 나오지 않아야 함

# .vite 캐시도 제거
rm -rf .vite

# 깨끗한 재설치
source ~/.nvm/nvm.sh
nvm use 18
npm cache clean --force
npm install
```

### 4. 시스템 시작

```bash
cd /Users/yummongi/Desktop/claude_rag_gpt5
./start.sh
```

## 만약 Finder 삭제도 실패한다면

### 방법 A: 프로젝트 재클론

```bash
cd /Users/yummongi/Desktop
mv claude_rag_gpt5 claude_rag_gpt5_backup

# Git에서 재클론
git clone <repository-url> claude_rag_gpt5
cd claude_rag_gpt5

# 백업에서 작업물 복사
cp -r claude_rag_gpt5_backup/backend/data/ backend/data/
cp -r claude_rag_gpt5_backup/data/ data/
cp claude_rag_gpt5_backup/.env .env

# 재설치
cd frontend
npm install

# 시작
cd ..
./start.sh
```

### 방법 B: 새 frontend 디렉토리 생성

```bash
cd /Users/yummongi/Desktop/claude_rag_gpt5

# 손상된 frontend 이동
mv frontend frontend_broken

# 새 frontend 생성
mkdir frontend
cd frontend

# package.json과 설정 파일 복사
cp ../frontend_broken/package.json .
cp ../frontend_broken/vite.config.js .
cp ../frontend_broken/postcss.config.js .
cp ../frontend_broken/tailwind.config.js .
cp ../frontend_broken/index.html .
cp ../frontend_broken/.nvmrc .
cp ../frontend_broken/.gitignore .

# src 디렉토리 복사
cp -r ../frontend_broken/src .

# 깨끗한 설치
source ~/.nvm/nvm.sh
nvm use 18
npm install

# 시작
cd ..
./start.sh
```

## 완료 후 검증

```bash
# 중복 파일 확인
find . -name "* [0-9]" 2>/dev/null | wc -l
# 결과: 0 (또는 매우 적은 수)

# node_modules 개수 확인
ls frontend/node_modules | wc -l
# 결과: 약 250-300 (정상)

# 시스템 상태 확인
curl http://localhost:8000/api/health
# 결과: {"status":"healthy",...}

curl http://localhost:5173
# 결과: HTML 응답
```

## 향후 예방

### 1. 절대 동시에 start.sh 실행 금지
- Lockfile이 추가되어 방지됨
- 에러 메시지: "시스템이 이미 실행 중입니다"

### 2. npm install 중 Vite 실행 금지
- 항상 `./stop.sh` 후 `npm install`

### 3. 정기 정리
```bash
# 매일 실행
cd /Users/yummongi/Desktop/claude_rag_gpt5/frontend
./cleanup_duplicates.sh
```

### 4. Git으로 추적
```bash
# 중복 파일이 커밋되지 않도록
git status | grep " [0-9]"
# 결과: 아무것도 나오지 않아야 함
```

## 근본 원인

1. **macOS Save Conflict**: 여러 프로세스가 동시에 같은 파일 쓰기 시도
2. **start.sh 중복 실행**: Lockfile 없어서 여러 번 실행됨
3. **Vite node_modules 감시**: 설정에서 제외되지 않음

## 적용된 해결책

### start.sh (수정 완료)
- ✅ Lockfile 추가 (`/tmp/rag_chatbot.lock`)
- ✅ PID 파일 원자적 쓰기
- ✅ Cleanup trap 추가

### vite.config.js (수정 완료)
- ✅ node_modules watch 제외
- ✅ 중복 파일 패턴 무시

### package.json (수정 완료)
- ✅ postinstall cleanup 추가

## 도움이 필요하면

1. 현재 상태 확인:
```bash
ls -la /Users/yummongi/Desktop/claude_rag_gpt5/frontend | grep -E "node_modules|package"
```

2. 프로세스 상태:
```bash
ps aux | grep -E "(node|uvicorn)" | grep -v grep
```

3. Lockfile 상태:
```bash
ls -la /tmp/rag_chatbot.lock
```
