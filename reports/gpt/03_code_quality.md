Generated on 2025-10-15 15:32 KST (rev2)

# 코드 품질 및 안정성 개선 분석

## 1) 성능 최적화(핫패스 지연/처리량)

| 영역 | 변경점 | 기대효과 | 정량(실측) | 근거 | 측정 TODO |
|---|---|---|---|---|---|
| 인덱싱 작업 | safe_index_operation(백업→작업→스냅샷) | 장애시 롤백, 재색인 안정성↑ | 근거 불충분 | (근거: ../proj_new/backend/utils/index_integrity.py:240-260) | pytest -k indexer -q; python -m timeit 'indexer.index_chunks' |
| 임베딩 | embed_batch(batch_size=EMBED_BATCH) | 벡터화 처리량↑ | 근거 불충분 | (근거: ../proj_new/backend/rag/embedder.py:40-70) | pytest -k embed -q --durations=10 |
| 생성 | HTTPX 스트리밍/타임아웃 설정 | 느린 모델/네트워크에서 체감응답 개선 | 근거 불충분 | (근거: ../proj_new/backend/rag/generator_ollama.py:1-40; ../proj_new/backend/rag/generator_ollama.py:200-260) | uvicorn main:app --log-level debug |

## 2) 에러 핸들링/로깅 (실코드 예시)

전역 예외 처리와 헬스체크 degrade 응답으로 안전한 실패를 보장합니다. (근거: ../proj_new/backend/main.py:60-90)

```python
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )
```

또한, 생성 실패 시 사용자 친화 메시지로 치환합니다. (근거: ../proj_new/backend/rag/generator_ollama.py:60-100)

```python
except Exception as e:
    logger.error(f"Generation failed: {str(e)}")
    import traceback
    logger.error(f"Traceback: {traceback.format_exc()}")
    return {
        "error": str(e),
        "answer": "죄송합니다. 응답 생성 중 오류가 발생했습니다.",
        "key_facts": [],
        "sources": []
    }
```

## 3) 구조 개선 (레이어드/지연초기화)

지연 초기화로 스타트업 비용↓, 테스트 격리성↑ (근거: ../proj_new/backend/routers/chat.py:21-40)

```python
def get_retriever():
    global retriever
    if retriever is None:
        from rag.hybrid_retriever import HybridRetriever
        retriever = HybridRetriever()
    return retriever

def get_reranker():
    global reranker
    if reranker is None:
        from rag.reranker import Reranker
        reranker = Reranker()
    return reranker
```

하이브리드 검색은 검색→융합→필터→다양성 보장을 단계화했습니다. (근거: ../proj_new/backend/rag/hybrid_retriever.py:60-120; ../proj_new/backend/rag/hybrid_retriever.py:180-240)

## 4) 테스트 (범주/지표)

| 항목 | 현황 | 근거 | 지표/목표 | 측정 TODO |
|---|---|---|---|---|
| 단위 테스트 | retrieval/rrf/index/chroma 커버 | (근거: ../proj_new/tests/test_retrieval.py:51-129) | 지속시간 Top10 보고 | pytest tests -q --durations=10 |
| 통합 테스트 | chat router memory 등 | (근거: ../proj_new/tests/test_chat_router_memory.py:1-60) | 응답 일관성 | pytest -k chat_router -q |
| E2E | 미정 — 근거 불충분 | (근거: PR#29) | 95%+ 시나리오 통과 | playwright/locust 도입 검토 |
| 커버리지 | 미정 — 근거 불충분 | (근거: PR#29) | 70%+ | pytest --cov=backend --cov-report=term-missing |

