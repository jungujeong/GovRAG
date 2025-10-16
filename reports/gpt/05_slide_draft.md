Generated on 2025-10-15 15:32 KST (rev2)

# 발표 초안 (13장)

## 슬라이드 1. 전체 개요 (TL;DR)
- Old(892fdc4): Streamlit+LangChain 체계(단일앱) (근거: ../proj_old/app.py:1-40)
- New(7c00a13): FastAPI+React, Whoosh+Chroma+RRF+Jina+Ollama (근거: ../proj_new/backend/main.py:15-41; ../proj_new/frontend/package.json:1-22)
- 인덱싱 정제/무결성·세션/요약·모니터링 추가 (근거: ../proj_new/backend/utils/index_integrity.py:160-240; ../proj_new/docs/MONITORING_GUIDE.md:1-30)
시간: 45초

## 슬라이드 2. 구조/스택 요약
- 백엔드 계층: Routers/Services/RAG/Processors 분리 (근거: ../proj_new/backend/routers/chat.py:1-40; ../proj_new/backend/services/session_manager.py:1-40)
- 프런트엔드: React+Vite+Zustand, 스트리밍 처리 (근거: ../proj_new/frontend/package.json:1-22; ../proj_new/frontend/src/services/chatAPI.js:70-160)
- 의존성: whoosh/onnxruntime/fastapi 등 추가 (근거: ../proj_new/requirements.txt:1-27)
시간: 45초

## 슬라이드 3. RAG Before/After 도식
- Before: [Streamlit UI] → [LangChain(SimpleRAGChain)] → [Chroma] (근거: ../proj_old/utils/rag_chain.py:1-40)
- After: [React/Vite] → [FastAPI Routers] → [Hybrid(Whoosh+Chroma, RRF)] → [Reranker(Jina)] → [Ollama] (근거: ../proj_new/backend/rag/hybrid_retriever.py:1-60; ../proj_new/backend/rag/reranker.py:1-40; ../proj_new/backend/rag/generator_ollama.py:1-40)
시간: 60초

## 슬라이드 4. 파이프라인 단계별 변화
- chunk 파라미터: Old(800/150) → New(2048/256) (근거: ../proj_old/config/config.py:20-40; ../proj_new/backend/config.py:14-28)
- index: Old(Chroma) → New(Whoosh+Chroma) (근거: ../proj_old/config/config.py:20-40; ../proj_new/backend/config.py:14-28)
- rerank: Old(없음) → New(Jina) (근거: ../proj_new/backend/rag/reranker.py:1-40)
시간: 45초

## 슬라이드 5. 검색/결합 방식
- BM25F(Whoosh) + Vector(Chroma) → RRF 가중 결합 (근거: ../proj_new/backend/rag/hybrid_retriever.py:140-200)
- 가중치/TopK/RRF_K 설정화 (근거: ../proj_new/backend/config.py:22-40)
시간: 40초

## 슬라이드 6. 문서 처리 개선
- 구조 인지형 청킹(표/각주), 텍스트 정제, 중복 제거 (근거: ../proj_new/backend/processors/structure_chunker.py:1-40; ../proj_new/backend/processors/indexer.py:210-260)
- 메타데이터 강화(doc_id/page/start/end/type) (근거: ../proj_new/backend/rag/chroma_store.py:60-120)
시간: 40초

## 슬라이드 7. 세션/요약/재작성
- 세션 영속/비동기 저장 큐, 요약/엔터티 메모리 (근거: ../proj_new/backend/services/session_manager.py:120-220)
- 질의 재작성/토픽 감지/문서 범위 결정 (근거: ../proj_new/backend/rag/query_rewriter.py:1-40; ../proj_new/backend/rag/two_stage_retrieval.py:38-56)
시간: 50초

## 슬라이드 8. 모니터링/로깅
- QueryLog·성능/품질 메트릭·대시보드 문서화 (근거: ../proj_new/docs/MONITORING_GUIDE.md:1-80)
- admin 라우트로 로그/통계 조회 (근거: ../proj_new/backend/routers/admin.py:185-236)
시간: 40초

## 슬라이드 9. 코드 품질 패턴
- safe_index_operation으로 무결성 보장 (근거: ../proj_new/backend/utils/index_integrity.py:240-260)
- 전역 예외 처리·degrade 헬스체크 (근거: ../proj_new/backend/main.py:60-90)
시간: 40초

## 슬라이드 10. 성능/정확도 개선 표

| 항목 | Before(892fdc4) | After(7c00a13) | 근거 |
|---|---|---|---|
| 인덱싱 안정성 | 단순 색인 | 무결성 스냅샷/백업/복구 | (근거: ../proj_new/backend/utils/index_integrity.py:160-240)
| 스트리밍 UX | (Streamlit) | 부분 응답 파싱/에러 전파 | (근거: ../proj_new/frontend/src/services/chatAPI.js:100-160)
| Citation 일치 | 불일치 사례 | 파서 재작성으로 동기화 | (근거: ../proj_new/FIXES_2025-10-14.md:27-80)
| Topic Change | 기본 | 0.03 임계치로 민감도↑ | (근거: ../proj_new/backend/rag/two_stage_retrieval.py:38-56)

시간: 50초

## 슬라이드 11. Breaking Changes (표)

| 항목 | 내용 | 근거 |
|---|---|---|
| 프레임워크 전환 | Streamlit→FastAPI | (근거: ../proj_old/app.py:1-40; ../proj_new/backend/main.py:15-41)
| RAG 구성 | LangChain 체인→모듈형 RAG | (근거: ../proj_old/utils/rag_chain.py:1-40; ../proj_new/backend/rag/*:1-40)
| 응답 후처리 | 과도 후처리 비활성 | (근거: ../proj_new/backend/rag/response_postprocessor.py:14-22)
| SimpleIndexer | 가짜 데이터 제거·비활성 | (근거: ../proj_new/backend/processors/simple_indexer.py:25-46)

시간: 45초

## 슬라이드 12. Migration Checklist (표)

| 단계 | 액션 | 근거 |
|---|---|---|
| Node 환경 | Node 18 LTS 적용, 패키지 재설치 | (근거: ../proj_new/FIXES_2025-10-14.md:232-274)
| 데이터 | SimpleIndexer 기반 테스트 데이터 제거 | (근거: ../proj_new/HALLUCINATION_FIX_REPORT.md:35-45)
| 인덱스 | 무결성 스냅샷 초기화/백업 | (근거: ../proj_new/backend/utils/index_integrity.py:160-200)
| 파라미터 | .env/Config 검증(가중치/TopK/RRF_K) | (근거: ../proj_new/backend/config.py:22-40)

시간: 45초

## 슬라이드 13. Q&A (예상 5)
1) 왜 Post-Processing을 끄나요?
- LLM 출력 손상 방지를 위해 인덱싱 단계 정제로 전환 (근거: ../proj_new/backend/rag/response_postprocessor.py:14-22; ../proj_new/FIXES_2025-10-14.md:175-240)

2) RRF/임계치 추천값은?
- 기본값 제공, 도메인별 grid-search로 튜닝 (근거: ../proj_new/backend/config.py:22-40; ../proj_new/backend/rag/hybrid_retriever.py:140-200)

3) Citation 불일치 재발 방지는?
- LLM 기존 [n] 파싱→evidence 매핑, 소스 수 동기화 (근거: ../proj_new/FIXES_2025-10-14.md:27-74)

4) 인덱스 손상 시 어떻게 복구하나요?
- 백업에서 복구하는 컨텍스트 매니저 제공 (근거: ../proj_new/backend/utils/index_integrity.py:240-260)

5) 오프라인/폐쇄망에서도 가능한가요?
- 로컬 모델/DB 기반으로 작동(Chroma/Whoosh/Ollama) (근거: ../proj_new/backend/rag/chroma_store.py:1-40; ../proj_new/backend/rag/whoosh_bm25.py:1-40)

시간: 60초

