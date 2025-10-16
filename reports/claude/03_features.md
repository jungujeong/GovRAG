# 기능 변화 추론

<!-- 생성 시간: 2025-10-15 15:50 -->

## README 비교로 새 기능 파악

### 이전 버전 README (147줄)
**근거: readme_old.md**

**핵심 내용**:
```markdown
# HWP 문서 기반 RAG 챗봇 시스템
폐쇄망 환경에서 동작하는 한글(HWP) 문서 기반 RAG 챗봇 시스템

## 주요 기능
- HWP 문서 분석 및 요약
- 문서 기반 질의응답
- 임베딩 모델 선택 가능
- 문서 관리(업로드, 삭제)

## 기술 스택
- Streamlit (UI)
- LangChain (RAG 프레임워크)
- Ollama (로컬 LLM)
- ChromaDB (벡터 데이터베이스)
- hwplib (Java 기반 HWP 처리)
```

**특징**:
- 단순 RAG 챗봇 (문서 → 임베딩 → 질의응답)
- Streamlit 기반 단일 UI
- 기본적인 HWP 처리

---

### 현재 버전 README (45줄)
**근거: readme_new.md**

**핵심 내용**:
```markdown
# RAG Chatbot System (폐쇄망/오프라인)
한국어 공문서(HWP/PDF) 처리에 최적화된 Evidence-Only RAG 시스템

## 주요 기능
- HWP/PDF 한국어 문서 구조 보존 파싱
- Whoosh(BM25) + ChromaDB 하이브리드 검색
- Evidence-Only 생성으로 할루시네이션 방지
- 출처 추적 및 인용 좌표 제공
- 오프라인/폐쇄망 완전 지원
- 후속 질문 대응용 대화 요약·엔터티 메모리 + 질의 재작성

## Conversation Memory / Observability
- 세션별 conversation_summary, recent_entities 메모리 계층 저장
- 질의 재작성(Anaphora 해소) → 검색 → 생성 전 과정 메타데이터 기록
- 회상 실패율, Retrieval Gain@5 등 KPI 수집

## 평가
- Golden QA 100문항 평가
- 기준: EM≥95%, F1≥99%, Citation≥99.5%, Hallucination=0%
```

**특징**:
- Evidence-Only RAG (할루시네이션 방지 강조)
- 하이브리드 검색 (BM25 + Vector)
- 대화 메모리 및 관찰성
- 체계적 평가 기준

---

## 의존성 변화로 기술 스택 변경 추론

### 프레임워크 전환
**근거: req_old.txt vs req_new.txt**

| 항목 | 이전 | 현재 | 변화 의미 |
|------|------|------|----------|
| **웹 프레임워크** | Streamlit | FastAPI + Uvicorn | 프로토타입 → 프로덕션 |
| **RAG 프레임워크** | LangChain | **없음** (자체 구현) | 범용 → 특화 |
| **UI** | Streamlit 내장 | React + Vite | 서버 사이드 → SPA |

**추론**:
- Streamlit은 빠른 프로토타이핑용, 실제 서비스에는 제약
- LangChain 제거 → 한국어 공문서에 최적화된 커스텀 파이프라인 구축
- React 도입 → 풍부한 상호작용 (세션 관리, 실시간 스트리밍, 출처 팝업)

### 검색 엔진 변화
**근거: requirements.txt**

| 기능 | 이전 | 현재 | 추론 |
|------|------|------|------|
| 키워드 검색 | rank-bm25 (메모리) | **Whoosh** (디스크 인덱스) | 확장성 + 지속성 |
| 벡터 검색 | ChromaDB | ChromaDB | 유지 |
| 하이브리드 | ❌ 없음 | ✅ BM25 + Vector + RRF | 정확도 개선 |

**추론**:
- rank-bm25는 Python 라이브러리로 메모리에서만 동작 → 대용량 문서 처리 한계
- Whoosh는 Lucene 스타일 디스크 인덱스 → 수백만 문서 처리 가능
- RRF (Reciprocal Rank Fusion): 키워드 + 의미 검색 결과 융합 → 최상위 결과 선정

### 새로 추가된 패키지 의미
**근거: req_new.txt**

| 패키지 | 용도 | 추론되는 기능 |
|--------|------|--------------|
| rapidfuzz | 퍼지 문자열 매칭 | 한국어 유사도 계산, 엔터티 정규화 |
| onnxruntime | ONNX 모델 실행 | 리랭커 모델 (jina-reranker) 추론 |
| httpx | 비동기 HTTP 클라이언트 | Ollama API 호출 (asyncio 지원) |
| pydantic | 데이터 검증 | FastAPI 스키마, 응답 검증 |
| aiofiles | 비동기 파일 I/O | 대용량 문서 비차단 처리 |
| redis | 캐시 | 쿼리 캐싱, 세션 저장 |
| Pillow + opencv-python | 이미지 처리 | PDF 이미지 추출, OCR 전처리 |
| pytesseract | OCR | PDF 텍스트 추출 실패 시 이미지 OCR |
| tiktoken | 토큰 카운팅 | 청킹 시 토큰 수 계산 (GPT 스타일) |
| psutil | 시스템 모니터링 | 메모리/CPU 사용률 추적 |

**추론**: 엔터프라이즈급 기능 추가 (캐싱, OCR, 리랭킹, 모니터링)

---

## RAG 구성 요소 변화

### 문서 처리 (Indexing)

#### 이전 (utils/document_processor.py 352줄)
**근거: tree_old.txt, git_stat.txt**

```
단일 파일로 통합 처리:
- HWP: hwplib 호출
- PDF: PyMuPDF
- 텍스트 추출 → 청킹 → 임베딩
```

#### 현재 (backend/processors/ 8개 파일, 2,844줄)
**근거: tree_new.txt, git_stat.txt**

```
모듈화된 파이프라인:
1. hwp_structure_parser.py (290줄)
   - HWP 문서 구조 보존 (문단, 표, 각주)

2. pdf_hybrid_processor.py (295줄)
   - PyMuPDF 텍스트 추출
   - 실패 시 Tesseract OCR 자동 전환

3. structure_chunker.py (508줄)
   - 의미 단위 청킹 (조/항/호 경계 보존)
   - 표/각주 역링크 생성

4. normalizer_govkr.py (233줄)
   - 한국 공문서 정규화 (날짜, 숫자, 법령 표기)

5. directive_extractor_whitelist_final.py (935줄)
   - 공문서 구조 추출 (Y축 좌표 매칭)

6. indexer.py (394줄)
   - 전체 파이프라인 오케스트레이션
```

**Before → After**:
| 항목 | 이전 | 현재 |
|------|------|------|
| 파일 수 | 1 | 8 |
| 총 코드 | 352줄 | 2,844줄 |
| HWP 처리 | 기본 텍스트 추출 | 구조 보존 파싱 |
| PDF 처리 | PyMuPDF만 | PyMuPDF + OCR (Tesseract) |
| 청킹 | 고정 크기 (1000자) | 의미 단위 (조항 경계) |
| 정규화 | 없음 | 날짜/숫자/법령 정규화 |

**추론**: 한국어 공문서 특성에 맞춘 특화 처리

---

### 검색 (Retrieval)

#### 이전 (utils/vector_store.py 533줄)
**근거: tree_old.txt**

```
ChromaDB 벡터 검색만:
- 질의 임베딩 생성
- 코사인 유사도 검색
- 상위 K개 반환
```

#### 현재 (backend/rag/ 3개 파일, 1,143줄)
**근거: tree_new.txt, git_stat.txt**

```
하이브리드 검색 파이프라인:
1. hybrid_retriever.py (580줄)
   - BM25 검색 (Whoosh)
   - Vector 검색 (ChromaDB)
   - RRF 융합 (w_bm25=0.4, w_vector=0.4)
   - 키워드 관련성 필터링
   - 문서 다양성 보장

2. embedder.py (101줄)
   - BAAI/bge-m3 (1차)
   - nlpai-lab/KoE5 (2차)
   - snunlp/KR-SBERT-Medium (폴백)

3. reranker.py (217줄)
   - jina-reranker-v2 (ONNX)
   - 상위 10개 재랭킹
```

**Before → After**:
| 항목 | 이전 | 현재 |
|------|------|------|
| 검색 방식 | Vector만 | BM25 + Vector + RRF |
| 리랭킹 | 없음 | jina-reranker (ONNX) |
| 임베딩 | 단일 모델 | 3단계 폴백 (bge-m3 → KoE5 → KR-SBERT) |
| 필터링 | 없음 | 키워드 관련성 + 문서 다양성 |
| 검색 엔진 | ChromaDB | Whoosh + ChromaDB |

**추론**: 정밀도와 재현율의 균형 (키워드 + 의미 검색)

---

### 생성 (Generation)

#### 이전 (utils/rag_chain.py 611줄)
**근거: tree_old.txt**

```
LangChain 기반 생성:
- 질의 + 검색 결과 → LLM
- 단순 프롬프트
- 후처리 없음
```

#### 현재 (backend/rag/ 7개 파일, 3,134줄)
**근거: tree_new.txt, git_stat.txt**

```
Evidence-Only 생성 파이프라인:
1. prompt_templates.py (239줄)
   - 시스템 프롬프트: "문서에 없는 내용 생성 금지"
   - 증거 문단 포맷 (doc_id, page, start, end)
   - 출력 스키마 강제

2. generator_ollama.py (339줄)
   - Ollama REST API 호출
   - 온도 0.0 (결정론적 생성)
   - 스트리밍 지원

3. evidence_enforcer.py (271줄)
   - 자카드 유사도 검증 (≥0.55)
   - 임계값 미만 시 재생성 또는 "근거 부족"

4. citation_tracker.py (813줄)
   - 출처 번호 생성 ([1], [2], [3])
   - 문서 ID → 번호 매핑
   - 좌표 추적 (page, start_char, end_char)

5. answer_formatter.py (713줄)
   - 4단 구조 (핵심 답변, 주요 사실, 상세 설명, 출처)
   - Markdown 포맷팅

6. response_validator.py (364줄)
   - 존재하지 않는 출처 제거
   - 중복 출처 정리
   - 출처 번호 정렬

7. response_grounder.py (236줄)
   - 답변 ↔ 증거 문단 매칭
   - Citation span IoU 계산
   - 문장 유사도 검증
```

**Before → After**:
| 항목 | 이전 | 현재 |
|------|------|------|
| 프레임워크 | LangChain | 자체 구현 (Ollama 직접 호출) |
| 프롬프트 | 단순 | Evidence-Only 시스템 프롬프트 |
| 후검증 | 없음 | 5단계 (Enforcer, Validator, Grounder) |
| 출처 추적 | 없음 | 출처 번호 + 좌표 + Citation Map |
| 포맷팅 | 없음 | 4단 구조 (핵심/사실/상세/출처) |
| 할루시네이션 방지 | 없음 | 증거 기반 생성 + 자카드 검증 |

**추론**: 정확도와 신뢰성이 최우선 목표 → 다층 검증 체계

---

## 새로 추가된 기능

### 1. 대화 메모리 (Conversation Memory)
**근거: readme_new.md, backend/rag/conversation_summarizer.py (180줄)**

**기능**:
- 세션별 대화 요약 저장 (`conversation_summary`)
- 엔터티 추출 및 추적 (`recent_entities`)
- 이전 대화 컨텍스트 활용

**Before**: 단일 질의응답 (독립적 처리)
**After**: 멀티턴 대화 지원 (맥락 유지)

**추론**: "그 문서의 담당 부서는?" 같은 후속 질문 처리 가능

---

### 2. 질의 재작성 (Query Rewriting)
**근거: backend/rag/query_rewriter.py (510줄)**

**기능**:
- 대명사 해소 (Anaphora Resolution)
- 대화 컨텍스트 기반 질의 확장
- 이전 출처 참조

**예시**:
- 사용자: "그 프로그램은?" (대명사)
- 재작성: "홍티예술촌 프로그램은?" (명시적)

**Before**: 없음 (대명사 질의 처리 실패)
**After**: 대화 이력 기반 질의 보완

---

### 3. 주제 변화 감지 (Topic Change Detection)
**근거: backend/rag/topic_detector.py (255줄), commits.txt (#7, #24)**

**기능**:
- 질의 간 의미 유사도 계산
- 검색 점수 기반 주제 전환 감지
- 새 주제 시 문서 범위 확장

**예시**:
- 질문 1: "홍티예술촌의 위치는?" → 문서 A
- 질문 2: "감천문화마을은?" → 주제 변화 감지 → 문서 B 추가

**Before**: 없음 (고정된 문서 범위)
**After**: 동적 문서 범위 조정

---

### 4. 출처 일관성 (Citation Stability)
**근거: commits.txt (#21, #22), backend/routers/chat.py (라인 532-568)**

**기능**:
- 첫 답변의 `evidences` + `citation_map` 저장
- 후속 질문에서 동일한 매핑 재사용
- 출처 번호 고정 (예: "문서 A" = [1] 고정)

**Before**: 질문마다 출처 번호 변경 (혼란)
**After**: 세션 내 출처 번호 일관성 유지

**추론**: 사용자 경험 개선 (출처 추적 용이)

---

### 5. 문서 요약 (Document Summary)
**근거: commits.txt (#3, #5, #6), backend/services/document_summarizer.py (380줄)**

**기능**:
- 업로드 시 자동 요약 생성
- 비동기 백그라운드 처리
- 요약 데이터 JSON 저장

**Before**: 없음
**After**: 문서 미리보기 기능

---

### 6. 평가 시스템 (Evaluation)
**근거: readme_new.md, backend/eval/ 3개 파일 (697줄)**

**기능**:
- Golden QA 데이터셋 (100문항)
- EM, F1, Citation Accuracy 메트릭
- 실패 분석 리포트 자동 생성

**평가 기준**:
- EM (Exact Match) ≥ 95%
- F1 Score ≥ 99%
- Citation Accuracy ≥ 99.5%
- Hallucination = 0%

**Before**: 없음 (수동 테스트)
**After**: 자동화된 평가 프레임워크

---

### 7. 모니터링 (Observability)
**근거: commits.txt (#1), backend/utils/query_logger.py (626줄)**

**기능**:
- 쿼리별 메트릭 수집 (검색 시간, 생성 시간, 증거 수)
- 회상 실패율, Retrieval Gain@5 추적
- 대시보드 데이터 제공

**Before**: 없음
**After**: 실시간 품질 모니터링

---

## Before → After 종합 표

### 핵심 RAG 구성 요소

| 구성 요소 | 이전 (892fdc4) | 현재 (7c00a13) |
|----------|----------------|----------------|
| **문서 처리** | 단일 파일 (352줄) | 8개 모듈 (2,844줄) |
| **청킹** | 고정 크기 (1000자) | 의미 단위 (조항 경계, 표/각주 분리) |
| **정규화** | ❌ 없음 | ✅ 날짜/숫자/법령 정규화 |
| **검색** | Vector만 (ChromaDB) | BM25 + Vector + RRF |
| **리랭킹** | ❌ 없음 | ✅ jina-reranker (ONNX) |
| **생성** | LangChain 단순 프롬프트 | Evidence-Only + 5단계 검증 |
| **출처 추적** | ❌ 없음 | ✅ 출처 번호 + 좌표 + 일관성 |
| **대화 메모리** | ❌ 없음 | ✅ 요약 + 엔터티 추적 |
| **질의 재작성** | ❌ 없음 | ✅ 대명사 해소 |
| **주제 감지** | ❌ 없음 | ✅ 동적 문서 범위 |
| **평가** | ❌ 없음 | ✅ Golden QA + 메트릭 |
| **모니터링** | ❌ 없음 | ✅ 쿼리 로깅 + KPI |

### 시스템 특성

| 특성 | 이전 | 현재 |
|------|------|------|
| **UI** | Streamlit (서버 사이드) | React (SPA) |
| **API** | ❌ 없음 | ✅ FastAPI (RESTful + WebSocket) |
| **세션 관리** | ❌ 없음 | ✅ 다중 세션 지원 |
| **스트리밍** | ❌ 없음 | ✅ 실시간 응답 스트리밍 |
| **캐싱** | ❌ 없음 | ✅ Redis 캐시 |
| **OCR** | ❌ 없음 | ✅ Tesseract (한국어) |
| **오프라인 번들** | ❌ 없음 | ✅ 번들 생성 도구 |
| **테스트** | 4개 루트 파일 | 7개 체계화된 테스트 |

---

## 결론

### 기능 진화 방향

1. **단순 RAG → Evidence-Only RAG**: 할루시네이션 방지가 최우선
2. **단일 턴 → 멀티턴 대화**: 대화 메모리 + 질의 재작성
3. **고정 문서 범위 → 동적 범위**: 주제 감지 + 범위 조정
4. **프로토타입 → 프로덕션**: 평가, 모니터링, 캐싱, 오프라인 지원

### 추론: 사용 사례 변화

**이전 (892fdc4)**: PoC (Proof of Concept)
- 내부 실험용 프로토타입
- 기본적인 HWP 문서 질의응답
- 개발자 중심 인터페이스

**현재 (7c00a13)**: Production-Ready 시스템
- 실제 업무 환경 배포 가능
- 한국 공문서 전문 처리
- 엔터프라이즈급 기능 (평가, 모니터링, 출처 추적)
- 일반 사용자 친화적 UI

**근거 파일**: readme_old.md, readme_new.md, req_old.txt, req_new.txt, tree_new.txt, commits.txt
