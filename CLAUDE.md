CLAUDE.md

목적: 이 파일은 Claude Code(모델: Opus 4.1)에게 한 번에 완성형 RAG 시스템(폐쇄망·오프라인, HWP/PDF 한국어 공문서)에 필요한 전체 코드베이스를 생성·수정하도록 지시하는 프로젝트 계획 프롬프트입니다.
중요: 날짜 계획·스프린트·서술형 로드맵 금지. 즉시 빌드 가능한 코드와 검증 스크립트를 단일 세션에서 완결하세요.

⸻

0) 절대 규칙 (Non‑Negotiables)
	1.	한 번에 완성: 설명보다 코드 출력이 우선. 빈 함수/미구현 금지. # TODO, “추후” 표현 금지.
	2.	파일 출력 형식: 반드시 다음 형식을 사용하여 여러 파일을 한 번에 생성/덮어쓰기.

```file:path/to/file.ext
<정확한 파일 내용>

- 코드 아닌 문서는 `.md`/`.env.example` 등으로 동일하게 출력.


	3.	오프라인/폐쇄망: Docker 금지. pip 패키지는 오프라인 번들링 스크립트 포함. 외부 API 호출 없음(Ollama는 로컬).
	4.	모델/엔진:
	•	LLM: Ollama (테스트 기본값: qwen3:4b) — .env에서 교체 가능.
	•	검색: Whoosh(BM25) + ChromaDB(DuckDB 백엔드) 하이브리드.
	•	임베딩: BAAI/bge-m3 기본, 불가시 nlpai-lab/KoE5 → snunlp/KR-SBERT-Medium-extended 폴백.
	•	리랭커: jinaai/jina-reranker-v2-base-multilingual (ONNX/FP16 로컬) — 불가시 BM25+Vector RRF로 대체.
	5.	HWP/PDF 처리:
	•	HWP: hwplib(Java) + JPype1 브리지. 조/항/호/표/각주 구조 유지.
	•	PDF: PyMuPDF 우선, 텍스트 결손 시 Tesseract OCR(한국어 데이터 포함).
	6.	정확도 안전장치: Evidence‑Only 생성(근거 외 생성 금지), 스키마 강제 포맷, Citation 좌표/문서ID 추적, 후검증 규칙(정규식·Jaccard·문장유사도) 내장.
	7.	결과 검증·수행 가능성:
	•	make install, make bundle, make index, make qa, make run으로 즉시 동작.
	•	Golden QA 100문항과 EM/F1/Citation 측정 스크립트 포함. Pass/Fail 게이트 만족 못하면 실패 원인 리포트 자동 생성.
	8.	언어/UX: 기본 한국어. 출력 포맷과 UI 텍스트는 중장년층 가독성.
	9.	성능 제약: 8GB RAM에서도 동작. 동시 사용자 수십 명을 가정한 비동기 FastAPI + Uvicorn 구성(멀티 워커·큐·타임아웃·캐시 포함).
	10.	보안/폐쇄망: 문서 접근권한 필터, 감사 로그, 세션 타임아웃, PII 마스킹 옵션 포함.

⸻

1) 리포지토리 스펙 (생성해야 할 최종 트리)

/rag-chatbot-system/
├── Makefile
├── README.md
├── .env.example
├── start.sh
├── stop.sh
├── setup_offline.py
├── tools/
│   ├── bundle_creator.py
│   ├── integrity_verifier.py
│   ├── validate_installation.py
│   └── export_licenses.md
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── deps.py
│   ├── schemas.py
│   ├── routers/
│   │   ├── query.py
│   │   ├── admin.py
│   │   └── documents.py
│   ├── processors/
│   │   ├── hwp_structure_parser.py
│   │   ├── pdf_hybrid_processor.py
│   │   ├── structure_chunker.py
│   │   └── normalizer_govkr.py
│   ├── rag/
│   │   ├── embedder.py
│   │   ├── whoosh_bm25.py
│   │   ├── chroma_store.py
│   │   ├── hybrid_retriever.py
│   │   ├── reranker.py
│   │   ├── prompt_templates.py
│   │   ├── generator_ollama.py
│   │   ├── evidence_enforcer.py
│   │   ├── citation_tracker.py
│   │   └── answer_formatter.py
│   ├── eval/
│   │   ├── metrics.py
│   │   ├── golden_evaluator.py
│   │   └── failure_report.py
│   └── utils/
│       ├── ocr.py
│       ├── text.py
│       ├── cache.py
│       ├── concurrency.py
│       └── logging.py
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── LargeUploadZone.jsx
│   │   │   ├── AccessibleChat.jsx
│   │   │   ├── StructuredAnswer.jsx
│   │   │   ├── CitationPopup.jsx
│   │   │   ├── DocumentManager.jsx
│   │   │   └── StatusIndicator.jsx
│   │   └── styles.css
├── data/
│   ├── documents/   # HWP/PDF 투입
│   ├── index/       # Whoosh 인덱스
│   ├── chroma/      # Chroma DuckDB
│   └── golden/
│       ├── qa_100.json
│       ├── doc_meta.json
│       └── eval_rules.json
└── tests/
    ├── test_retrieval.py
    ├── test_generation.py
    └── test_citation.py

Claude는 위 트리를 정확히 생성해야 합니다. 파일 누락/빈 파일 금지.

⸻

2) 실행/환경 규격
	•	Python: 3.12 이상.
	•	시스템: Linux/macOS/Windows(WSL 권장). Docker 사용 금지.
	•	Ollama: 로컬 서비스(기본 http://localhost:11434).
	•	Tesseract: 오프라인 설치 가이드 및 한국어 데이터(kor) 포함.
	•	패키지 핵심 목록: fastapi, uvicorn, whoosh, chromadb, sentence-transformers, onnxruntime, jieba(불필요시 제외), pymupdf, pytesseract, python-dotenv, rapidfuzz, scikit-learn, numpy, pandas, orjson 등.

2.1 .env.example 사양

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

# 리랭커 (ONNX 경로 또는 HF 식별자)
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

사용자는 .env에서 OLLAMA_MODEL만 바꿔 상위 모델로 교체 가능(예: qwen2.5:14b, llama3.1:70b 등).

⸻

3) 핵심 설계 지침 (Claude가 준수해야 할 구현 규칙)

3.1 청킹·정규화
	•	청킹 규칙: 의미 단락·조/항/호 경계 우선. CHUNK_TOKENS를 상한으로 문장 단위 병합. 표/각주는 별도 청크로 분리하고 본문에 역링크(#표-1, #각주-2) 삽입.
	•	정규화: 날짜 ISO(YYYY-MM-DD), 숫자 천단위 콤마, 금액/단위 표준화, 법령 표기 제3조 제2항 통일.

3.2 검색·리랭킹
	•	**Whoosh(BM25)**와 **Chroma(cosine)**를 병렬 검색 → Reciprocal Rank Fusion(RRF)로 병합.
	•	리랭커는 상위 후보(≤TOPK_RERANK) 문단을 문장쌍 점수화 → 최종 상위 evidences 선정. 리랭커 부재 시 RRF만 사용.

3.3 생성(Evidence‑Only)
	•	입력: 사용 질의 + 상위 evidences(문서ID, 페이지, 오프셋 포함).
	•	프롬프트 골격(요지):
	•	제공된 evidence 외 사실 생성 금지, 모르면 모른다고 답변, 숫자·날짜·조항은 그대로 추출.
	•	고정 출력 스키마 강제:
	1.	핵심 답변(1–2문장)
	2.	주요 사실 불릿(3–5)
	3.	상세 설명(옵션)
	4.	출처 목록[(문서ID, p, start, end)]
	•	후검증: 답변↔evidence 자카드 유사도 ≥ EVIDENCE_JACCARD 미만이면 재생성 또는 “근거 부족” 반환.

3.4 Citation 추적
	•	evidence 수집 시 각 문단에 (doc_id, page, start_char, end_char) 메타를 부착하여 응답에 그대로 반영.
	•	출처 문자열이 파싱 가능하도록 JSON 블록으로도 함께 제공.

3.5 평가/게이트
	•	/data/golden/qa_100.json으로 EM/F1/Citation 측정.
	•	기준: EM≥95, F1≥99, Citation≥99.5, Hallucination=0 → 미달 시 failure_report.json 생성(루트 원인·개선안 포함).

3.6 동시성/안정성
	•	FastAPI + Uvicorn workers=WORKERS. 요청 큐/세마포어, per‑request 타임아웃.
	•	임베딩·리랭커 배치 처리 및 LRU 캐싱. 인덱스 핫‑리로드.

⸻

4) Claude가 반드시 생성할 대표 파일 내용 요건

아래 요건을 충족하는 구체 코드를 파일별로 출력하세요. 설명만 쓰지 말고 실행 가능한 코드로 작성합니다.

4.1 Makefile
	•	install(의존성 설치), bundle(오프라인 번들 제작), index(문서 파싱·청킹·색인), qa(골든셋 평가), run(백엔드+프론트엔드 동시 구동).

4.2 backend/processors/hwp_structure_parser.py
	•	hwplib(Java) 구동을 위한 JPype1 초기화, HWP 단락/문단/표/각주 파싱, 문서ID/페이지/오프셋 추출.

4.3 backend/processors/pdf_hybrid_processor.py
	•	PyMuPDF 텍스트 추출 + 누락율 임계 초과 시 pytesseract로 OCR 대체(한글 옵션).

4.4 backend/processors/structure_chunker.py
	•	의미 단락 병합, 표/각주 분리·역링크, 청크 메타(doc_id, page, start, end).

4.5 backend/rag/*
	•	embedder.py: bge‑m3 우선, 가용 모델 자동 폴백. 배치 임베딩.
	•	whoosh_bm25.py: 인덱스 작성·질의, 한국어 토크나이징은 공백/조사 완화용 간단 정규식.
	•	chroma_store.py: DuckDB 퍼시스턴스, 메타 저장.
	•	hybrid_retriever.py: BM25 & Vector 점수 정규화 + RRF 병합.
	•	reranker.py: ONNX 지원 멀티링구얼 리랭커 로딩/점수화.
	•	prompt_templates.py: Evidence‑Only 시스템 메시지·출력 스키마 고정 템플릿.
	•	generator_ollama.py: Ollama REST 호출(온도 0, top_p 1), 스트리밍 지원.
	•	evidence_enforcer.py: 자카드/정규식 후검증, 미달 시 재생성 또는 근거 부족.
	•	citation_tracker.py: 출처 JSON/텍스트 동시 생성.
	•	answer_formatter.py: 4단 스키마 포맷터.

4.6 backend/eval/*
	•	metrics.py: EM/F1 계산(정규화 파이프라인 포함), Citation IoU/문장유사도.
	•	golden_evaluator.py: /data/golden 로딩, 배치 평가, 대시보드 HTML 생성.
	•	failure_report.py: 실패 유형 자동 태깅 및 원인/개선안 3개 산출.

4.7 frontend/*
	•	Vite + React 18 + Tailwind. 큰 글꼴, 고대비. 파일 업로드, 채팅, 출처 팝업, 상태 표시. 키보드 전용 네비.

4.8 테스트 tests/*.py
	•	회귀·정확도 단위 테스트. 최소 1개 문서로도 통과하는 스모크 포함.

⸻

5) 프롬프트 템플릿 지시 (Claude 내부 구성)

Claude는 다음 시스템 지시를 사용해 응답을 생성합니다.

SYSTEM
	•	너는 빌드‑엔지니어 모드다. 설명보다 완성 코드를 우선 출력한다.
	•	출력은 반드시 다중 파일 블록 형식(file:...)을 사용한다.
	•	미구현/플레이스홀더/주석만 있는 함수 금지. 외부 네트워크 접근 금지.
	•	모델 파라미터: temperature=0.0, top_p=1.0, stop 시퀀스 안전 설정.
	•	에러 가능 지점(경로, 인코딩, Windows 경로 구분자)은 교차 OS 호환 코드를 쓴다.

DEVELOPER
	•	.env를 읽는 단일 설정 모듈을 작성하고 모든 서브모듈에서 사용.
	•	실패 시 복구 경로(폴백 임베딩·리랭커 비활성화·RRF 단독)를 갖춘다.
	•	인덱싱/질의 모두 로깅·측정(시간·메모리)·감사(ID·세션)를 남긴다.

USER
	•	사용자가 문서를 업로드하면 자동 인덱싱.
	•	질의 시 근거 없는 생성은 금지.
	•	UI 출처를 클릭하면 원문 하이라이트.

⸻

6) 수용 기준(수동 점검 포인트)
	•	make install로 의존성 설치 및 ONNX 리랭커 준비 완료.
	•	make index 후 data/index, data/chroma 생성 및 청크 메타 포함.
	•	make run으로 :8000 백엔드·:5173 프런트엔드 구동. 브라우저에서 업로드/질의/출처 팝업 동작.
	•	make qa로 EM/F1/Citation 수치 출력 및 reports/accuracy_dashboard.html 생성.
	•	리랭커 불가 환경에서도 질의·응답 정상 동작(RRF 폴백).

⸻

7) 주의해야 할 흔한 실패와 방지책
	•	HWP 파싱 실패: JVM attach 타이밍 문제 → JPype isJVMStarted() 체크, classpath 동적 설정, 종료 훅 등록.
	•	OCR 과다 호출: 텍스트 추출률 샘플링 후 임계치(예: 0.6) 미만에만 OCR.
	•	과도한 청킹: 토큰 상한 준수 + 문장 경계 유지. 표/각주 역링크 누락 금지.
	•	Hallucination: Evidence‑Only 템플릿 + 후검증 불합격 시 재생성 대신 “근거 부족”.
	•	메모리 초과: 배치 임베딩/캐시/지연 로딩. Whoosh searcher 재사용.

⸻

8) Claude 출력 예시(형식 데모)

아래는 형식만 예시입니다. 실제 구현 시 실동 코드와 실제 내용을 작성하십시오.

```file:Makefile
<내용>

<내용>

<내용>

---

## 9) 지금 바로 생성

위 사양을 **모두 만족**하는 전체 리포지토리를 *이번 응답에서 한 번에* 출력하세요. 누락 없이 `Makefile`부터 프런트/백엔드/테스트/도구/데이터 샘플까지 모든 파일을 생성하십시오.