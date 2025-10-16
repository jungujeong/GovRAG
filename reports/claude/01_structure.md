# 프로젝트 구조 & 기술 스택 비교

<!-- 생성 시간: 2025-10-15 15:50 -->

## TL;DR (3줄 요약)

1. **아키텍처 대전환**: Streamlit 단일 앱 → FastAPI(백엔드) + React(프론트엔드) 분리 구조로 완전 재설계
2. **파일 규모 3배 증가**: 30개 파일 → 100개 파일, 모듈화된 RAG 파이프라인 구축 (backend/rag/, processors/)
3. **기술 스택 현대화**: LangChain 제거, Whoosh(BM25) + ChromaDB 하이브리드 검색, Evidence-Only 생성 방식 도입

---

## 디렉토리 구조 변화

### 이전 버전 (892fdc4) - 단순 구조
**근거: tree_old.txt**

```
프로젝트 루트 (30개 파일)
├── app.py (1,189줄)           # Streamlit 메인 앱
├── app_enhanced.py (1,262줄)  # 향상된 버전
├── config/                     # 설정 모듈
│   ├── __init__.py
│   ├── config.py (98줄)
│   └── improved_models.md
├── utils/                      # 유틸리티 (단일 모듈)
│   ├── document_processor.py (352줄)
│   ├── enhanced_document_processor.py (293줄)
│   ├── rag_chain.py (611줄)
│   ├── vector_store.py (533줄)
│   └── hwplib/                 # HWP 처리
├── backup/vector_db/           # 벡터 DB 백업
└── test_*.py (4개 테스트 파일)
```

**특징**:
- 단일 진입점 (app.py)
- 3개 주요 디렉토리 (config, utils, backup)
- 테스트 파일 루트에 분산

---

### 현재 버전 (7c00a13) - 모듈화 구조
**근거: tree_new.txt, git_stat.txt**

```
프로젝트 루트 (100개 파일)
├── backend/                    # 백엔드 API 서버
│   ├── main.py (112줄)         # FastAPI 진입점
│   ├── config.py (81줄)        # 통합 설정
│   ├── routers/                # API 라우터 (5개 파일)
│   │   ├── chat.py (2,029줄)  # 채팅 핵심 로직
│   │   ├── documents.py (728줄)
│   │   ├── query.py (403줄)
│   │   ├── admin.py (399줄)
│   │   └── sessions.py (400줄)
│   ├── processors/             # 문서 처리 (8개 파일)
│   │   ├── indexer.py (394줄)
│   │   ├── hwp_structure_parser.py (290줄)
│   │   ├── pdf_hybrid_processor.py (295줄)
│   │   ├── structure_chunker.py (508줄)
│   │   ├── normalizer_govkr.py (233줄)
│   │   └── directive_extractor_*.py (1,310줄)
│   ├── rag/                    # RAG 파이프라인 (20개 파일)
│   │   ├── hybrid_retriever.py (580줄)
│   │   ├── generator_ollama.py (339줄)
│   │   ├── embedder.py (101줄)
│   │   ├── whoosh_bm25.py (303줄)
│   │   ├── chroma_store.py (260줄)
│   │   ├── reranker.py (217줄)
│   │   ├── evidence_enforcer.py (271줄)
│   │   ├── citation_tracker.py (813줄)
│   │   ├── answer_formatter.py (713줄)
│   │   ├── conversation_summarizer.py (180줄)
│   │   ├── query_rewriter.py (510줄)
│   │   ├── topic_detector.py (255줄)
│   │   └── prompt_templates.py (239줄)
│   ├── services/               # 비즈니스 로직 (3개 파일)
│   │   ├── session_manager.py (364줄)
│   │   ├── title_generator.py (166줄)
│   │   └── document_summarizer.py (380줄)
│   ├── utils/                  # 유틸리티 (12개 파일)
│   │   ├── query_logger.py (626줄)
│   │   ├── cache_manager.py (192줄)
│   │   └── index_manager.py (202줄)
│   └── eval/                   # 평가 시스템 (3개 파일)
│       ├── golden_evaluator.py (262줄)
│       └── metrics.py (205줄)
│
├── frontend/                   # React 프론트엔드
│   ├── src/
│   │   ├── App.jsx
│   │   ├── AppMediumClean.jsx (1,280줄)
│   │   ├── components/ (15개 컴포넌트)
│   │   ├── services/ (API 클라이언트)
│   │   ├── hooks/ (5개 훅)
│   │   ├── stores/ (상태 관리)
│   │   └── styles/ (6개 CSS 파일)
│   ├── package.json
│   └── vite.config.js
│
├── tests/                      # 체계화된 테스트
│   ├── test_retrieval.py (172줄)
│   ├── test_generation.py (175줄)
│   ├── test_citation.py (193줄)
│   └── test_conversation_*.py (3개 파일)
│
├── tools/                      # 개발 도구
│   ├── bundle_creator.py (230줄)
│   ├── integrity_verifier.py (203줄)
│   └── validate_installation.py (244줄)
│
├── data/                       # 데이터 디렉토리
│   ├── documents/
│   ├── index/
│   ├── chroma/
│   └── golden/ (평가 데이터셋)
│
├── .claude/                    # Claude Code 설정
│   ├── agents/ (17개 에이전트)
│   └── commands/
│
└── 문서/스크립트 (15개 MD, 11개 스크립트)
```

**특징**:
- 백엔드/프론트엔드 완전 분리
- 7개 주요 디렉토리 (backend, frontend, tests, tools, data, docs, scripts)
- RAG 파이프라인 20개 모듈로 세분화
- 체계적인 테스트 및 도구 지원

---

## 의존성 변화 표

### Python 패키지 비교
**근거: req_old.txt vs req_new.txt**

| 항목 | 이전 (20개) | 현재 (27개) | 변화 |
|------|------------|------------|------|
| **웹 프레임워크** | Streamlit | FastAPI + Uvicorn | ⚡ 전환 |
| **LLM 프레임워크** | LangChain (8개 패키지) | **제거** | ❌ 삭제 |
| **검색 엔진** | ChromaDB만 | **Whoosh** + ChromaDB | ➕ 추가 |
| **임베딩** | sentence-transformers | sentence-transformers (업그레이드) | ⬆️ 2.2.2 → 3.3.1 |
| **PDF 처리** | PyMuPDF + pdfplumber | PyMuPDF + **pytesseract** | 🔄 OCR 추가 |
| **검색 알고리즘** | rank-bm25 | **Whoosh** (내장 BM25) | 🔄 교체 |
| **기타 추가** | - | rapidfuzz, onnxruntime, httpx, pydantic, aiofiles, redis, Pillow, tiktoken, opencv-python, psutil | ➕ 11개 |

**주요 변경사항**:
- ❌ **LangChain 제거**: langchain, langchain_ollama, langchain_community, langchain_chroma, langchain-text-splitters (5개 제거)
- ➕ **FastAPI 생태계 추가**: fastapi, uvicorn, pydantic, httpx, aiofiles
- ➕ **검색 엔진 강화**: Whoosh (BM25), rapidfuzz (유사도)
- ➕ **성능/모니터링**: onnxruntime (리랭커), psutil (시스템 모니터링), redis (캐시)
- ➕ **이미지 처리**: Pillow, opencv-python, pytesseract (OCR)

### 프론트엔드 패키지
**근거: pkg_old.json (빈 파일) vs pkg_new.json**

| 항목 | 이전 | 현재 |
|------|------|------|
| **UI 프레임워크** | Streamlit (백엔드에 포함) | **React 18** + Vite |
| **상태 관리** | 없음 | Zustand |
| **HTTP 클라이언트** | 없음 | Axios |
| **Markdown 렌더링** | 없음 | react-markdown |
| **스타일링** | 없음 | Tailwind CSS |
| **파일 업로드** | 없음 | react-dropzone |
| **빌드 도구** | 없음 | Vite + esbuild |

**추론: 이전에는 프론트엔드가 없었거나 별도 저장소였음 → 현재는 monorepo 구조로 통합**

---

## 주요 변경사항 (Bullet Points)

### 1. 아키텍처 변화
**근거: git_stat.txt (app.py 1,189줄 삭제, backend/main.py 112줄 추가)**

- ❌ **Streamlit 단일 앱 제거** (app.py, app_enhanced.py 삭제: 2,451줄)
- ✅ **FastAPI 백엔드 생성** (backend/ 디렉토리: 17,000+ 줄)
- ✅ **React 프론트엔드 추가** (frontend/ 디렉토리: 10,000+ 줄)
- ✅ **API 기반 통신**: RESTful + WebSocket 지원

### 2. RAG 파이프라인 재설계
**근거: git_stat.txt (utils/ 삭제, backend/rag/ 추가)**

- ❌ **LangChain 의존성 제거**: 모든 langchain_* 패키지 삭제
- ✅ **하이브리드 검색 구현**: Whoosh(BM25) + ChromaDB(Vector) + RRF 융합
- ✅ **Evidence-Only 생성**: 할루시네이션 방지 프롬프트 + 후검증
- ✅ **리랭킹 추가**: jina-reranker-v2 (ONNX)
- ✅ **모듈화**: 20개 RAG 컴포넌트 (이전: 4개 유틸리티)

### 3. 문서 처리 강화
**근거: backend/processors/ 디렉토리 생성 (1,935줄)**

- ✅ **구조 보존 파싱**: hwp_structure_parser.py, pdf_hybrid_processor.py
- ✅ **의미 단위 청킹**: structure_chunker.py (508줄)
- ✅ **한국어 정규화**: normalizer_govkr.py (233줄)
- ✅ **공문서 구조 추출**: directive_extractor_whitelist_final.py (935줄)
- ✅ **OCR 지원**: pytesseract 추가 (한국어 지원)

### 4. 대화 메모리 및 컨텍스트
**근거: backend/rag/conversation_summarizer.py, query_rewriter.py, topic_detector.py**

- ✅ **대화 요약**: ConversationSummarizer (180줄)
- ✅ **질의 재작성**: QueryRewriter (510줄) - 대명사 해소
- ✅ **주제 변화 감지**: TopicDetector (255줄)
- ✅ **문서 범위 해결**: DocScopeResolver (452줄)

### 5. 평가 및 모니터링
**근거: backend/eval/, backend/utils/query_logger.py**

- ✅ **Golden QA 평가**: golden_evaluator.py (262줄), metrics.py (205줄)
- ✅ **쿼리 로깅**: query_logger.py (626줄) - 상세 메트릭 수집
- ✅ **인덱스 관리**: index_manager.py (202줄) - 백업/복구/검증
- ✅ **캐시 시스템**: cache_manager.py (192줄)

### 6. 프론트엔드 기능
**근거: frontend/src/ 디렉토리**

- ✅ **세션 관리**: 다중 대화 세션 지원
- ✅ **출처 표시**: CitationPopup, DocumentDetailsPopup
- ✅ **스트리밍 응답**: WebSocket + Server-Sent Events
- ✅ **문서 요약**: SummaryPopup 컴포넌트
- ✅ **모니터링 대시보드**: MonitoringDashboard.jsx (384줄)

### 7. 개발 인프라
**근거: Makefile, tools/, .claude/**

- ✅ **빌드 자동화**: Makefile (117줄) - setup, install, index, run, qa
- ✅ **오프라인 번들**: bundle_creator.py (230줄)
- ✅ **설치 검증**: validate_installation.py (244줄)
- ✅ **무결성 검증**: integrity_verifier.py (203줄)
- ✅ **Claude Code 통합**: 17개 전문 에이전트 설정

---

## 통계 요약

| 항목 | 이전 | 현재 | 변화율 |
|------|------|------|--------|
| 파일 수 | 30 | 100+ | **+233%** |
| 총 코드 라인 | ~7,031 | ~51,950 | **+639%** |
| Python 패키지 | 20 | 27 | +35% |
| 주요 디렉토리 | 3 | 7 | +133% |
| 테스트 파일 | 4 (루트) | 7 (tests/) | +75% |
| RAG 모듈 | 4 (utils/) | 20 (backend/rag/) | **+400%** |
| API 라우터 | 0 | 5 | 신규 |
| 프론트엔드 컴포넌트 | 0 | 15+ | 신규 |

---

## 결론

**추론: 892fdc4 → 7c00a13 버전은 단순한 개선이 아닌 완전한 재설계 (Full Rewrite)**

1. **아키텍처**: 모놀리식 Streamlit 앱 → 마이크로서비스 아키텍처 (API + SPA)
2. **기술 스택**: LangChain 의존성 제거 → 순수 Python + 특화된 검색 엔진
3. **확장성**: 단일 파일 → 100+ 모듈화된 파일, 테스트/도구/문서 체계화
4. **품질**: Evidence-Only RAG, 대화 메모리, 평가 시스템 등 엔터프라이즈급 기능 추가

**근거 파일**: tree_old.txt, tree_new.txt, git_stat.txt, req_old.txt, req_new.txt, pkg_new.json
