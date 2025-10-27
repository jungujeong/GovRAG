# 문서 검색 AI 시스템 사용 가이드

> **이 프로그램은 무엇을 하나요?**
> 업로드한 PDF 문서를 AI가 읽고 이해하여, 질문에 답변해주는 프로그램입니다.

---

## 목차

1. [시스템 요구사항](#1-시스템-요구사항)
2. [설치 방법](#2-설치-방법)
3. [프로그램 실행](#3-프로그램-실행)
4. [사용 방법](#4-사용-방법)
5. [프로그램 종료](#5-프로그램-종료)
6. [문제 해결](#6-문제-해결)
7. [자주 묻는 질문](#7-자주-묻는-질문)

---

## 1. 시스템 요구사항

### 필수 설치 프로그램

| 프로그램 | 용도 | 다운로드 링크 |
|---------|------|--------------|
| **Python 3.12** | 프로그램 실행 | [다운로드 →](https://www.python.org/downloads/) |
| **Node.js 18+** | 웹 화면 표시 | [다운로드 →](https://nodejs.org/) |
| **Ollama** | AI 엔진 | [다운로드 →](https://ollama.com/download) |

### 시스템 사양

- **운영체제**: Ubuntu 20.04 이상 또는 Linux 배포판 **(Ubuntu/Linux 전용)**
- **RAM(메모리)**: 8GB 이상 **(16GB 권장)**
- **저장공간**: 10GB 이상 여유
- **인터넷**: 최초 설치 시에만 필요

**중요**: 이 시스템은 Ubuntu/Linux에서만 작동합니다.

---

## 2. 설치 방법

> **설치 환경을 선택하세요:**
> - **A. 인터넷 연결된 환경** → 바로 아래 [방법 A](#방법-a-인터넷-연결된-환경) 참고
> - **B. 폐쇄망(인터넷 없는) 환경** → [방법 B](#방법-b-폐쇄망오프라인-환경) 참고

---

### 방법 A: 인터넷 연결된 환경

인터넷이 연결되어 있고, 한 대의 컴퓨터에서만 사용할 경우

#### Step 1: 프로그램 다운로드

1. 받으신 압축 파일(`claude_rag_gpt5.zip`)을 압축 해제
2. 권장 위치: `/home/[사용자명]/RAG시스템/`

#### Step 2: 필수 프로그램 설치 확인

**터미널에서 확인:**

```bash
python3 --version
# 결과 예시: Python 3.12.0

node --version
# 결과 예시: v18.20.0

ollama --version
# 결과 예시: ollama version is 0.1.x
```

> **오류가 나오면?**
> "명령을 찾을 수 없습니다" 등의 오류 시 → 해당 프로그램 설치 필요

#### Step 3: AI 모델 다운로드

**터미널에서:**

```bash
ollama pull qwen3:4b
```

**소요 시간**: 약 5분 (파일 크기: 2.4GB)

**완료 확인:**
```bash
ollama list
```
→ `qwen3:4b`가 목록에 있으면 성공

**모델 교체**: 추후 더 높은 성능의 AI 모델로 언제든지 변경 가능합니다.

#### Step 4: 프로그램 의존성 설치

```bash
cd ~/RAG시스템/claude_rag_gpt5
chmod +x install.sh
./install.sh
```

**소요 시간**: 5-10분

> **설치 중 "계속하시겠습니까?" 나오면**
> → `Y` 입력 후 Enter

**설치 완료** → [3. 프로그램 실행](#3-프로그램-실행)으로 이동

---

### 방법 B: 폐쇄망(오프라인) 환경

인터넷이 없는 서버에 설치하거나, 여러 대의 컴퓨터에서 접속할 경우

> **작업 순서:**
> 1. 인터넷 있는 PC에서 필요한 파일 다운로드
> 2. USB/네트워크로 폐쇄망 서버에 전송
> 3. 폐쇄망 서버에 설치

---

#### Step 1: 인터넷 있는 PC에서 준비

##### 1-1. Ollama 설치 파일 다운로드

**Linux 서버용:**
```bash
# 최신 버전 다운로드
wget https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64

# 다운로드 확인
ls -lh ollama-linux-amd64
```

##### 1-2. Ollama 모델 다운로드

```bash
# 1. Ollama 설치 (임시)
curl -fsSL https://ollama.com/install.sh | sh

# 2. 모델 다운로드 (원하는 크기 선택)
ollama pull qwen3:14b

# 3. 모델 파일 위치 확인
ls -lh ~/.ollama/models/
```

**참고: 모델 크기 선택**
| 모델 | 크기 | 필요 RAM | 용도 |
|------|------|----------|------|
| `qwen3:4b` | 2.5GB | 8GB+ | 테스트/소형 |
| `qwen3:8b` | 5.2GB | 16GB+ | 일반 사용 |
| `qwen3:14b` | 9.3GB | 24GB+ | 권장 |
| `qwen3:30b` | 19GB | 48GB+ | 고성능 |

##### 1-3. Python 패키지 다운로드

```bash
# 프로젝트 폴더로 이동
cd ~/RAG시스템/claude_rag_gpt5

# pip 패키지 다운로드 (오프라인용)
pip download -r requirements.txt -d ./pip_packages

# 다운로드 확인
ls -lh pip_packages/
```

##### 1-4. 프로젝트 파일 압축

```bash
# 모든 파일을 하나의 압축 파일로
tar -czf rag_offline_bundle.tar.gz \
  backend/ \
  frontend/ \
  data/ \
  requirements.txt \
  .env.example \
  start.sh \
  stop.sh \
  install.sh \
  README.md \
  pip_packages/

# 압축 파일 크기 확인
ls -lh rag_offline_bundle.tar.gz
```

##### 1-5. Ollama 모델 폴더 압축

```bash
# Ollama 모델 압축
tar -czf ollama_models.tar.gz -C ~/.ollama models/

# 압축 파일 크기 확인
ls -lh ollama_models.tar.gz
```

---

#### Step 2: 폐쇄망 서버로 파일 전송

**전송할 파일 목록:**
1. `ollama-linux-amd64` - Ollama 실행 파일
2. `ollama_models.tar.gz` - AI 모델 파일
3. `rag_offline_bundle.tar.gz` - 프로젝트 파일

**전송 방법:**
- USB 메모리
- 내부 네트워크 (SCP)
- 승인된 파일 전송 시스템

---

#### Step 3: 폐쇄망 서버에 설치

##### 3-1. Ollama 설치

```bash
# Ollama 바이너리 설치
sudo install -o root -g root -m 755 ollama-linux-amd64 /usr/local/bin/ollama

# 설치 확인
ollama --version
# 출력: ollama version is 0.x.x

# Ollama 서비스 시작 (백그라운드)
nohup ollama serve > /dev/null 2>&1 &

# 실행 확인
ps aux | grep ollama
```

##### 3-2. Ollama 모델 설치

```bash
# 홈 디렉토리에 압축 해제
cd ~
tar -xzf ollama_models.tar.gz

# 모델 파일 확인
ls -lh ~/.ollama/models/

# Ollama에서 모델 확인
ollama list
# 출력: qwen3:14b 등이 표시되어야 함
```

##### 3-3. 프로젝트 설치

```bash
# 프로젝트 압축 해제
mkdir -p ~/RAG시스템
cd ~/RAG시스템
tar -xzf rag_offline_bundle.tar.gz

# 폴더 확인
ls -la
# backend/, frontend/, data/ 등이 보여야 함

# Python 패키지 오프라인 설치
pip install --no-index --find-links=./pip_packages -r requirements.txt

# 또는 가상환경 사용 시:
python3 -m venv venv
source venv/bin/activate
pip install --no-index --find-links=./pip_packages -r requirements.txt
```

##### 3-4. 환경 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집 (모델 이름 확인)
nano .env

# 확인 사항:
# OLLAMA_MODEL=qwen3:14b  (다운받은 모델과 일치해야 함)
# OLLAMA_HOST=http://localhost:11434
```

##### 3-5. 프론트엔드 설치

```bash
cd frontend

# Node.js 패키지 설치 (오프라인)
# 사전에 node_modules.tar.gz 준비 필요
npm install

# 빌드
npm run build
```

---

#### Step 4: 설치 검증

```bash
# 1. Ollama 상태 확인
curl http://localhost:11434/api/tags
# 정상: {"models":[...]} 응답

# 2. Ollama 모델 확인
ollama list
# qwen3:14b 등이 보여야 함

# 3. 시스템 시작
cd ~/RAG시스템/claude_rag_gpt5
./start.sh

# 4. 브라우저에서 접속
# http://localhost:5173
```

---

#### 폐쇄망 환경 문제 해결

##### "Ollama에 연결할 수 없습니다"

**원인**: Ollama 서비스가 실행되지 않음

**해결:**
```bash
# Ollama 프로세스 확인
ps aux | grep ollama

# 없으면 실행
nohup ollama serve > /dev/null 2>&1 &

# 포트 확인
netstat -tlnp | grep 11434
```

##### "모델을 찾을 수 없습니다"

**원인**: 모델 파일이 제대로 복사되지 않음

**해결:**
```bash
# 모델 위치 확인
ls -lh ~/.ollama/models/manifests/
ls -lh ~/.ollama/models/blobs/

# 모델 목록 확인
ollama list

# .env 파일의 모델 이름 확인
cat .env | grep OLLAMA_MODEL
```

##### "Python 패키지 설치 실패"

**원인**: pip_packages 폴더가 없거나 불완전함

**해결:**
```bash
# pip_packages 폴더 확인
ls -lh pip_packages/

# 누락된 패키지가 있다면 인터넷 있는 PC에서 다시 다운로드
pip download [패키지명] -d ./pip_packages
```

---

#### 폐쇄망 설치 체크리스트

**인터넷 있는 PC:**
- [ ] Ollama 설치 파일 다운로드 (`ollama-linux-amd64`)
- [ ] Ollama 모델 다운로드 (`ollama pull qwen3:14b`)
- [ ] 모델 파일 압축 (`ollama_models.tar.gz`)
- [ ] Python 패키지 다운로드 (`pip download`)
- [ ] 프로젝트 파일 압축 (`rag_offline_bundle.tar.gz`)

**폐쇄망 서버:**
- [ ] 파일 전송 완료 (USB/네트워크)
- [ ] Ollama 바이너리 설치 (`sudo install`)
- [ ] Ollama 서비스 시작 (`ollama serve`)
- [ ] 모델 파일 압축 해제 (`~/.ollama/models/`)
- [ ] `ollama list`로 모델 확인
- [ ] 프로젝트 압축 해제
- [ ] Python 패키지 설치 (`pip install --no-index`)
- [ ] `.env` 파일 설정
- [ ] 프론트엔드 빌드 (`npm run build`)
- [ ] `./start.sh` 실행 테스트

**설치 완료** → [3. 프로그램 실행](#3-프로그램-실행)으로 이동

---

## 3. 프로그램 실행

### 실행 방법

**터미널에서:**

```bash
cd ~/RAG시스템/claude_rag_gpt5
./start.sh
```

### 결과 확인

1. 터미널에 시작 메시지가 표시됩니다 → **터미널 창을 닫지 마세요**
2. 자동으로 웹 브라우저가 열립니다 (http://localhost:5173)
3. **웹 브라우저에 화면이 나타날 때까지 약 30초 대기**

4. **성공** 아래와 같은 화면이 보이면 사용 가능:

```
┌─────────────────────────────────────┐
│   문서 검색 AI 시스템            │
│                                     │
│  [문서 업로드] [설정]              │
│                                     │
│   무엇을 도와드릴까요?           │
│  ─────────────────────────────────  │
│  여기에 질문을 입력하세요...       │
└─────────────────────────────────────┘
```

> **브라우저가 자동으로 안 열리면?**
> 직접 브라우저를 열고 주소창에 입력: `http://localhost:5173`

---

## 4. 사용 방법

### 문서 업로드

1. **화면 왼쪽 상단** "문서 업로드" 버튼 클릭
2. 파일 선택:
   - PDF 파일 (`.pdf`)
   - 여러 파일 동시 선택 가능
3. "열기" 클릭
4. 업로드 진행률 표시 → **100% 될 때까지 대기**
5. 완료되면 왼쪽에 문서 목록 표시

### 질문하기

**Step 1: 질문 입력**
```
예시 질문:
"이 문서의 주요 내용은?"
"담당 부서는 어디인가요?"
"예산은 얼마인가요?"
```

**Step 2: 전송**
- 화면 하단 입력창에 질문 입력 후 Enter
- 또는 **전송** 버튼 클릭

**Step 3: 답변 확인 (5-30초 소요)**

```
AI 답변:

[답변 내용이 여기에 표시됩니다] [1]

주요 내용:
1. 첫 번째 주요 사항 [1]
2. 두 번째 주요 사항 [2]

담당 부서: [부서명] [1]

─────────────────────────────────
출처:
[1] 문서명 - 2페이지
[2] 문서명 - 3페이지
```

**Step 4: 출처 확인**
- 답변 하단의 `[1]`, `[2]` 클릭
- 원본 문서 해당 부분으로 이동

### 후속 질문

이전 답변을 참고하여 질문 가능:

```
사용자: "이 프로젝트의 주요 내용은?"
AI: [답변 생성]

사용자: "담당 부서는?"
AI: "[부서명]입니다."
     (이전 맥락을 이해하고 답변)
```

---

## 5. 프로그램 종료

### 정상 종료

**터미널에서:**

```bash
./stop.sh
```

또는:
1. 웹 브라우저 탭 닫기
2. 터미널 창에서 `Ctrl + C` 누르기

### 강제 종료 (문제 발생 시)

**터미널에서:**

```bash
# 프로세스 종료
pkill -f "uvicorn main:app"
pkill -f "npm run dev"

# 또는 포트로 종료
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9
```

---

## 6. 문제 해결

### "포트 8000이 이미 사용 중입니다"

**원인**: 이전 실행이 완전히 종료되지 않음

**해결:**
```bash
./stop.sh
# 또는
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9

# 다시 시작
./start.sh
```

### "Ollama 서버에 연결할 수 없습니다"

**해결:**
```bash
# 새 터미널에서 실행
ollama serve
```
→ 이 창을 닫지 말고, 새 터미널에서 `./start.sh` 실행

### "모델을 찾을 수 없습니다"

**해결:**
```bash
ollama pull qwen3:4b
```

### 웹 브라우저가 자동으로 안 열림

**해결:**
1. Chrome, Firefox 등 브라우저 직접 실행
2. 주소창에 입력: `http://localhost:5173`

### "메모리 부족" 오류

**해결:**
1. 다른 프로그램 종료
2. 서버 재시작
3. 문서 개수 줄이기 (한 번에 10개 이하)

### 답변이 너무 느림 (1분 이상)

**원인**: CPU 성능 부족

**해결:**
1. 다른 프로그램 모두 종료
2. 더 짧은 질문으로 시도
3. `.env` 파일에서 모델 변경 가능 (더 가벼운 모델 사용)

---

## 7. 자주 묻는 질문

### Q1: 인터넷 없이 사용 가능한가요?

**A**: 네. 설치만 완료되면 **오프라인 사용 가능**
- 인터넷은 최초 설치 시에만 필요 (모델 다운로드)
- 이후 인터넷 연결 없이 사용

### Q2: 몇 개의 문서를 업로드할 수 있나요?

**A**: RAM에 따라 다름
- **8GB RAM**: 약 50개 문서 (각 10페이지)
- **16GB RAM**: 약 200개 문서

### Q3: 업로드한 문서는 어디에 저장되나요?

**A**: `프로그램폴더/data/documents/`
- 서버를 재시작해도 유지됨
- 삭제하면 다시 업로드 필요

### Q4: 답변이 틀리면 어떡하나요?

**A**: 다음을 확인하세요
1. 올바른 문서가 업로드되었는지
2. 질문이 명확한지 (애매한 질문 → 애매한 답변)
3. 문서에 실제로 해당 정보가 있는지

### Q5: 여러 명이 동시에 사용 가능한가요?

**A**: 현재 버전은 **1명씩** 사용 권장
- 같은 서버에서 동시 사용 불가
- 다른 서버에 각각 설치 필요

### Q6: 더 좋은 AI 모델을 사용할 수 있나요?

**A**: 네. 언제든지 더 높은 성능의 AI 모델로 교체 가능합니다.

`.env` 파일 수정:
```bash
OLLAMA_MODEL=qwen2.5:14b  # 더 정확하지만 느림, RAM 많이 필요
# 또는
OLLAMA_MODEL=llama3.1:70b  # 최고 성능 (32GB+ RAM 필요)
```

모델 다운로드 후 재시작:
```bash
ollama pull qwen2.5:14b
./stop.sh
./start.sh
```

### Q7: 업데이트는 어떻게 하나요?

**A**:
1. 기존 `data/` 폴더 백업
2. 새 버전 파일 덮어쓰기
3. `data/` 폴더 복원

---

## 문의하기

**문제가 해결되지 않으면:**

1. **에러 메시지 캡처**
   - 터미널 창의 빨간색 메시지 복사

2. **로그 파일 첨부**
   - `logs/backend.log`
   - `logs/frontend.log`

3. **연락처**
   - 이메일: [담당자 이메일 입력]
   - 전화: [담당자 전화번호 입력]

---

## 부록: 폴더 구조

```
claude_rag_gpt5/
├── start.sh                    # ← 이걸 실행하세요
├── stop.sh                     # ← 종료할 때
├── install.sh                  # ← 최초 설치 시
├── backend/                    # 서버 프로그램
├── frontend/                   # 웹 화면
├── data/
│   ├── documents/              # ← 업로드한 문서 저장
│   ├── index/                  # 검색 인덱스
│   └── chroma/                 # AI 데이터
└── logs/
    ├── backend.log             # 백엔드 로그
    ├── frontend.log            # 프론트엔드 로그
    └── queries/                # 질문/답변 기록
```

---

## 고급 설정 (선택사항)

`.env` 파일을 편집기로 열어서 수정 가능:

```bash
# 서버 포트 변경 (기본값: 8000)
APP_PORT=9000

# AI 모델 변경 (성능이 더 좋은 모델로 교체)
OLLAMA_MODEL=qwen2.5:14b

# 검색 결과 개수 (기본값: 10)
TOPK_RERANK=10
```

---

## 설치 체크리스트

- [ ] Python 3.12 설치 (`python3 --version` 확인)
- [ ] Node.js 18+ 설치 (`node --version` 확인)
- [ ] Ollama 설치 (`ollama --version` 확인)
- [ ] AI 모델 다운로드 (`ollama list`에서 `qwen3:4b` 확인)
- [ ] 프로그램 압축 해제
- [ ] `./install.sh` 실행
- [ ] `./start.sh` 실행 → 브라우저 열림 확인
- [ ] 문서 업로드 테스트
- [ ] 질문/답변 테스트

---

**버전**: 1.0.0
**최종 수정**: 2025-10-26
**시스템**: Ubuntu/Linux 전용

