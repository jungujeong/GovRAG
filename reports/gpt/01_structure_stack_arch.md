Generated on 2025-10-15 15:32 KST (rev2)

# TL;DR
- Streamlit+LangChain 단일앱(Old, 892fdc4) → FastAPI 백엔드+React 프런트(New, 7c00a13)로 전환 (근거: ../proj_old/app.py:1-40; ../proj_new/backend/main.py:15-41)
- 검색 스택: LangChain+Chroma(Old) → Whoosh(BM25)+Chroma+RRF+Jina 재랭커(New) (근거: ../proj_old/utils/rag_chain.py:1-30; ../proj_new/backend/rag/hybrid_retriever.py:1-60; ../proj_new/backend/rag/reranker.py:1-40)
- 파이프라인: 간단 체인(Old) → parse→chunk→index→retrieve→rerank→generate 모듈화(New) (근거: ../proj_old/utils/vector_store.py:1-40; ../proj_new/backend/processors/indexer.py:150-220)
- 운영/품질: 인덱스 무결성, 세션/요약, 모니터링 추가 (근거: ../proj_new/backend/utils/index_integrity.py:160-240; ../proj_new/backend/services/session_manager.py:1-60; ../proj_new/docs/MONITORING_GUIDE.md:1-30)
- 빌드/실행: Makefile 신설 및 명령 일원화 (근거: ../proj_new/Makefile:1-45 — Old 확인 불가, TODO: git ls-tree 892fdc4 | rg Makefile)

---

## 1) 프로젝트 구조 변경 (상위 3레벨 디렉터리 트리 비교)

| 항목 | 이전(892fdc4) | 현재(7c00a13) | 변경유형 | 대표 근거 |
|---|---|---|---|---|
| 앱 진입점 | app.py | backend/main.py | 이동/분리 | (근거: ../proj_old/app.py:1-40; ../proj_new/backend/main.py:15-41)
| 설정/Config | config/config.py | backend/config.py | 이동 | (근거: ../proj_old/config/config.py:1-40; ../proj_new/backend/config.py:1-40)
| RAG 구현 | utils/rag_chain.py, utils/vector_store.py | backend/rag/*, backend/processors/* | 대체/모듈화 | (근거: ../proj_old/utils/rag_chain.py:1-40; ../proj_new/backend/rag/hybrid_retriever.py:1-40)
| 프런트엔드 | (없음) | frontend/ (Vite+React) | 추가 | (근거: ../proj_new/frontend/package.json:1-22 — Old 확인 불가, TODO: git show 892fdc4:frontend/package.json)
| 데이터/인덱스 | data/vector_db | data/index, data/chroma | 변경 | (근거: ../proj_old/config/config.py:20-40; ../proj_new/backend/config.py:14-28)
| 빌드/실행 | (없음) | Makefile, scripts/* | 추가 | (근거: ../proj_new/Makefile:1-45 — Old 확인 불충분, TODO: git ls-tree 892fdc4 | rg Makefile)

- 주요 설정 파일 이동/분리: `config/config.py` → `backend/config.py`, 인덱스 경로가 `VECTOR_DB_PATH`(Old)에서 `WHOOSH_DIR/CHROMA_DIR`(New)로 세분화 (근거: ../proj_old/config/config.py:20-40; ../proj_new/backend/config.py:14-28)

## 1-1) 백엔드 라우트 비교(추가/변경/삭제)

| 메서드 | 경로 | 이전(892fdc4) | 현재(7c00a13) | 근거 |
|---|---|---|---|---|
| GET | /api/admin/config | 없음 — 근거 불충분 | 존재 | (근거: ../proj_new/backend/routers/admin.py:15-16; TODO Old: rg -n "@router" ../proj_old)
| POST | /api/query/ | 없음 — 근거 불충분 | 존재 | (근거: ../proj_new/backend/routers/query.py:102-106)
| GET | /api/query/test | 없음 — 근거 불충분 | 존재 | (근거: ../proj_new/backend/routers/query.py:75-80)
| POST | /api/chat/sessions | 없음 — 근거 불충분 | 존재 | (근거: ../proj_new/backend/routers/chat.py:335-342)
| POST | /api/chat/sessions/{id}/messages/stream | 없음 — 근거 불충분 | 존재 | (근거: ../proj_new/backend/routers/chat.py:1166-1172)
| GET | /api/documents/list | 없음 — 근거 불충분 | 존재 | (근거: ../proj_new/backend/routers/documents.py:322-328)

추가 채증 TODO: Old에는 REST 라우트가 없고 Streamlit UI였는지 확인 (명령: `git show 892fdc4:app.py | rg -n "st\.|@router"`).


## 2) 기술 스택 변경 표

| 영역 | 이전(892fdc4) | 현재(7c00a13) | 근거 |
|---|---|---|---|
| 프런트 프레임워크 | Streamlit UI 내장 | React 18 | (근거: ../proj_old/app.py:1-40; ../proj_new/frontend/package.json:1-22)
| 번들러 | (없음) | Vite 5 | (근거: ../proj_new/frontend/package.json:1-22 — Old 확인 불충분, TODO: git show 892fdc4:frontend/package.json)
| 상태관리 | (없음) | Zustand 4 | (근거: ../proj_new/frontend/package.json:10-22)
| 백엔드 프레임워크 | (없음/Streamlit 런타임) | FastAPI 0.115.6 | (근거: ../proj_old/app.py:1-40; ../proj_new/requirements.txt:1-5)
| 서버 | (Streamlit) | Uvicorn 0.34.0 | (근거: ../proj_new/requirements.txt:1-5)
| 임베딩 | nomic/all-minilm 등 문자열 구성 | Sentence-Transformers 3.3.1 (BGE-M3 등) | (근거: ../proj_old/config/config.py:40-70; ../proj_new/backend/rag/embedder.py:18-40)
| 벡터DB | Chroma 0.4.13 | Chroma 0.5.23 | (근거: ../proj_old/requirements.txt:1-40; ../proj_new/requirements.txt:1-10)
| 검색 | rank-bm25 | Whoosh 2.7.4 + RRF 결합 | (근거: ../proj_old/requirements.txt:1-40; ../proj_new/backend/rag/whoosh_bm25.py:1-40; ../proj_new/backend/rag/hybrid_retriever.py:120-180)
| 재랭킹 | (없음) | Jina reranker + onnxruntime | (근거: ../proj_new/backend/rag/reranker.py:1-40; ../proj_new/requirements.txt:6-12)
| 생성 | LangChain OllamaLLM | Ollama Chat API(HTTPX) | (근거: ../proj_old/utils/rag_chain.py:20-40; ../proj_new/backend/rag/generator_ollama.py:1-40)

의존성 비교(요약)

| 패키지 | 이전 버전 | 현재 버전 | 근거 |
|---|---|---|---|
| fastapi | - | 0.115.6 | (근거: ../proj_new/requirements.txt:1-5)
| uvicorn | - | 0.34.0 | (근거: ../proj_new/requirements.txt:1-5)
| streamlit | ≥1.24.0 | - | (근거: ../proj_old/requirements.txt:1-21)
| langchain | ≥0.0.267 | - | (근거: ../proj_old/requirements.txt:1-21)
| chromadb | ≥0.4.13 | 0.5.23 | (근거: ../proj_old/requirements.txt:1-21; ../proj_new/requirements.txt:1-12)
| whoosh | - | 2.7.4 | (근거: ../proj_new/requirements.txt:1-8)
| sentence-transformers | ≥2.2.2 | 3.3.1 | (근거: ../proj_old/requirements.txt:1-21; ../proj_new/requirements.txt:4-10)

추가 채증 TODO: NPM 의존성 Old 부재 확인 (명령: `git show 892fdc4:frontend/package.json`).


## 3) 아키텍처 Before/After 텍스트 도식

- Old: [UI(Streamlit)] → [LangChain 단일앱(SimpleRAGChain)] → [Chroma] (근거: ../proj_old/app.py:1-40; ../proj_old/utils/rag_chain.py:1-40; ../proj_old/utils/vector_store.py:1-40)
- New: [React/Vite] → [FastAPI Routers] → [Hybrid Retriever(Whoosh+Chroma)] → [Reranker] → [Ollama] (근거: ../proj_new/frontend/package.json:1-22; ../proj_new/backend/routers/chat.py:335-360; ../proj_new/backend/rag/hybrid_retriever.py:1-60; ../proj_new/backend/rag/reranker.py:1-40; ../proj_new/backend/rag/generator_ollama.py:1-40)

설명: 컨트롤러/서비스/인프라 계층으로 분리하고, 검색은 BM25+Vector를 RRF로 결합 후 재랭킹·생성 단계로 이어지는 파이프라인으로 확장 (근거: ../proj_new/backend/routers/chat.py:1-60; ../proj_new/backend/services/session_manager.py:1-60)


## 4) 이전(892fdc4) → 현재(7c00a13) 비교표(요약)

| 항목 | 이전(892fdc4) | 현재(7c00a13) | 근거 |
|---|---|---|---|
| 앱 프레임워크 | Streamlit 단일앱 | FastAPI 백엔드 | (근거: ../proj_old/app.py:1-40; ../proj_new/backend/main.py:15-41)
| 프런트엔드 | 내장 UI | React+Vite 별도 프런트 | (근거: ../proj_old/app.py:1-40; ../proj_new/frontend/package.json:1-22)
| 검색 | LangChain+Chroma | Whoosh+Chroma+RRF | (근거: ../proj_old/utils/rag_chain.py:1-30; ../proj_new/backend/rag/hybrid_retriever.py:1-60)
| 재랭킹 | (없음) | Jina reranker(ONNX/PyTorch) | (근거: ../proj_new/backend/rag/reranker.py:1-40)
| 생성 | LangChain OllamaLLM | Ollama Chat API | (근거: ../proj_old/utils/rag_chain.py:20-40; ../proj_new/backend/rag/generator_ollama.py:1-40)
| 파이프라인 | 간단 청킹/검색 | processors+rag 모듈 파이프라인 | (근거: ../proj_old/utils/vector_store.py:1-40; ../proj_new/backend/processors/indexer.py:150-260)



## 5) 빌드/실행/환경 변화

| 항목 | 이전(892fdc4) | 현재(7c00a13) | 근거 |
|---|---|---|---|
| 빌드/실행 | (Streamlit 실행 추정) — 근거 불충분 | Makefile 제공: setup/install/index/run/qa | (근거: ../proj_new/Makefile:1-45; TODO Old: run 명령 확인 `rg -n "streamlit run" ../proj_old`)
| 환경 변수 | OLLAMA_MODEL, VECTOR_DB_PATH, CHUNK_SIZE/OVERLAP | APP_PORT, WHOOSH_DIR/CHROMA_DIR, EMBED_BATCH, RERANKER_ID 등 | (근거: ../proj_old/config/config.py:1-80; ../proj_new/backend/config.py:1-40)

## 6) LOC/언어 통계(요약)

| 스냅샷 | Python 파일수/LOC | JS/TS 파일수/LOC | 근거 |
|---|---|---|---|
| Old(892fdc4) | 22 / 6,685 | 0 / 0 | (근거: PR#29; TODO: 집계 명령 `git ls-tree -r 892fdc4 --name-only | grep -E "\.py$"` + `git show 892fdc4:<path> | wc -l`)
| New(7c00a13) | 75 / 21,164 | 47 / 11,483 | (근거: ../proj_new/frontend/src/*.jsx:1-40; ../proj_new/backend/**/*.py:1-40; TODO: 동일 집계 명령 실행)
