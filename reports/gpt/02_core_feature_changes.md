Generated on 2025-10-15 15:32 KST (rev2)

# 핵심 기능 변화 분석

비교 기준: Old(892fdc4) ↔ New(7c00a13)

## 1) RAG 파이프라인 (이전→현재)

| 단계 | 이전(892fdc4) | 현재(7c00a13) | 파라미터/경로 | 근거 |
|---|---|---|---|---|
| ingest | Streamlit 업로드 핸들러 | REST 업로드(`/api/documents/upload(-batch)`) | - | (근거: ../proj_old/app.py:1-40; ../proj_new/backend/routers/documents.py:183-200; ../proj_new/backend/routers/documents.py:250-270)
| parse | utils.DocumentProcessor(HWP/PDF) | processors.HWPStructureParser/PDFHybridProcessor | Old: HWP extractor; New: 구조 파서 | (근거: ../proj_old/utils/document_processor.py:1-60; ../proj_new/backend/processors/hwp_structure_parser.py:1-60; ../proj_new/backend/processors/pdf_hybrid_processor.py:1-40)
| chunk | Recursive splitter | StructureChunker(표/각주 분리) | Old CHUNK_SIZE=800, OVERLAP=150; New CHUNK_TOKENS=2048, OVERLAP=256 | (근거: ../proj_old/config/config.py:20-40; ../proj_new/backend/config.py:14-28; ../proj_new/backend/processors/structure_chunker.py:1-40)
| index | Chroma only | Whoosh(BM25)+Chroma | Old `VECTOR_DB_PATH`; New `WHOOSH_DIR/CHROMA_DIR` | (근거: ../proj_old/config/config.py:20-40; ../proj_new/backend/config.py:14-28)
| retrieve | Chroma similarity | Hybrid(RRF: BM25+Vector) | RRF_K, W_BM25/W_VECTOR | (근거: ../proj_new/backend/rag/hybrid_retriever.py:1-40; ../proj_new/backend/rag/hybrid_retriever.py:120-180; ../proj_new/backend/config.py:22-40)
| rerank | 없음 | Jina reranker(ONNX/PyTorch) | `RERANKER_ID`, `RERANK_USE_ONNX` | (근거: ../proj_new/backend/rag/reranker.py:1-40; ../proj_new/backend/config.py:30-36)
| generate | LangChain OllamaLLM | Ollama Chat API(HTTPX) | `OLLAMA_HOST`, 모델 | (근거: ../proj_old/utils/rag_chain.py:20-40; ../proj_new/backend/rag/generator_ollama.py:1-40)

트레이드오프: 단계 증가로 초기화/관찰 지점이 늘어남 (근거: ../proj_new/backend/main.py:41-90). 향후 개선: make qa·metrics 자동 집계로 단계별 SLA 계측 도입 (근거: ../proj_new/docs/MONITORING_GUIDE.md:1-30).

## 2) 문서 처리(포맷/전처리/메타데이터) (이전→현재)

| 항목 | 이전(892fdc4) | 현재(7c00a13) | 근거 |
|---|---|---|---|
| 포맷 | HWP/PDF/텍스트 | HWP/PDF(구조 파서), 표/각주 분리 | (근거: ../proj_old/utils/document_processor.py:1-60; ../proj_new/backend/processors/structure_chunker.py:1-40)
| 전처리 | 간단 직렬화·키워드 | 인덱싱 단계 특수문자 정제(PUA 제거)·중복청크 제거 | (근거: ../proj_new/backend/processors/indexer.py:210-260; ../proj_new/FIXES_2025-10-14.md:175-240)
| 메타데이터 | source, chunk_index 등 | doc_id/page/start/end/type/section_or_page | (근거: ../proj_old/utils/vector_store.py:80-120; ../proj_new/backend/rag/chroma_store.py:60-120)

트레이드오프: 정제 강도↑ 시 원문 보존성↓ — 근거 불충분. TODO: 정제 전후 BLEU/TER 측정 스크립트 추가(`python tools/text_compare.py`).

## 3) 검색/임베딩/재랭킹 결합 방식

| 단계 | 이전(892fdc4) | 현재(7c00a13) | 파라미터 | 근거 |
|---|---|---|---|---|
| BM25 | rank-bm25 | Whoosh BM25F | TOPK_BM25 | (근거: ../proj_old/requirements.txt:1-21; ../proj_new/backend/rag/whoosh_bm25.py:1-40; ../proj_new/backend/config.py:22-30)
| Vector | Chroma sim | Chroma(코사인) | TOPK_VECTOR | (근거: ../proj_new/backend/rag/chroma_store.py:80-140; ../proj_new/backend/config.py:22-30)
| RRF | - | 1/(k+rank) 합산 | RRF_K, W_* 가중치 | (근거: ../proj_new/backend/rag/hybrid_retriever.py:140-200; ../proj_new/backend/config.py:22-30)
| Rerank | - | Jina reranker | TOPK_RERANK | (근거: ../proj_new/backend/rag/reranker.py:120-180; ../proj_new/backend/config.py:22-36)

트레이드오프: 가중치/임계치 튜닝 실패 시 정밀도/재현율 균형 저하 (근거: ../proj_new/backend/rag/hybrid_retriever.py:260-320). 향후 개선: grid-search 스크립트 추가(TODO: `python tools/rrf_grid_search.py`).

## 4) 추가/제거 기능 목록

| 유형 | 항목 | 설명 | 근거 |
|---|---|---|---|
| 추가 | 세션 영속/비동기 저장 | 세션 JSON 저장, 저장 큐/백그라운드 태스크 | (근거: ../proj_new/backend/services/session_manager.py:1-60; ../proj_new/backend/services/session_manager.py:120-200)
| 추가 | Topic Change(0.03) | Two-Stage Retrieval로 토픽전환 감지 | (근거: ../proj_new/backend/rag/two_stage_retrieval.py:38-56; ../proj_new/backend/rag/two_stage_retrieval.py:166-176)
| 추가 | 인덱스 무결성 | 백업/스냅샷/복구 컨텍스트 | (근거: ../proj_new/backend/utils/index_integrity.py:160-240; ../proj_new/backend/utils/index_integrity.py:240-260)
| 제거/대체 | LangChain 체인 | 모듈형 RAG(Whoosh/Chroma/RRF/Jina/Ollama) | (근거: ../proj_old/utils/rag_chain.py:1-40; ../proj_new/backend/rag/hybrid_retriever.py:1-40)
| 제거/대체 | SimpleIndexer | 비활성/경고, 실제 파이프라인만 사용 | (근거: ../proj_new/backend/processors/simple_indexer.py:25-46; ../proj_new/HALLUCINATION_FIX_REPORT.md:35-45)

사유(PR/Issue): Streamlit→FastAPI 전환 및 환각 근본 원인 제거(테스트 데이터) — (근거: PR#29; ../proj_new/FIXES_2025-10-14.md:9-40).

## 5) 트레이드오프 및 향후 개선 요약

- 트레이드오프: 구성요소 증가로 복잡도↑, 초기화/관찰점↑ (근거: ../proj_new/backend/main.py:41-90)
- 향후 개선: 단계별 SLA 측정·튜닝 자동화(`make qa` 연동), 파라미터 스윕 도구 추가 (근거: ../proj_new/Makefile:35-70)

