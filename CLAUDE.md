# CLAUDE.md

**목적**: 이 파일은 Claude Code에게 폐쇄망/오프라인 환경에서 동작하는 완성형 RAG 시스템(HWP/PDF 한국어 공문서 처리)의 현재 구현 상태와 유지보수 지침을 제공합니다.

**중요**: 이 시스템은 실제 운영 중이며, 모든 핵심 기능이 구현되어 있습니다. 새로운 기능 추가 시 기존 아키텍처를 준수하세요.

---

## 0) 시스템 개요

### 핵심 특징
- ✅ **완전 오프라인**: Docker 없이 로컬 환경에서 동작
- ✅ **한국어 공문서 특화**: HWP/PDF 구조 보존 파싱
- ✅ **하이브리드 검색**: Whoosh(BM25) + ChromaDB + 리랭커
- ✅ **Evidence-Only 생성**: 할루시네이션 방지 및 출처 추적
- ✅ **멀티턴 대화**: 세션 기반 컨텍스트 관리 및 대화 메모리
- ✅ **스트리밍 응답**: 실시간 답변 생성
- ✅ **8GB RAM 동작**: 효율적인 메모리 관리

### 기술 스택
- **Backend**: FastAPI + Uvicorn (Python 3.12+)
- **Frontend**: React 18 + Vite + Tailwind CSS
- **LLM**: Ollama (로컬, 기본 qwen3:4b)
- **검색**: Whoosh(BM25) + ChromaDB(DuckDB) + Jina Reranker
- **임베딩**: BAAI/bge-m3 (폴백: KoE5 → KR-SBERT)
- **문서 처리**: hwplib+JPype1 (HWP), PyMuPDF+Tesseract (PDF)

---

## 1) 현재 구현된 디렉토리 구조

```
/claude_rag_gpt5/
├── Makefile                          # ✅ 빌드/실행 자동화
├── README.md                         # ✅ 사용자 가이드
├── .env.example                      # ✅ 환경 설정 템플릿
├── requirements.txt                  # ✅ Python 의존성
├── setup_offline.py                  # ✅ 오프라인 설치 스크립트
├── start.sh                          # ⚠️ TODO: 생성 필요
├── stop.sh                           # ✅ 시스템 종료 스크립트
│
├── tools/                            # ✅ 유틸리티 도구
│   ├── bundle_creator.py            # ✅ 오프라인 번들 생성
│   ├── integrity_verifier.py        # ✅ 설치 검증
│   ├── validate_installation.py     # ✅ 환경 검증
│   └── export_licenses.md           # ✅ 라이선스 정보
│
├── backend/                          # ✅ 백엔드 애플리케이션
│   ├── main.py                      # ✅ FastAPI 앱 엔트리포인트
│   ├── config.py                    # ✅ 중앙 설정 관리
│   ├── deps.py                      # ✅ 의존성 주입
│   ├── schemas.py                   # ✅ Pydantic 스키마
│   │
│   ├── routers/                     # ✅ API 라우터
│   │   ├── query.py                # ✅ 레거시 질의 엔드포인트
│   │   ├── chat.py                 # ✅ 멀티턴 채팅 (핵심)
│   │   ├── documents.py            # ✅ 문서 관리
│   │   └── admin.py                # ✅ 관리 기능
│   │
│   ├── processors/                  # ✅ 문서 처리
│   │   ├── hwp_structure_parser.py          # ✅ HWP 파싱 (hwplib+JPype1)
│   │   ├── pdf_hybrid_processor.py          # ✅ PDF 파싱 (PyMuPDF+OCR)
│   │   ├── structure_chunker.py             # ✅ 구조 보존 청킹
│   │   ├── normalizer_govkr.py              # ✅ 공문서 정규화
│   │   ├── indexer.py                       # ✅ 문서 인덱싱
│   │   ├── directive_processor.py           # ✅ 지시사항 문서 처리
│   │   └── directive_extractor_*.py         # ✅ 특수 문서 추출
│   │
│   ├── rag/                         # ✅ RAG 파이프라인
│   │   ├── embedder.py             # ✅ 임베딩 (bge-m3, 폴백 지원)
│   │   ├── whoosh_bm25.py          # ✅ BM25 검색
│   │   ├── chroma_store.py         # ✅ 벡터 저장소 (DuckDB)
│   │   ├── hybrid_retriever.py     # ✅ 하이브리드 검색 + RRF
│   │   ├── reranker.py             # ✅ Jina Reranker (ONNX 지원)
│   │   ├── prompt_templates.py     # ✅ Evidence-Only 프롬프트
│   │   ├── generator_ollama.py     # ✅ Ollama 생성기 (스트리밍)
│   │   ├── evidence_enforcer.py    # ✅ 후검증 (Jaccard, 정규식)
│   │   ├── citation_tracker.py     # ✅ 출처 추적 (좌표 포함)
│   │   ├── answer_formatter.py     # ✅ 4단 스키마 포맷터
│   │   ├── conversation_summarizer.py       # ✅ 대화 요약
│   │   ├── query_rewriter.py       # ✅ 질의 재작성 (Anaphora 해소)
│   │   ├── topic_detector.py       # ✅ 토픽 변경 감지
│   │   ├── doc_scope_resolver.py   # ✅ 문서 범위 해결
│   │   ├── response_grounder.py    # ✅ 응답 그라운딩
│   │   ├── response_validator.py   # ✅ 응답 검증
│   │   ├── response_postprocessor.py        # ✅ 후처리
│   │   └── real_time_corrector.py  # ✅ 실시간 교정
│   │
│   ├── eval/                        # ⚠️ 부분 구현
│   │   ├── metrics.py              # ✅ EM/F1/Citation 계산
│   │   ├── golden_evaluator.py     # ✅ Golden QA 평가
│   │   └── failure_report.py       # ⚠️ TODO: 검증 필요
│   │
│   ├── models/                      # ✅ 데이터 모델
│   │   └── session.py              # ✅ 세션/메시지 모델
│   │
│   ├── services/                    # ✅ 비즈니스 로직
│   │   ├── title_generator.py      # ✅ 세션 제목 생성
│   │   └── session_manager.py      # ✅ 세션 관리
│   │
│   └── utils/                       # ✅ 유틸리티
│       ├── log_utils.py            # ✅ 로깅
│       ├── error_handler.py        # ✅ 에러 처리
│       ├── rate_limiter.py         # ✅ Rate limiting
│       ├── ocr.py                  # ⚠️ TODO: 독립 모듈화
│       ├── text.py                 # ⚠️ TODO: 독립 모듈화
│       ├── cache.py                # ⚠️ TODO: 독립 모듈화
│       └── index_manager.py        # ✅ 인덱스 관리
│
├── frontend/                        # ✅ 프론트엔드 (React)
│   ├── index.html                  # ✅ HTML 엔트리
│   ├── vite.config.js              # ✅ Vite 설정
│   ├── package.json                # ✅ npm 의존성
│   ├── tailwind.config.js          # ✅ Tailwind 설정
│   └── src/
│       ├── main.jsx                # ✅ React 엔트리
│       ├── App.jsx                 # ✅ 메인 앱
│       ├── components/             # ✅ React 컴포넌트
│       │   ├── ChatInterface.jsx          # ✅ 채팅 UI
│       │   ├── DocumentUploader.jsx       # ✅ 문서 업로드
│       │   ├── SourcePopup.jsx            # ✅ 출처 팝업
│       │   ├── SessionList.jsx            # ✅ 세션 목록
│       │   └── StatusIndicator.jsx        # ✅ 상태 표시
│       ├── stores/                 # ✅ 상태 관리 (Zustand)
│       ├── services/               # ✅ API 클라이언트
│       └── styles.css              # ✅ 스타일
│
├── data/                            # ✅ 데이터 디렉토리
│   ├── documents/                  # 📁 문서 업로드 위치
│   ├── index/                      # 📁 Whoosh 인덱스
│   ├── chroma/                     # 📁 Chroma 벡터 DB
│   ├── sessions/                   # 📁 세션 저장소
│   └── golden/                     # ✅ Golden QA 데이터셋
│       ├── qa_100.json            # ✅ 평가 질문
│       ├── doc_meta.json          # ✅ 문서 메타데이터
│       └── eval_rules.json        # ✅ 평가 규칙
│
├── tests/                           # ⚠️ 부분 구현
│   ├── test_retrieval.py           # ✅ 검색 테스트
│   ├── test_generation.py          # ✅ 생성 테스트
│   ├── test_citation.py            # ✅ Citation 테스트
│   ├── test_conversation_summarizer.py    # ✅ 요약 테스트
│   ├── test_query_rewriter.py      # ✅ 재작성 테스트
│   └── test_chat_router_memory.py  # ✅ 라우터 통합 테스트
│
└── logs/                            # 📁 로그 디렉토리
```

**범례**:
- ✅ 완전 구현 및 동작
- ⚠️ 부분 구현 또는 검증 필요
- ❌ 미구현 (향후 추가 필요)
- 📁 런타임 생성 디렉토리

---

## 2) 환경 설정 (.env)

현재 `.env.example`에 정의된 주요 설정:

```bash
# 서버/동시성
APP_PORT=8000
WORKERS=4
REQUEST_TIMEOUT_S=15
MAX_QUEUE=256

# 문서/인덱스
DOC_DIR=./data/documents
WHOOSH_DIR=./data/index
CHROMA_DIR=./data/chroma
CHUNK_TOKENS=2048
CHUNK_OVERLAP=256
TABLE_AS_SEPARATE=true
FOOTNOTE_BACKLINK=true

# 임베딩
PRIMARY_EMBED=BAAI/bge-m3
SECONDARY_EMBED=nlpai-lab/KoE5
FALLBACK_EMBED=snunlp/KR-SBERT-Medium-extended
EMBED_BATCH=16

# 하이브리드 검색 가중치
W_BM25=0.4
W_VECTOR=0.4
W_RERANK=0.2
RRF_K=60
TOPK_BM25=30
TOPK_VECTOR=30
TOPK_RERANK=10

# 리랭커
RERANKER_ID=jinaai/jina-reranker-v2-base-multilingual
RERANK_USE_ONNX=true

# 생성(LLM)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
GEN_TEMPERATURE=0.0
GEN_TOP_P=1.0
GEN_MAX_TOKENS=1024

# 정확도 임계값
EVIDENCE_JACCARD=0.55
CITATION_SENT_SIM=0.9
CITATION_SPAN_IOU=0.5
CONFIDENCE_MIN=0.7

# 보안/세션
SESSION_TIMEOUT_S=3600
AUDIT_LOG_RETENTION_D=90
PII_MASKING=true

# 토픽 감지
TOPIC_SIMILARITY_THRESHOLD=0.3
TOPIC_CONFIDENCE_THRESHOLD=0.15
TOPIC_MIN_SCORE_THRESHOLD=0.05
TOPIC_DETECTION_ENABLED=true
```

**모델 교체**: `OLLAMA_MODEL`만 변경하면 상위 모델 사용 가능 (예: `qwen2.5:14b`, `llama3.1:70b`)

---

## 3) 핵심 아키텍처 설계

### 3.1 RAG 파이프라인 플로우

```
사용자 질의
    ↓
[질의 재작성] (query_rewriter.py)
    ↓ (Anaphora 해소, 대화 요약 활용)
    ↓
[문서 범위 해결] (doc_scope_resolver.py)
    ↓ (세션 문서, 이전 출처, 토픽 변경 감지)
    ↓
[하이브리드 검색] (hybrid_retriever.py)
    ├─ Whoosh BM25 (TOPK_BM25=30)
    ├─ ChromaDB Vector (TOPK_VECTOR=30)
    └─ RRF 병합 (RRF_K=60)
    ↓
[리랭킹] (reranker.py)
    ↓ (Jina Reranker, TOPK_RERANK=10)
    ↓
[생성] (generator_ollama.py)
    ↓ (Evidence-Only, 스트리밍)
    ↓
[후검증] (evidence_enforcer.py)
    ├─ Jaccard 유사도
    ├─ 정규식 검증
    └─ 문장 유사도
    ↓
[출처 추적] (citation_tracker.py)
    ↓ (문서ID, 페이지, 좌표)
    ↓
[응답 포맷팅] (answer_formatter.py)
    ↓ (4단 스키마: 답변, 핵심사실, 상세, 출처)
    ↓
[응답 그라운딩] (response_grounder.py)
    ↓
[응답 검증] (response_validator.py)
    ↓
최종 응답
```

### 3.2 문서 처리 파이프라인

```
HWP/PDF 업로드
    ↓
[파싱]
    ├─ HWP: hwp_structure_parser.py (hwplib+JPype1)
    │   └─ 조/항/호/표/각주 구조 보존
    └─ PDF: pdf_hybrid_processor.py (PyMuPDF)
        └─ OCR 폴백 (Tesseract, 임계값 0.6)
    ↓
[정규화] (normalizer_govkr.py)
    ├─ 날짜 ISO 변환
    ├─ 숫자/금액 표준화
    └─ 법령 표기 통일
    ↓
[청킹] (structure_chunker.py)
    ├─ 의미 단락 병합 (CHUNK_TOKENS=2048)
    ├─ 표/각주 분리 + 역링크
    └─ 메타데이터 부착 (doc_id, page, start, end)
    ↓
[임베딩] (embedder.py)
    └─ BAAI/bge-m3 (폴백: KoE5 → KR-SBERT)
    ↓
[인덱싱]
    ├─ Whoosh: whoosh_bm25.py
    └─ ChromaDB: chroma_store.py
```

### 3.3 멀티턴 대화 메모리

현재 시스템은 **3계층 메모리 구조**를 구현:

1. **Short-term Memory** (최근 10개 메시지)
   - `routers/chat.py`: `get_session_context(max_messages=10)`

2. **Summary Memory** (대화 요약)
   - `conversation_summarizer.py`: 신뢰도 게이트(confidence gate) 기반 요약
   - 저장 조건: `should_use_summary=True`, `used_fallback=False`

3. **Entity Memory** (최근 엔터티)
   - `recent_entities` 리스트로 저장
   - 질의 재작성 시 참조

4. **Document Scope Memory** (문서 범위 고정)
   - `first_response_evidences`: 첫 답변의 evidence 저장
   - `first_response_citation_map`: Citation 번호 고정
   - 후속 질문에서 동일 문서 범위 재사용

**중요**: 메모리 팩트 수집 기능은 **현재 비활성화** (출처 일관성 문제 해결 우선)

---

## 4) 주요 컴포넌트 상세 설명

### 4.1 HWP 파서 (hwp_structure_parser.py)

**구현 상태**: ✅ 완전 구현

**핵심 기능**:
- hwplib (Java) + JPype1 브리지
- JVM 시작/종료 자동 관리
- 조/항/호 구조 감지 (정규식)
- 표/각주 추출 및 ID 부여
- 페이지 추정 (2000자/페이지)

**주의사항**:
- `jpype.isJVMStarted()` 체크 필수
- hwplib.jar 경로: `./lib/hwplib.jar`, `/usr/local/lib/hwplib.jar`
- 폴백 파서 구현 (hwplib 실패 시)

### 4.2 PDF 파서 (pdf_hybrid_processor.py)

**구현 상태**: ✅ 완전 구현

**핵심 기능**:
- PyMuPDF 우선 텍스트 추출
- OCR 필요 여부 자동 판단 (임계값 0.6)
- Tesseract OCR 폴백 (한국어 지원)
- 특수 문서 감지 (구청장 지시사항)
- 텍스트 정리 (특수문자, 중복 공백)

**OCR 활성화 조건**:
```python
def _needs_ocr(self, text: str) -> bool:
    if len(text.strip()) < 100:
        return True

    extraction_rate = len(alphanumeric) / len(text)
    return extraction_rate < 0.6  # ocr_threshold
```

### 4.3 하이브리드 검색 (hybrid_retriever.py)

**구현 상태**: ✅ 완전 구현

**알고리즘**: Reciprocal Rank Fusion (RRF)

```python
def rrf_score(rank, k=60):
    return 1.0 / (k + rank)

# BM25 결과와 Vector 결과 병합
final_score = w_bm25 * bm25_score + w_vector * vector_score
```

**가중치** (`.env`):
- `W_BM25=0.4`
- `W_VECTOR=0.4`
- `W_RERANK=0.2`

### 4.4 Evidence-Only 생성 (generator_ollama.py)

**구현 상태**: ✅ 완전 구현 (스트리밍 지원)

**프롬프트 구조** (`prompt_templates.py`):
```
SYSTEM:
- 제공된 evidence 외 사실 생성 금지
- 모르면 "근거 부족" 응답
- 숫자/날짜/조항 그대로 추출

OUTPUT SCHEMA:
1. 핵심 답변 (1-2문장)
2. 주요 사실 (3-5개 불릿)
3. 상세 설명 (옵션)
4. 출처 목록 [(doc_id, page, start, end)]
```

**후검증** (`evidence_enforcer.py`):
- Jaccard 유사도 ≥ 0.55
- 정규식 검증
- 문장 유사도 (cosine)

### 4.5 출처 추적 (citation_tracker.py)

**구현 상태**: ✅ 완전 구현

**메타데이터 구조**:
```python
{
    "doc_id": "문서ID",
    "page": 페이지번호,
    "start_char": 시작오프셋,
    "end_char": 종료오프셋,
    "text": "원문텍스트",
    "score": 0.95
}
```

**고정 Citation 기능**:
- 첫 답변의 `citation_map` 저장
- 후속 질문에서 동일 번호 재사용
- 출처 일관성 보장

### 4.6 질의 재작성 (query_rewriter.py)

**구현 상태**: ✅ 완전 구현

**Anaphora 해소**:
```python
# "그건 어떻게 해?" → "2024년 예산 편성은 어떻게 해?"
# 대화 요약, 최근 엔터티, 이전 출처 활용
```

**폴백 전략**:
- LLM 호출 실패 시 원본 질의 사용
- `used_fallback=True` 메타데이터 기록

### 4.7 토픽 변경 감지 (topic_detector.py)

**구현 상태**: ✅ 완전 구현

**감지 조건**:
- 임베딩 유사도 < 0.3
- 검색 신뢰도 < 0.15
- 최소 점수 < 0.05

**동작**:
- 토픽 변경 감지 시 문서 범위 확장
- 새로운 문서 제안 (`suggested_doc_ids`)
- 메타데이터로 전달

---

## 5) API 엔드포인트

### 5.1 핵심 엔드포인트 (routers/chat.py)

#### POST `/api/chat/sessions`
- 새 채팅 세션 생성
- Request: `{title?, document_ids?}`
- Response: `{success, session}`

#### GET `/api/chat/sessions`
- 세션 목록 조회 (페이징)
- Query: `?page=1&page_size=20`

#### GET `/api/chat/sessions/{session_id}`
- 특정 세션 조회
- Response: 전체 메시지 히스토리

#### POST `/api/chat/sessions/{session_id}/messages`
- **메인 질의 엔드포인트** (비스트리밍)
- Request: `{query, doc_ids?, reset_context?}`
- Response: `QueryResponse` (답변, 출처, 메타데이터)

#### POST `/api/chat/sessions/{session_id}/messages/stream`
- **스트리밍 질의 엔드포인트**
- Response: NDJSON 스트림
  - `{status: "문서 검색 중..."}`
  - `{content: "chunk"}`
  - `{complete: true, sources: [...]}`

#### POST `/api/chat/sessions/{session_id}/interrupt`
- 답변 생성 중단
- 중단 메시지 자동 저장

#### DELETE `/api/chat/sessions/{session_id}/messages`
- 세션 메시지 초기화

### 5.2 문서 관리 (routers/documents.py)

#### POST `/api/documents/upload`
- 문서 업로드 (HWP/PDF)
- 자동 인덱싱

#### GET `/api/documents`
- 문서 목록 조회

#### DELETE `/api/documents/{doc_id}`
- 문서 삭제 및 인덱스 제거

---

## 6) 실행 및 배포

### 6.1 초기 설정

```bash
# 1. 프로젝트 구조 생성
make setup

# 2. 의존성 설치
make install

# 3. Ollama 모델 다운로드 (필수)
ollama pull qwen3:4b

# 4. (옵션) 모델 다운로드
python3 setup_offline.py --download-models
```

### 6.2 문서 인덱싱

```bash
# data/documents/에 HWP/PDF 파일 배치 후
make index
```

**인덱싱 시 생성되는 것**:
- `data/index/`: Whoosh BM25 인덱스
- `data/chroma/`: ChromaDB 벡터 DB (DuckDB 백엔드)

### 6.3 시스템 실행

```bash
# 개발 모드 (hot reload)
make run

# 백그라운드 실행
./start.sh  # TODO: 생성 필요
```

**실행 후 접근**:
- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- API Docs: http://localhost:8000/docs

### 6.4 중단

```bash
make stop
# 또는
./stop.sh
```

### 6.5 오프라인 번들 생성

```bash
make bundle
# → dist/rag_chatbot_offline_YYYYMMDD.tar.gz 생성
```

---

## 7) 평가 및 품질 관리

### 7.1 Golden QA 평가

```bash
make qa
# → reports/accuracy_dashboard.html 생성
```

**평가 기준** (`data/golden/eval_rules.json`):
- Exact Match ≥ 95%
- F1 Score ≥ 99%
- Citation Accuracy ≥ 99.5%
- Hallucination Rate = 0%

### 7.2 테스트 실행

```bash
# 전체 테스트
pytest tests/ -v

# 개별 테스트
pytest tests/test_retrieval.py
pytest tests/test_conversation_summarizer.py
pytest tests/test_chat_router_memory.py
```

**현재 테스트 커버리지**:
- ✅ 검색 테스트 (test_retrieval.py)
- ✅ 생성 테스트 (test_generation.py)
- ✅ Citation 테스트 (test_citation.py, test_citation_accuracy.py)
- ✅ 대화 메모리 테스트 (test_conversation_summarizer.py)
- ✅ 질의 재작성 테스트 (test_query_rewriter.py)
- ✅ 라우터 통합 테스트 (test_chat_router_memory.py)
- ✅ 포맷터 테스트 (test_answer_formatter.py)
- ⚠️ 멀티 세션 테스트 (test_multi_session.py) - 검증 필요

### 7.3 로깅 및 모니터링

**로그 위치**:
- `logs/`: 애플리케이션 로그
- `backend.log`: 백엔드 메인 로그

**메타데이터 추적**:
- 질의 재작성: `metadata.rewrite.used_fallback`
- 대화 요약: `metadata.memory.summary_updated`
- 문서 범위: `metadata.doc_scope.mode`
- 토픽 변경: `metadata.doc_scope.topic_change_detected`

---

## 8) 주요 설계 결정 및 제약사항

### 8.1 메모리 최적화 (8GB RAM)

**전략**:
- 임베딩 배치 처리 (`EMBED_BATCH=16`)
- LRU 캐싱 (임베딩, 리랭커)
- Whoosh searcher 재사용
- ChromaDB DuckDB 백엔드 (메모리 효율)
- 지연 로딩 (lazy initialization)

### 8.2 출처 일관성 보장

**문제**: 후속 질문에서 다른 문서의 출처가 섞임

**해결책** (현재 구현):
1. 첫 답변의 `evidences`와 `citation_map` 저장
2. 후속 질문에서 문서 범위(`doc_ids`) 고정
3. 새로운 검색 수행하되 동일 문서만 필터링
4. `fixed_citation_map` 재사용으로 출처 번호 일관성 유지

**핵심 코드** (`routers/chat.py:832-854`):
```python
fixed_citation_map = session.first_response_citation_map if should_use_previous_sources else None
response = citation_tracker.track_citations(response, evidences, allowed_doc_ids=allowed_docs, fixed_citation_map=fixed_citation_map)
```

### 8.3 스트리밍 응답 Think Tag 필터링

**문제**: Ollama 일부 모델이 `<think>` 태그 출력

**해결책** (`routers/chat.py:1136-1390`):
- 스트리밍 중 실시간 필터링
- `<think>`, `<thinking>`, `[think]` 패턴 감지
- 버퍼링 및 안전한 출력

### 8.4 클라이언트 연결 중단 처리

**구현** (`routers/chat.py:434-463, 1109-1131`):
- `asyncio.Event` 기반 취소 신호
- `http_request.is_disconnected()` 주기적 체크
- 중단 메시지 자동 저장 (중복 방지)

---

## 9) 향후 개선 사항

### 9.1 TODO 항목

#### 높음 우선순위
- [ ] `start.sh` 생성 (백그라운드 실행 스크립트)
- [ ] `failure_report.py` 검증 및 보완
- [ ] `utils/ocr.py`, `utils/text.py`, `utils/cache.py` 독립 모듈화
- [ ] 전체 테스트 커버리지 80% 이상

#### 중간 우선순위
- [ ] 메모리 팩트 수집 재활성화 (출처 일관성 유지하면서)
- [ ] 인덱스 핫 리로드 기능 개선
- [ ] 문서 접근권한 필터 구현
- [ ] PII 마스킹 기능 활성화

#### 낮음 우선순위
- [ ] WebSocket 엔드포인트 최적화
- [ ] 프론트엔드 접근성 개선 (ARIA)
- [ ] 다국어 지원 (영어)

### 9.2 알려진 제한사항

1. **HWP 파싱**:
   - hwplib.jar 필수 (오프라인 환경에서 별도 제공)
   - Java 런타임 필요

2. **PDF OCR**:
   - Tesseract 한국어 데이터 필수
   - OCR 임계값(0.6) 조정 가능하나 성능 영향

3. **Golden QA**:
   - 샘플 데이터셋만 포함 (실제 평가는 추가 필요)
   - 평가 메트릭 정확도 검증 필요

4. **동시성**:
   - 현재 최대 수십 명 동시 사용자 가정
   - 대규모 환경은 Redis 세션 저장소 권장

---

## 10) 문제 해결 가이드

### 10.1 흔한 오류

#### "JVM already started"
```python
# hwp_structure_parser.py 확인
if not jpype.isJVMStarted():
    jpype.startJVM(classpath=[jar_path])
```

#### "Ollama connection failed"
```bash
# Ollama 상태 확인
ollama list
curl http://localhost:11434/api/tags

# 모델 다운로드
ollama pull qwen3:4b
```

#### "No module named 'sentence_transformers'"
```bash
# 의존성 재설치
make install

# 또는 수동 설치
pip install -r requirements.txt
```

#### "ChromaDB DuckDB error"
```bash
# ChromaDB 디렉토리 초기화
rm -rf data/chroma/*
make index
```

### 10.2 성능 튜닝

#### 메모리 부족
- `EMBED_BATCH` 감소 (16 → 8)
- `TOPK_BM25`, `TOPK_VECTOR` 감소 (30 → 20)
- `CHUNK_TOKENS` 감소 (2048 → 1024)

#### 검색 품질 저하
- `W_BM25`, `W_VECTOR`, `W_RERANK` 가중치 조정
- `TOPK_RERANK` 증가 (10 → 15)
- 리랭커 활성화 확인

#### 응답 속도 저하
- 리랭커 ONNX 모드 활성화 (`RERANK_USE_ONNX=true`)
- 스트리밍 엔드포인트 사용
- 임베딩 캐시 확인

---

## 11) 참고 자료

### 11.1 핵심 파일 위치

| 기능 | 파일 경로 | 비고 |
|------|-----------|------|
| 메인 API | `backend/main.py` | FastAPI 앱 |
| 채팅 라우터 | `backend/routers/chat.py` | 핵심 엔드포인트 |
| 하이브리드 검색 | `backend/rag/hybrid_retriever.py` | RRF 구현 |
| Evidence 검증 | `backend/rag/evidence_enforcer.py` | Jaccard 후검증 |
| Citation 추적 | `backend/rag/citation_tracker.py` | 출처 좌표 |
| 세션 관리 | `backend/services/session_manager.py` | 파일 기반 |
| 프론트엔드 | `frontend/src/App.jsx` | React 메인 |
| 환경 설정 | `backend/config.py` | 중앙 설정 |

### 11.2 외부 의존성

- **Ollama**: https://ollama.com/
- **hwplib**: https://github.com/neolord0/hwplib
- **Tesseract**: https://github.com/tesseract-ocr/tesseract
- **BAAI/bge-m3**: https://huggingface.co/BAAI/bge-m3
- **Jina Reranker**: https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual

---

---

**문서 버전**: 2.0
**시스템 상태**: ✅ 프로덕션 준비 완료