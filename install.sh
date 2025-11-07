#!/bin/bash
# RAG 시스템 설치 스크립트 (Mac/Linux)

set -e  # 에러 발생 시 중단

echo "========================================"
echo "  📦 문서 검색 AI 시스템 설치"
echo "========================================"
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Python 확인
echo "[1/5] Python 확인 중..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3가 설치되지 않았습니다.${NC}"
    echo "   macOS: brew install python@3.12"
    echo "   Ubuntu: sudo apt install python3.12"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✓ Python $PYTHON_VERSION 설치됨${NC}"
echo ""

# Node.js 확인
echo "[2/5] Node.js 확인 중..."
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js가 설치되지 않았습니다.${NC}"
    echo "   macOS: brew install node@18"
    echo "   Ubuntu: curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -"
    echo "           sudo apt-get install -y nodejs"
    exit 1
fi
NODE_VERSION=$(node --version)
echo -e "${GREEN}✓ Node.js $NODE_VERSION 설치됨${NC}"
echo ""

# Ollama 확인
echo "[3/5] Ollama 확인 중..."
if ! command -v ollama &> /dev/null; then
    echo -e "${RED}❌ Ollama가 설치되지 않았습니다.${NC}"
    echo "   macOS: brew install ollama"
    echo "   Linux: curl https://ollama.ai/install.sh | sh"
    exit 1
fi
echo -e "${GREEN}✓ Ollama 설치됨${NC}"
echo ""

# Ollama 모델 확인
echo "AI 모델 확인 중..."
if ! ollama list | grep -q "qwen3:4b"; then
    echo -e "${YELLOW}⚠️  qwen3:4b 모델이 설치되지 않았습니다.${NC}"
    echo "   다운로드 중... (약 2.4GB, 5분 소요)"
    echo ""
    ollama pull qwen3:4b
fi
echo -e "${GREEN}✓ qwen3:4b 모델 확인됨${NC}"
echo ""

# .env 파일 생성
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo ".env 파일 생성 중..."
        cp .env.example .env
        echo -e "${GREEN}✓ .env 파일 생성됨${NC}"
    fi
fi
echo ""

# 백엔드 의존성 설치
echo "[4/5] 백엔드 의존성 설치 중..."
echo "   (약 5분 소요)"
cd backend
if [ -f "requirements.txt" ]; then
    python3 -m pip install --upgrade pip
    pip3 install -r requirements.txt
fi
cd ..
echo -e "${GREEN}✓ 백엔드 패키지 설치 완료${NC}"
echo ""

# 프론트엔드 의존성 설치
echo "[5/5] 프론트엔드 의존성 설치 중..."
echo "   (약 3분 소요)"
cd frontend
if [ -f "package.json" ]; then
    npm install
fi
cd ..
echo -e "${GREEN}✓ 프론트엔드 패키지 설치 완료${NC}"
echo ""

# 필요한 폴더 생성
echo "데이터 폴더 생성 중..."
mkdir -p data/documents
mkdir -p data/index
mkdir -p data/chroma
mkdir -p logs
echo -e "${GREEN}✓ 폴더 생성 완료${NC}"
echo ""

# 실행 권한 부여
echo "실행 권한 설정 중..."
chmod +x start.sh
chmod +x stop.sh
chmod +x install.sh
echo -e "${GREEN}✓ 실행 권한 설정 완료${NC}"
echo ""

echo "========================================"
echo "  ✅ 설치 완료!"
echo "========================================"
echo ""
echo "다음 단계:"
echo "  1. ./start.sh 실행으로 프로그램 시작"
echo "  2. 웹 브라우저에서 http://localhost:5173 접속"
echo "  3. 문서 업로드 후 질문하기"
echo ""
echo "문제가 있으면 README.md의 '문제 해결' 섹션을 참고하세요."
echo ""
