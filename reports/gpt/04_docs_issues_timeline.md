Generated on 2025-10-15 15:32 KST (rev2)

# 문서 및 이슈/PR 타임라인 분석

비교 기준: Old(892fdc4) ↔ New(7c00a13)

## 1) 시간순 타임라인

| 날짜 | PR/Issue | 내용(한 줄) | 근거 |
|---|---|---|---|
| 2025-06-12 | PR#29 | enhanced rag system v1.1 병합(Streamlit+LangChain 체계) | (근거: PR#29; ../proj_old/app.py:1-40)
| 2025-10-14 | PR#N/A — 근거 불충분 | chat.py 로깅·모니터링 추가, 대시보드/가이드 문서화 | (근거: ../proj_new/docs/MONITORING_GUIDE.md:1-30; TODO: 해당 변경 PR 링크 수집)
| 2025-10-14 | PR#N/A — 근거 불충분 | Citation 파싱 재작성·특수문자 정제·FE 복구 가이드 | (근거: ../proj_new/FIXES_2025-10-14.md:9-40; ../proj_new/FIXES_2025-10-14.md:168-240; TODO: PR 링크 수집)
| 2025-10-14 | PR#N/A — 근거 불충분 | SimpleIndexer 가짜 데이터 제거/비활성화 | (근거: ../proj_new/HALLUCINATION_FIX_REPORT.md:35-45; ../proj_new/backend/processors/simple_indexer.py:25-46; TODO: PR 링크 수집)

## 2) Problem → Decision → Outcome (핵심 사례)

1) Hallucination(가짜 데이터) 문제
- Problem: “The `SimpleIndexer` class contained hardcoded fake test data…” (근거: ../proj_new/HALLUCINATION_FIX_REPORT.md:7-19)
- Decision: “Removed all fake data, method now returns empty array” (근거: ../proj_new/HALLUCINATION_FIX_REPORT.md:35-45)
- Outcome: “Databases clean — No fake data currently indexed” (근거: ../proj_new/HALLUCINATION_FIX_REPORT.md:77-86)

2) Citation 개수 불일치
- Problem: “LLM이 답변에 [1], [2]… `response_sources`에는 1개만” (근거: ../proj_new/FIXES_2025-10-14.md:9-16)
- Decision: “Parse existing [1], [2] citations… then match evidences” (근거: ../proj_new/FIXES_2025-10-14.md:27-74)
- Outcome: “응답 citation 개수와 sources 동기화” (근거: ../proj_new/FIXES_2025-10-14.md:76-80)

3) 특수문자 표시로 가독성 저하
- Problem: “Private Use Area Unicode 표시” (근거: ../proj_new/FIXES_2025-10-14.md:83-90)
- Decision: 인덱싱 단계·후처리 정제 추가 (근거: ../proj_new/FIXES_2025-10-14.md:121-166; ../proj_new/FIXES_2025-10-14.md:175-240)
- Outcome: “가독성 향상” (근거: ../proj_new/FIXES_2025-10-14.md:168-172)

4) 토픽 전환 민감도
- Problem: 후속 질문에서 context 유지 과도 (근거: ../proj_new/backend/rag/two_stage_retrieval.py:38-56)
- Decision: threshold 0.03로 낮춤 (근거: ../proj_new/backend/rag/two_stage_retrieval.py:38-56; ../proj_new/backend/rag/two_stage_retrieval.py:220-238)
- Outcome: 전환 감지 민감도↑ (근거: ../proj_new/backend/rag/two_stage_retrieval.py:148-176)

5) 모니터링/품질·성능 메트릭 도입
- Problem: 관찰 가능한 지표 부족 (근거: PR#29)
- Decision: QueryLog/대시보드·API 문서화 (근거: ../proj_new/docs/MONITORING_GUIDE.md:1-30)
- Outcome: 로그 기반 품질/성능 현황 집계 가능 (근거: ../proj_new/docs/MONITORING_GUIDE.md:30-120)

## 3) 인용(짧게)

> “Fake test data source removed… Databases clean” (근거: ../proj_new/HALLUCINATION_FIX_REPORT.md:77-86)

> “Parse existing [1], [2] citations… then match them to evidences” (근거: ../proj_new/FIXES_2025-10-14.md:27-40)

> “Two-stage retrieval… topic change detected” (근거: ../proj_new/backend/rag/two_stage_retrieval.py:166-176)

