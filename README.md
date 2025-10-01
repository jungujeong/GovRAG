# RAG Chatbot System (폐쇄망/오프라인)

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18-blue.svg)](https://reactjs.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

한국어 공문서(HWP/PDF) 처리에 최적화된 **Evidence-Only RAG 시스템**

완전 오프라인 환경에서 동작하며, 할루시네이션 방지 및 정확한 출처 추적을 보장합니다.

---

## 📋 목차

- [시작하기](#시작하기)
- [주요 기능](#주요-기능)
- [시스템 아키텍처](#시스템-아키텍처)
- [설치 및 실행](#설치-및-실행)
- [사용 방법](#사용-방법)
- [평가 및 테스트](#평가-및-테스트)
- [API 문서](#api-문서)
- [문제 해결](#문제-해결)
- [기여 및 라이선스](#기여-및-라이선스)

---

## 🚀 시작하기

### 빠른 시작 (Quick Start)

```bash
# 1. 프로젝트 구조 생성
make setup

# 2. 의존성 설치
make install

# 3. Ollama 모델 다운로드
ollama pull qwen3:4b

# 4. 문서 인덱싱 (data/documents/에 HWP/PDF 배치 후)
make index

# 5. 시스템 실행
make run
```

**실행 후 접근**:
- 프론트엔드: http://localhost:5173
- API 문서: http://localhost:8000/docs

---

## ✨ 주요 기능

### 핵심 기능
- ✅ **완전 오프라인**: Docker 없이 로컬 환경에서 동작 (Ollama 로컬 LLM)
- ✅ **한국어 문서 특화**: HWP/PDF 구조 보존 파싱 (조/항/호/표/각주)
- ✅ **하이브리드 검색**: Whoosh(BM25) + ChromaDB(Vector) + Jina Reranker
- ✅ **Evidence-Only 생성**: 할루시네이션 방지 및 후검증 (Jaccard, 정규식)
- ✅ **정확한 출처 추적**: 문서ID, 페이지, 문자 오프셋 포함
- ✅ **멀티턴 대화**: 세션 기반 컨텍스트 관리 및 대화 메모리
- ✅ **스트리밍 응답**: 실시간 답변 생성
- ✅ **8GB RAM 동작**: 메모리 효율적 설계

### 문서 처리
- **HWP**: hwplib(Java) + JPype1 브리지로 구조 보존 파싱
- **PDF**: PyMuPDF 우선, 텍스트 부족 시 Tesseract OCR 자동 폴백
- **정규화**: 날짜 ISO 변환, 숫자/금액 표준화, 법령 표기 통일
- **청킹**: 의미 단락 병합, 표/각주 분리 + 역링크

### 대화 메모리 (Conversation Memory)
시스템은 **4계층 메모리 구조**를 구현:
1. **Short-term**: 최근 10개 메시지
2. **Summary**: 대화 요약 (신뢰도 게이트)
3. **Entity**: 최근 엔터티 추출
4. **Document Scope**: 문서 범위 고정 (출처 일관성)

### 질의 처리 파이프라인
```
질의 입력 → 재작성(Anaphora 해소) → 문서 범위 해결 →
하이브리드 검색(BM25+Vector) → 리랭킹 → Evidence-Only 생성 →
후검증 → 출처 추적 → 포맷팅 → 응답
```

### 관측 가능성 (Observability)
- 질의 재작성 메타데이터: `metadata.rewrite.used_fallback`
- 대화 요약 추적: `metadata.memory.summary_updated`
- 문서 범위: `metadata.doc_scope.mode`
- 토픽 변경 감지: `metadata.doc_scope.topic_change_detected`
- 상세 로그: `backend/routers/chat.py`

---

## 🏗️ 시스템 아키텍처

### 기술 스택
- **Backend**: FastAPI + Uvicorn (Python 3.12+)
- **Frontend**: React 18 + Vite + Tailwind CSS
- **LLM**: Ollama (로컬, 기본 qwen3:4b)
- **검색**: Whoosh(BM25) + ChromaDB(DuckDB) + Jina Reranker
- **임베딩**: BAAI/bge-m3 (폴백: KoE5 → KR-SBERT)
- **문서 처리**: hwplib+JPype1 (HWP), PyMuPDF+Tesseract (PDF)

### RAG 파이프라인

```
[질의 재작성] (query_rewriter.py)
    ↓ Anaphora 해소, 대화 요약 활용
[문서 범위 해결] (doc_scope_resolver.py)
    ↓ 세션 문서, 이전 출처, 토픽 변경 감지
[하이브리드 검색] (hybrid_retriever.py)
    ├─ Whoosh BM25 (TOPK=30)
    ├─ ChromaDB Vector (TOPK=30)
    └─ RRF 병합 (k=60)
    ↓
[리랭킹] (reranker.py)
    ↓ Jina Reranker (TOPK=10)
[생성] (generator_ollama.py)
    ↓ Evidence-Only, 스트리밍
[후검증] (evidence_enforcer.py)
    ↓ Jaccard ≥ 0.55, 정규식, 문장유사도
[출처 추적] (citation_tracker.py)
    ↓ (doc_id, page, start, end)
[포맷팅] (answer_formatter.py)
    ↓ 4단 스키마: 답변, 핵심사실, 상세, 출처
[최종 응답]
```

### 디렉토리 구조

```
/claude_rag_gpt5/
├── backend/              # FastAPI 백엔드
│   ├── main.py          # 엔트리포인트
│   ├── routers/         # API 라우터 (chat, documents, admin)
│   ├── processors/      # 문서 파싱 (HWP, PDF, 청킹)
│   ├── rag/             # RAG 파이프라인 (검색, 생성, 검증)
│   ├── eval/            # 평가 시스템 (Golden QA)
│   └── utils/           # 유틸리티
├── frontend/            # React 프론트엔드
│   └── src/
│       ├── components/  # UI 컴포넌트
│       └── stores/      # 상태 관리
├── data/
│   ├── documents/       # 문서 업로드 위치
│   ├── index/           # Whoosh 인덱스
│   ├── chroma/          # ChromaDB
│   └── golden/          # Golden QA 데이터셋
├── tests/               # 테스트
└── tools/               # 유틸리티 도구
```

상세 구조는 [CLAUDE.md](CLAUDE.md) 참조

---

## 📦 설치 및 실행

### 시스템 요구사항
- **OS**: Linux, macOS, Windows (WSL2 권장)
- **Python**: 3.12 이상
- **RAM**: 8GB 이상 (16GB 권장)
- **Disk**: 10GB 이상 여유 공간

### 의존성
- **Ollama**: https://ollama.com/ (로컬 LLM)
- **Java**: hwplib 사용 시 필요 (HWP 파싱)
- **Tesseract**: OCR 사용 시 필요 (PDF 폴백)

### 설치 단계

#### 1. Ollama 설치 및 모델 다운로드
```bash
# Ollama 설치 (https://ollama.com/download)
curl -fsSL https://ollama.com/install.sh | sh

# 모델 다운로드 (필수)
ollama pull qwen3:4b

# (옵션) 상위 모델 사용
ollama pull qwen2.5:14b
ollama pull llama3.1:70b
```

#### 2. Python 의존성 설치
```bash
# 프로젝트 구조 생성
make setup

# 의존성 설치
make install

# (옵션) 모델 오프라인 다운로드
python3 setup_offline.py --download-models
```

#### 3. Tesseract 설치 (OCR 필요 시)
```bash
# macOS
brew install tesseract tesseract-lang

# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-kor

# Windows
# https://github.com/UB-Mannheim/tesseract/wiki 참조
```

#### 4. Java 설치 (HWP 필요 시)
```bash
# macOS
brew install openjdk@17

# Ubuntu/Debian
sudo apt-get install openjdk-17-jdk

# hwplib.jar 배치
# ./lib/hwplib.jar 또는 /usr/local/lib/hwplib.jar
```

### 환경 설정

`.env` 파일 생성 (`.env.example` 참조):
```bash
cp .env.example .env
```

주요 설정 (필요 시 수정):
```bash
# LLM 모델 변경
OLLAMA_MODEL=qwen3:4b  # 또는 qwen2.5:14b, llama3.1:70b

# 검색 가중치 조정
W_BM25=0.4
W_VECTOR=0.4
W_RERANK=0.2

# 성능 튜닝 (메모리 부족 시)
EMBED_BATCH=8          # 기본 16
TOPK_BM25=20           # 기본 30
TOPK_VECTOR=20         # 기본 30
CHUNK_TOKENS=1024      # 기본 2048
```

---

## 📖 사용 방법

### 1. 문서 인덱싱

```bash
# data/documents/ 디렉토리에 HWP/PDF 파일 배치
cp your_documents/*.hwp data/documents/
cp your_documents/*.pdf data/documents/

# 인덱싱 실행
make index
```

**인덱싱 결과**:
- `data/index/`: Whoosh BM25 인덱스
- `data/chroma/`: ChromaDB 벡터 DB

### 2. 시스템 실행

```bash
# 개발 모드 (hot reload)
make run

# 백그라운드 실행
nohup make run > logs/app.log 2>&1 &

# 중단
make stop
```

### 3. 웹 UI 사용

1. 브라우저에서 http://localhost:5173 접속
2. **새 세션 생성** 버튼 클릭
3. **문서 업로드** (선택사항, 또는 기존 인덱스 사용)
4. 질문 입력 및 답변 확인
5. **출처 번호** 클릭 시 원문 보기

### 4. API 사용

#### 세션 생성
```bash
curl -X POST http://localhost:8000/api/chat/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "예산 관련 질의"}'
```

#### 질의 (비스트리밍)
```bash
curl -X POST http://localhost:8000/api/chat/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"query": "2024년 예산 편성 지침의 주요 변경사항은?"}'
```

#### 스트리밍 질의
```bash
curl -X POST http://localhost:8000/api/chat/sessions/{session_id}/messages/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "디지털 전환 예산은 얼마인가?"}' \
  --no-buffer
```

전체 API 문서: http://localhost:8000/docs

---

## 🧪 평가 및 테스트

### Golden QA 평가

```bash
make qa
# → reports/accuracy_dashboard.html 생성
```

**평가 기준** (`data/golden/eval_rules.json`):
- Exact Match ≥ 95%
- F1 Score ≥ 99%
- Citation Accuracy ≥ 99.5%
- Hallucination Rate = 0%

### 단위 테스트

```bash
# 전체 테스트 실행
pytest tests/ -v

# 개별 테스트
pytest tests/test_retrieval.py           # 검색 테스트
pytest tests/test_conversation_summarizer.py  # 대화 요약
pytest tests/test_query_rewriter.py      # 질의 재작성
pytest tests/test_chat_router_memory.py  # 라우터 통합

# 커버리지 리포트
pytest tests/ --cov=backend --cov-report=html
```

### 품질 지표 추적

**메타데이터 기반 모니터링**:
- 회상 실패율(Recall Failure Rate): `metadata.doc_scope.diagnostics`
- Retrieval Gain@5: 검색 점수 분포 분석
- 재작성 폴백 비율: `metadata.rewrite.used_fallback`
- 요약 사용률: `metadata.memory.summary_updated`

**로그 분석**:
```bash
# 질의 재작성 로그
grep "rewrite" logs/backend.log

# 토픽 변경 감지
grep "topic_change_detected" logs/backend.log

# 출처 일관성 체크
grep "CRITICAL: Generated source" logs/backend.log
```

---

## 📚 API 문서

### 핵심 엔드포인트

#### POST `/api/chat/sessions`
새 채팅 세션 생성
```json
// Request
{
  "title": "예산 관련 질의",
  "document_ids": ["budget_2024.pdf"]  // 옵션
}

// Response
{
  "success": true,
  "session": {
    "id": "abc123",
    "title": "예산 관련 질의",
    "created_at": "2025-01-30T10:00:00"
  }
}
```

#### POST `/api/chat/sessions/{session_id}/messages`
질의 및 응답 (비스트리밍)
```json
// Request
{
  "query": "2024년 예산 편성 지침은?",
  "doc_ids": ["budget_2024.pdf"],  // 옵션
  "reset_context": false           // 옵션 (대화 초기화)
}

// Response
{
  "query": "2024년 예산 편성 지침은?",
  "answer": "2024년 예산 편성 지침의 주요 내용은 다음과 같습니다...",
  "key_facts": [
    "디지털 전환 예산 10% 증액 [1]",
    "탄소중립 관련 예산 신설 [1]"
  ],
  "sources": [
    {
      "doc_id": "budget_2024.pdf",
      "page": 3,
      "text": "...원문...",
      "display_index": 1
    }
  ],
  "metadata": {
    "evidence_count": 10,
    "rewrite": {"used_fallback": false},
    "doc_scope": {"mode": "session"},
    "memory": {"summary_updated": true}
  }
}
```

#### POST `/api/documents/upload`
문서 업로드
```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@document.pdf" \
  -F "auto_index=true"
```

전체 API: http://localhost:8000/docs

---

## 🛠️ 문제 해결

### 흔한 오류

#### "Ollama connection failed"
```bash
# Ollama 상태 확인
ollama list

# Ollama 재시작
pkill ollama
ollama serve

# 모델 재다운로드
ollama pull qwen3:4b
```

#### "JVM already started" (HWP 파싱)
- `jpype.isJVMStarted()` 체크가 누락되었을 수 있습니다
- hwplib.jar 경로 확인: `./lib/hwplib.jar`

#### "ChromaDB DuckDB error"
```bash
# ChromaDB 초기화
rm -rf data/chroma/*
make index
```

#### "No module named 'sentence_transformers'"
```bash
# 의존성 재설치
make install
```

### 성능 튜닝

#### 메모리 부족 (8GB RAM)
`.env` 수정:
```bash
EMBED_BATCH=8          # 기본 16
TOPK_BM25=20           # 기본 30
TOPK_VECTOR=20         # 기본 30
CHUNK_TOKENS=1024      # 기본 2048
```

#### 검색 품질 저하
```bash
# 가중치 조정
W_BM25=0.5
W_VECTOR=0.3
W_RERANK=0.2

# 리랭킹 후보 증가
TOPK_RERANK=15         # 기본 10
```

#### 응답 속도 저하
```bash
# ONNX 리랭커 활성화
RERANK_USE_ONNX=true

# 스트리밍 엔드포인트 사용
# POST /api/chat/sessions/{id}/messages/stream
```

---

## 🤝 기여 및 라이선스

### 기여하기

버그 리포트 및 기능 제안: [GitHub Issues](https://github.com/your-repo/issues)

### 상태

**현재 상태**: ✅ 프로덕션 준비 완료

### 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일 참조

---

## 📖 추가 문서

- **[CLAUDE.md](CLAUDE.md)**: 상세 시스템 아키텍처 및 유지보수 가이드
- **[WINDOWS_SETUP.md](WINDOWS_SETUP.md)**: Windows 환경 설치 가이드
- **[PROJECT_PLAN.md](PROJECT_PLAN.md)**: 프로젝트 계획 및 로드맵

---

**문서 버전**: 2.0
