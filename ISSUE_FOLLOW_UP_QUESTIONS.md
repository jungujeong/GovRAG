## 🐞 버그 리포트

### 📌 버그 설명
후속 질문 처리 시스템이 제대로 작동하지 않아 다음과 같은 문제들이 발생하고 있습니다:

1. **후속 질문 시 문서 스코프 재조정 실패**: 첫 답변의 evidence만 고정 재사용하여 다양한 후속 질문에 대응하지 못함
2. **답변 텍스트와 증거 정렬 미작동**: ResponseGrounder가 파이프라인에 연결되지 않아 LLM 답변 보정 없음
3. **주제 변경 대응 불완전**: Topic change 감지 후 fallback/확장 로직이 일관되지 않음
4. **스트리밍 경로 미정리**: 스트리밍에서 동일한 evidence 스코프/grounding 미적용
5. **통합 테스트 부족**: 컴파일 체크만 완료, 기능 테스트 미진행

### ⚙️ 재현 방법
1. 특정 문서에 대해 초기 질문 수행
2. 첫 답변 확인 후 관련 후속 질문 입력
3. 다른 주제로 전환하는 질문 입력
4. 다음 문제들 발생:
   - 후속 질문이 첫 답변의 문서 범위에만 국한됨
   - 주제 전환 시 적절한 문서를 찾지 못함
   - 스트리밍 모드에서 일반 모드와 다른 결과 출력

### 📷 스크린샷 / 에러 메시지
```python
# 현재 문제가 있는 코드 구조
# backend/routers/chat.py

# 1. 후속 질문 처리 시 고정된 evidence 재사용
if is_followup and session.first_response_evidences:
    evidences = session.first_response_evidences  # 문제: 첫 답변 증거만 재사용

# 2. ResponseGrounder 미연결
# response = response_grounder.ground_response(response, evidences)  # 주석 처리됨

# 3. Topic change 대응 미완성
if topic_changed:
    # fallback 로직이 _resolve_evidences로 이동되지 않음
    pass
```

### 💡 참고 사항

#### 수정 방향 및 세부 구현 계획

**1. Evidence 스코프 리졸버 통합**
- `_resolve_evidences` 메서드 신규 작성
- send_message와 스트리밍 모두 동일 경로로 evidence scope 판단
- doc scope 메타데이터(요청 문서, 검출 문서, 평균 스코어) 반환
- Topic change 감지 시: 세션 전체 문서 → 전체 문서 범위 순으로 확장

**2. 후속 질문 시 스코프 사용 방식 개선**
- `session.first_response_evidences` 의존 제거
- `session.recent_source_doc_ids`만 참조하도록 변경
- `_deduplicate_doc_ids`로 문서 순서 보존하며 중복 제거
- `_average_evidence_score` 사용해 scope 확장 여부 결정

**3. 답변 Grounding과 후처리**
- ResponseGrounder를 일반/스트리밍 경로 모두에 삽입
- 처리 순서: ResponseGrounder → ResponsePostProcessor → EvidenceEnforcer → CitationTracker → AnswerFormatter
- Grounding 정보를 `metadata.grounding`으로 추가

**4. Topic change 대응 UX**
- `_resolve_evidences`에서 topic change 감지 시 metadata에 이유/제안 문서 저장
- 증거가 없을 때 사용자에게 새 문서 범위 선택 안내

**5. 스트리밍 경로 동기화**
- 동일한 `_resolve_evidences` 호출
- `allowed_doc_ids_enforce` 공유
- grounder/후처리 재사용
- `metadata.doc_scope`와 grounding 기록을 스트리밍 출력에도 포함

**6. 테스트 및 검증**
```bash
# 컴파일 체크
python -m py_compile backend/routers/chat.py backend/rag/response_grounder.py

# 단위 테스트
pytest tests/test_chat_router_memory.py

# 통합 테스트
python scripts/test_followup_questions.py
```

**7. 문서/메타 업데이트**
- README에 후속 질문 처리 방식 문서화
- QA 결과 및 변경된 메타 필드 설명 업데이트

#### 우선순위
1. **긴급**: Evidence 스코프 리졸버 통합 (후속 질문 기본 기능)
2. **높음**: ResponseGrounder 연결 (답변 품질)
3. **중간**: Topic change UX 개선
4. **낮음**: 문서 업데이트

#### 예상 소요 시간
- 전체 수정 및 테스트: 약 1-2주
- 핵심 기능(1-3번) 수정: 3-4일
- 테스트 및 안정화: 2-3일