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

## 평가
```bash
make qa  # Golden QA 100문항 평가
```

기준: EM≥95%, F1≥99%, Citation≥99.5%, Hallucination=0%