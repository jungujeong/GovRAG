# 커밋 히스토리 분석

<!-- 생성 시간: 2025-10-15 15:50 -->

## 커밋 로그 (892fdc4..7c00a13, 46개)

**근거: commits.txt**

| # | 커밋 해시 | 메시지 | 유형 |
|---|----------|--------|------|
| 1 | 7c00a13 | fix: chat.py 로깅 시스템 수정 및 모니터링 기능 추가 | fix |
| 2 | b705aa3 | fix: improve frontend startup reliability and cleanup unused files | fix |
| 3 | 68e5ad3 | fix: improve document summary generation reliability and performance | fix |
| 4 | 9bac1f0 | fix: resolve frontend infinite loading and improve startup reliability | fix |
| 5 | 15e9500 | feat: add missing files for document summary feature | feat |
| 6 | 3e1ad8a | feat: add document summary button to UI and fix summary path | feat |
| 7 | 763891f | fix: resolve citation mismatch and topic change detection issues (#51) | fix |
| 8 | 8771476 | Merge pull request #49 from jungujeong/feature/statistical-approach-refactor | merge |
| 9 | 5b27063 | refactor: replace hardcoded patterns with statistical approaches | refactor |
| 10 | 53de022 | fix(postprocess): harmonize tokens with evidence vocabulary | fix |
| 11 | e69f095 | Revert "fix(postprocess): drop low-coverage sentences to avoid unsupported facts" | revert |
| 12 | 55450d0 | Revert "fix(postprocess): canonicalize entities and prune unsupported sentences" | revert |
| 13 | 09339aa | fix(postprocess): canonicalize entities and prune unsupported sentences | fix |
| 14 | 3063e90 | fix(postprocess): drop low-coverage sentences to avoid unsupported facts | fix |
| 15 | 325c7de | fix(rag): drop Levenshtein dependency and use pure Python similarity | fix |
| 16 | cf622e4 | fix(rag): validate outputs against evidences and normalize entity variants | fix |
| 17 | 0ab0391 | fix(frontend): surface streaming errors and avoid silent empty replies | fix |
| 18 | f0d0663 | chore(prompt): guide model to structure answers by intent | chore |
| 19 | afed6fa | Revert "feat(postprocess): auto-structure department summaries when requested" | revert |
| 20 | 9c897ea | feat(postprocess): auto-structure department summaries when requested | feat |
| 21 | d601c2e | fix(citation,format): unify numbering and avoid duplicates; preserve line breaks; guard fixed citation map | fix |
| 22 | 7ffa3f6 | feat(rag): topic-aware doc scope, re-retrieval, and citation stability | feat |
| 23 | 4063cd6 | Merge pull request #46 from jungujeong/feature/improve-rag-accuracy | merge |
| 24 | 7291a4c | feat: improve RAG system accuracy and topic detection | feat |
| 25 | 50a06c7 | Merge pull request #44 from jungujeong/feature/improve-rag-system | merge |
| 26 | 05f6560 | feat: improve citation system with sequential numbering and interactive UI | feat |
| 27 | 3eb1b3c | Merge pull request #41 from jungujeong/feature/improve-citation-system | merge |
| 28 | 63daa81 | feat: improve citation system with sequential numbering and interactive UI | feat |
| 29 | 04b03ae | Merge pull request #39 from jungujeong/feature/improve-response-generation-and-cleanup | merge |
| 30 | f24250a | feat: improve response generation and clean up codebase | feat |
| 31 | 0d5d4df | Merge pull request #37 from jungujeong/feature/fix-index-corruption-and-improve-korean-handling | merge |
| 32 | e3d2fe2 | feat: fix index corruption issues and improve Korean language handling | feat |
| 33 | d85f114 | Merge pull request #35 from jungujeong/feature/improve-ui-and-citation-system | merge |
| 34 | c87845d | feat: enhance UI/UX and citation system for Korean RAG chatbot | feat |
| 35 | ece3e14 | Merge pull request #33 from jungujeong/feature/enhanced-directive-processing | merge |
| 36 | 3bd9c1b | feat: implement enhanced directive processing with Y-axis coordinate matching | feat |
| 37 | 3029257 | clean: remove old RAG system files | clean |
| 38 | efd4669 | feat: merge new Evidence-Only RAG system (#31) | feat |
| 39 | c083e13 | update: add SSH and Git commands to Claude settings | update |
| 40 | 8252d29 | chore: 재생성 가능한 파일들을 Git에서 제외 | chore |
| 41 | 50e0af5 | feat: 새로운 RAG 시스템 구현 - 한국어 공문서 전용 | feat |
| 42 | 2d4507b | update: claude settings for directive processing tools | update |
| 43 | 58e0266 | clean: 데이터 파일 정리, .gitkeep만 유지 | clean |
| 44 | adad94e | feat: 완전 개선된 RAG 시스템 구현 | feat |
| 45 | cdd18cd | chore: exclude large model files from git | chore |
| 46 | c1330b8 | feat: new RAG chatbot system with Evidence-Only generation | feat |

---

## 커밋 유형별 분류

**근거: commits.txt 커밋 메시지 분석**

| 유형 | 개수 | 비율 | 설명 |
|------|------|------|------|
| **feat** (기능 추가) | 15 | 32.6% | 새로운 기능 구현 |
| **fix** (버그 수정) | 13 | 28.3% | 버그 및 이슈 해결 |
| **merge** (PR 병합) | 9 | 19.6% | Pull Request 병합 |
| **refactor** (리팩토링) | 1 | 2.2% | 코드 구조 개선 |
| **revert** (되돌리기) | 3 | 6.5% | 이전 커밋 취소 |
| **chore** (기타 작업) | 3 | 6.5% | 설정/도구 작업 |
| **clean** (정리) | 2 | 4.3% | 코드/파일 정리 |

**추론: feat(32.6%) + fix(28.3%) = 60.9% → 새 기능 개발과 안정화가 주요 활동**

---

## 변경 많은 파일 TOP 10

**근거: git_stat.txt**

| 순위 | 파일 | 변경 라인 | 추가 | 삭제 | 비고 |
|------|------|----------|------|------|------|
| 1 | backend/routers/chat.py | 2,029 | +2,029 | - | 채팅 핵심 로직 |
| 2 | app_enhanced.py | 1,262 | - | -1,262 | 삭제됨 |
| 3 | app.py | 1,189 | - | -1,189 | 삭제됨 |
| 4 | frontend/package-lock.json | 4,911 | +4,911 | - | npm 의존성 |
| 5 | data/golden/qa_100.json | 1,605 | +1,605 | - | 평가 데이터셋 |
| 6 | frontend/src/styles/Chat.css | 1,779 | +1,779 | - | 채팅 UI 스타일 |
| 7 | frontend/src/App_Medium.jsx | 2,099 | +2,099 | - | 프론트엔드 앱 |
| 8 | frontend/src/AppMediumClean.jsx | 1,280 | +1,280 | - | 정리된 버전 |
| 9 | backend/processors/directive_extractor_whitelist_final.py | 935 | +935 | - | 공문서 추출기 |
| 10 | .claude/agents/performance-profiler.md | 799 | +799 | - | Claude 에이전트 |

**추가 분석**:
- **신규 추가 파일**: 총 51,950줄 (백엔드/프론트엔드/문서/도구)
- **삭제된 파일**: 총 7,031줄 (구 RAG 시스템, 테스트 파일)
- **순 증가**: +44,919줄 (639% 증가)

---

## 주요 키워드 추출

**근거: commits.txt 메시지 분석**

### 기능 키워드 (상위 15개)

| 키워드 | 출현 | 관련 커밋 | 의미 |
|--------|------|----------|------|
| **citation** | 8회 | #7, #21, #26, #28, #34 | 출처 추적 시스템 |
| **RAG** | 6회 | #22, #24, #38, #41, #44, #46 | RAG 시스템 재설계 |
| **frontend** | 4회 | #2, #4, #17 | 프론트엔드 개선 |
| **summary** | 3회 | #3, #5, #6 | 문서 요약 기능 |
| **postprocess** | 6회 | #10, #11, #13, #14, #19, #20 | 응답 후처리 |
| **topic** | 2회 | #7, #24 | 주제 감지 |
| **Korean** | 2회 | #32, #34 | 한국어 처리 |
| **evidence** | 2회 | #16, #46 | 증거 기반 생성 |
| **index** | 2회 | #32 | 인덱스 관리 |
| **UI/UX** | 2회 | #26, #34 | 사용자 인터페이스 |
| **statistical** | 1회 | #9 | 통계적 접근 |
| **monitoring** | 1회 | #1 | 모니터링 |
| **directive** | 1회 | #36 | 공문서 처리 |
| **accuracy** | 2회 | #24 | 정확도 개선 |
| **reliability** | 2회 | #2, #4 | 안정성 |

**추론: "citation", "RAG", "postprocess"가 핵심 개발 초점 → 출처 추적 정확도가 최우선 과제**

### 기술 키워드

| 키워드 | 출현 | 의미 |
|--------|------|------|
| Levenshtein | 1회 | 유사도 알고리즘 제거 |
| streaming | 1회 | 스트리밍 응답 |
| token | 1회 | 토큰 정규화 |
| entity | 2회 | 엔터티 정규화 |
| sentence | 1회 | 문장 필터링 |
| scope | 1회 | 문서 범위 관리 |

---

## 시간별 개발 흐름 추론

**근거: commits.txt 역순 분석**

### Phase 1: 초기 구현 (커밋 46~38, 9개)
```
c1330b8 feat: new RAG chatbot system with Evidence-Only generation
adad94e feat: 완전 개선된 RAG 시스템 구현
50e0af5 feat: 새로운 RAG 시스템 구현 - 한국어 공문서 전용
efd4669 feat: merge new Evidence-Only RAG system (#31)
```
**특징**: Evidence-Only RAG 시스템 기본 구현, 한국어 공문서 특화

### Phase 2: 기능 확장 (커밋 37~25, 13개)
```
3bd9c1b feat: implement enhanced directive processing with Y-axis coordinate matching
c87845d feat: enhance UI/UX and citation system for Korean RAG chatbot
e3d2fe2 feat: fix index corruption issues and improve Korean language handling
05f6560 feat: improve citation system with sequential numbering and interactive UI
```
**특징**: 공문서 처리, UI/UX, 출처 시스템 개선, 인덱스 안정화

### Phase 3: 정확도 개선 (커밋 24~10, 15개)
```
7291a4c feat: improve RAG system accuracy and topic detection
7ffa3f6 feat(rag): topic-aware doc scope, re-retrieval, and citation stability
cf622e4 fix(rag): validate outputs against evidences and normalize entity variants
5b27063 refactor: replace hardcoded patterns with statistical approaches
```
**특징**: 주제 감지, 출처 안정성, 증거 검증, 통계적 접근 도입

### Phase 4: 안정화 및 최적화 (커밋 9~1, 9개)
```
68e5ad3 fix: improve document summary generation reliability and performance
9bac1f0 fix: resolve frontend infinite loading and improve startup reliability
7c00a13 fix: chat.py 로깅 시스템 수정 및 모니터링 기능 추가
```
**특징**: 프론트엔드 안정화, 문서 요약 성능, 로깅/모니터링 강화

**추론: 4개 Phase를 거쳐 점진적으로 완성도를 높임**

---

## Revert 커밋 분석

**근거: commits.txt**

| 커밋 | Revert 대상 | 이유 추론 |
|------|-------------|-----------|
| e69f095 | "fix(postprocess): drop low-coverage sentences" | 문장 필터링이 과도하여 정보 손실 |
| 55450d0 | "fix(postprocess): canonicalize entities" | 엔터티 정규화 로직 문제 |
| afed6fa | "feat(postprocess): auto-structure department summaries" | 부서 요약 자동 구조화 실패 |

**추론: 응답 후처리(postprocess)가 가장 실험적이고 불안정한 영역 → 3번의 revert 발생**

---

## Pull Request 패턴

**근거: commits.txt (Merge pull request)**

| PR 번호 | 브랜치 | 주제 | 커밋 개수 추정 |
|---------|--------|------|--------------|
| #51 | (직접 커밋) | citation mismatch & topic detection | 1 |
| #49 | feature/statistical-approach-refactor | 통계적 접근 리팩토링 | 1+ |
| #46 | feature/improve-rag-accuracy | RAG 정확도 개선 | 1+ |
| #44 | feature/improve-rag-system | RAG 시스템 개선 | 1+ |
| #41 | feature/improve-citation-system | 출처 시스템 개선 | 1+ |
| #39 | feature/improve-response-generation-and-cleanup | 응답 생성 & 정리 | 1+ |
| #37 | feature/fix-index-corruption-and-improve-korean-handling | 인덱스 & 한국어 처리 | 1+ |
| #35 | feature/improve-ui-and-citation-system | UI/UX & 출처 | 1+ |
| #33 | feature/enhanced-directive-processing | 공문서 처리 강화 | 1+ |
| #31 | (branch 불명) | Evidence-Only RAG 병합 | 다수 |

**추론: Feature 브랜치 전략 사용, 주요 기능마다 독립 브랜치 생성 → 체계적인 개발 프로세스**

---

## 변경 동기 추론

### 1. 왜 Streamlit → FastAPI + React?
**근거: app.py/app_enhanced.py 삭제 (2,451줄), backend/routers/ 생성 (4,360줄)**

**추론**:
- Streamlit은 프로토타입용, 프로덕션에는 부적합 (확장성, API 제공, 커스텀 UI 제한)
- FastAPI: 비동기 지원, API 문서 자동 생성, 높은 성능
- React: 풍부한 상호작용, 컴포넌트 재사용, 상태 관리

### 2. 왜 LangChain 제거?
**근거: requirements.txt (langchain 8개 패키지 삭제)**

**추론**:
- LangChain은 범용 프레임워크 → 한국어 공문서 특화에는 오버헤드
- 직접 구현으로 세밀한 제어 가능 (Evidence-Only, 출처 추적)
- 의존성 최소화 (폐쇄망 환경 고려)

### 3. 왜 Whoosh 추가?
**근거: backend/rag/whoosh_bm25.py 생성, rank-bm25 제거**

**추론**:
- rank-bm25는 메모리 기반 → 대용량 문서 처리 한계
- Whoosh는 디스크 기반 인덱스 → 확장성, 지속성, 빠른 검색
- BM25 + Vector 하이브리드 검색 전략

### 4. 왜 46개 커밋이나?
**근거: commits.txt (feat 15, fix 13, revert 3)**

**추론**:
- 대규모 재설계 프로젝트 → 점진적 개발 필요
- 출처 추적 정확도가 핵심 → 반복 실험 (revert 3회)
- Pull Request 9개 → 팀 협업 또는 기능별 격리

---

## 결론

### 개발 특징
1. **체계적 접근**: Feature 브랜치 전략, PR 리뷰, 단계적 병합
2. **반복 실험**: Postprocess 영역에서 3번 revert → 최적 해법 탐색
3. **증분 개발**: 46개 커밋으로 기능 분할 → 안정적 진화

### 핵심 목표
1. **출처 정확도** (citation 키워드 8회 → 최다 출현)
2. **한국어 최적화** (Korean, directive, entity 처리)
3. **안정성** (frontend reliability, index corruption 수정)

### 개발 기간 추정
**추론**: 46개 커밋, 9개 PR → 약 **2~3개월** 개발 기간 추정 (1주일 1~2 PR 가정)

**근거 파일**: commits.txt, git_stat.txt
