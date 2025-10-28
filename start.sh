#!/bin/bash

# RAG 시스템 시작 스크립트

# Lockfile to prevent multiple instances
LOCKFILE="/tmp/rag_chatbot.lock"

if [ -f "$LOCKFILE" ]; then
    echo "❌ 시스템이 이미 실행 중입니다."
    echo "   lockfile: $LOCKFILE"
    echo "   강제 재시작하려면: rm $LOCKFILE && ./stop.sh && ./start.sh"
    exit 1
fi

# Create lockfile
touch "$LOCKFILE"

# Cleanup function
cleanup() {
    rm -f "$LOCKFILE"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
}

# Set trap for cleanup on exit
trap cleanup EXIT INT TERM

echo "🚀 RAG Chatbot 시스템을 시작합니다..."
echo ""

# 포트 확인
if lsof -tiTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "❌ 오류: 포트 8000이 이미 사용 중입니다."
    echo "   실행 중인 프로세스를 종료하려면: ./stop.sh"
    exit 1
fi

if lsof -tiTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "❌ 오류: 포트 5173이 이미 사용 중입니다."
    echo "   실행 중인 프로세스를 종료하려면: ./stop.sh"
    exit 1
fi

# .env 파일 확인
if [ ! -f .env ]; then
    echo "⚙️  .env 파일이 없습니다. .env.example에서 복사합니다..."
    cp .env.example .env
fi

# Python 버전 확인
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python 버전: $PYTHON_VERSION"

# Ollama 확인 및 자동 시작
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama가 실행 중이 아닙니다. 자동으로 시작합니다..."

    # Ollama가 설치되어 있는지 확인
    if ! command -v ollama &> /dev/null; then
        echo "❌ Ollama가 설치되어 있지 않습니다."
        echo "   설치 방법: https://ollama.com/download"
        echo "   또는 README.md의 설치 방법을 참고하세요."
        exit 1
    fi

    # Ollama 서비스 시작
    nohup ollama serve > logs/ollama.log 2>&1 &
    OLLAMA_PID=$!
    echo "   Ollama PID: $OLLAMA_PID"

    # Ollama가 시작될 때까지 대기 (최대 10초)
    echo "   Ollama 초기화 중..."
    for i in {1..10}; do
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo "   ✓ Ollama 준비 완료"
            break
        fi
        sleep 1
    done

    # 최종 확인
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "   ❌ Ollama 시작 실패. logs/ollama.log를 확인하세요."
        exit 1
    fi
else
    echo "✓ Ollama가 실행 중입니다."
fi

# 로그 디렉토리 생성
mkdir -p logs

# 백엔드 시작
echo ""
echo "📦 백엔드 서버를 시작합니다..."
(cd backend && PYTHONPATH=. uvicorn main:app --port 8000) > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "   PID: $BACKEND_PID"

# 백엔드가 시작될 때까지 대기
echo "   백엔드 초기화 중..."
sleep 5

# 백엔드 health check
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "   ✓ 백엔드 준비 완료"
else
    echo "   ⚠️  백엔드가 아직 준비 중입니다..."
fi

# 프론트엔드 시작
echo ""
echo "🎨 프론트엔드 서버를 시작합니다..."
# Node 18 경로 설정 및 프론트엔드 직접 시작
(cd frontend && export PATH="$HOME/.nvm/versions/node/v18.20.8/bin:$PATH" && nohup npm run dev > ../logs/frontend.log 2>&1) &
FRONTEND_PID=$!
echo "   PID: $FRONTEND_PID"

# PID 저장 (atomic write to prevent macOS file conflicts)
echo "$BACKEND_PID" > .backend.pid.tmp && mv -f .backend.pid.tmp .backend.pid
echo "$FRONTEND_PID" > .frontend.pid.tmp && mv -f .frontend.pid.tmp .frontend.pid

echo ""
echo "✅ 서버가 시작되었습니다!"
echo ""
echo "🌐 접속 주소:"
echo "   프론트엔드: http://localhost:5173"
echo "   백엔드:     http://localhost:8000"
echo "   API 문서:   http://localhost:8000/docs"
echo ""
echo "📝 로그 파일:"
echo "   백엔드:     logs/backend.log"
echo "   프론트엔드: logs/frontend.log"
echo ""
echo "📊 로그 실시간 보기:"
echo "   tail -f logs/backend.log"
echo "   tail -f logs/frontend.log"
echo ""
echo "🛑 중지하려면: ./stop.sh"
echo ""

# 종료 시 프로세스 정리
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT