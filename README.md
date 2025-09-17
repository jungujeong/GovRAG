# RAG Chatbot System (폐쇄망/오프라인)

한국어 공문서(HWP/PDF) 처리에 최적화된 Evidence-Only RAG 시스템

## 시작하기

```bash
make setup    # 프로젝트 구조 생성
make install  # 의존성 설치
make index    # 문서 인덱싱
make run      # 시스템 실행
```

## 주요 기능
- HWP/PDF 한국어 문서 구조 보존 파싱
- Whoosh(BM25) + ChromaDB 하이브리드 검색
- Evidence-Only 생성으로 할루시네이션 방지
- 출처 추적 및 인용 좌표 제공
- 오프라인/폐쇄망 완전 지원
- 후속 질문 대응용 대화 요약·엔터티 메모리 + 질의 재작성

## Conversation Memory / Observability
- 세션별 `conversation_summary`, `recent_entities` 메모리 계층 저장
- 질의 재작성(Anaphora 해소) → 검색 → 생성 전 과정 메타데이터(`rewrite`, `memory`)로 기록
- `backend/routers/chat.py` 로그에서 rewrite fallback, summary gate, entity 개수, 증거 수 확인 가능
- `pytest tests/test_conversation_summarizer.py tests/test_query_rewriter.py tests/test_chat_router_memory.py`
  로 요약·재작성·라우터 통합 TDD 시나리오 실행
- KPI(회상 실패율, Retrieval Gain@5)는 `QueryResponse.metadata`와 서버 로그를 기반으로 대시보드 수집

## 평가
```bash
make qa  # Golden QA 100문항 평가
```

기준: EM≥95%, F1≥99%, Citation≥99.5%, Hallucination=0%

### 품질 지표 추적
- 회상 실패율(Recall Failure Rate) 및 Retrieval Gain@5는 `/api/chat` 응답 메타데이터와 로그를 수집해 산출합니다.
- 재작성 폴백 비율은 `metadata.rewrite.used_fallback`으로 계산합니다.
- 요약 사용률/거부율은 `metadata.memory.summary_updated`, `metadata.memory.summarizer_confidence` 로 추적합니다.

### 현재 상태
- 앱 실행 시 첫 질문에서도 원활히 답변이 생성되도록 수정했습니다.
- `pytest tests/test_chat_router_memory.py` 등 핵심 TDD 테스트는 통과했습니다.
- sandbox 제한으로 `pytest tests -q` 전체 실행은 현재 환경에서 중단되지만, 개별 기능 테스트는 성공적으로 완료되었습니다.
