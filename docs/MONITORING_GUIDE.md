# RAG 시스템 로그 모니터링 가이드

## 개요

이 시스템은 RAG 시스템의 모든 질의와 응답을 상세하게 로깅하고 분석할 수 있는 포괄적인 모니터링 시스템을 제공합니다.

## 주요 기능

### 1. 포괄적인 로깅 시스템

#### 저장되는 정보
- **기본 정보**: 질의, 타임스탬프, 세션 ID, 질의 타입
- **성능 메트릭**:
  - 검색 시간 (ms)
  - 리랭킹 시간 (ms)
  - 생성 시간 (ms)
  - 총 처리 시간 (ms)
  - 메모리 사용량 (MB)
  - CPU 사용률 (%)
  - 토큰 수 (prompt, completion, total)

- **품질 메트릭**:
  - 신뢰도 점수
  - Evidence Jaccard 유사도
  - Citation 커버리지
  - Hallucination 탐지 여부
  - 일반 응답 여부
  - 출처 개수
  - Evidence 개수
  - 답변 길이
  - 핵심 사실 개수

- **검색 메트릭**:
  - BM25/Vector/RRF/Rerank 결과 수
  - 평균 점수 및 최고 점수
  - 검색 결과 상세 정보

- **오류 정보**:
  - 오류 발생 여부
  - 오류 타입
  - 오류 메시지
  - 재시도 횟수

### 2. API 엔드포인트

모든 API는 `http://localhost:8000/admin/logs/` 경로로 접근 가능합니다.

#### 통계 조회
```bash
GET /admin/logs/statistics?date=2025-10-15
```
응답:
```json
{
  "total_queries": 150,
  "query_types": {"normal": 140, "greeting": 5, "no_evidence": 5},
  "performance": {
    "avg_total_time_ms": 1234.5,
    "avg_search_time_ms": 234.5,
    "avg_generation_time_ms": 890.2,
    "total_tokens": 45000,
    "avg_tokens_per_query": 300
  },
  "quality": {
    "avg_confidence": 0.85,
    "high_confidence_rate": 0.78,
    "avg_sources_per_query": 2.3,
    "hallucination_rate": 0.01,
    "generic_response_rate": 0.05
  },
  "errors": {
    "error_count": 2,
    "error_rate": 0.013
  }
}
```

#### 최근 질의 조회
```bash
GET /admin/logs/recent?limit=20&date=2025-10-15
```

#### 로그 검색
```bash
GET /admin/logs/search?query_text=홍티예술촌&min_confidence=0.7&limit=50
```
필터 옵션:
- `query_text`: 질의 텍스트 검색
- `date`: 특정 날짜
- `min_confidence`: 최소 신뢰도
- `has_error`: 오류 여부 (true/false)
- `limit`: 결과 개수

#### 품질 이슈 조회
```bash
GET /admin/logs/quality-issues?date=2025-10-15&limit=20
```
응답:
```json
{
  "low_confidence": [...],
  "hallucinations": [...],
  "generic_responses": [...],
  "no_sources": [...],
  "counts": {
    "low_confidence": 5,
    "hallucinations": 1,
    "generic_responses": 3,
    "no_sources": 2
  }
}
```

#### 성능 이슈 조회
```bash
GET /admin/logs/performance-issues?date=2025-10-15&slow_threshold_ms=5000
```
응답:
```json
{
  "slow_queries": [...],
  "high_memory": [...],
  "high_tokens": [...],
  "counts": {
    "slow_queries": 3,
    "high_memory": 1,
    "high_tokens": 2
  }
}
```

#### 트렌드 분석
```bash
GET /admin/logs/trends?days=7
```
7일간의 트렌드 데이터 반환 (일별 통계)

#### HTML 리포트 생성
```bash
GET /admin/logs/report?date=2025-10-15
```
상세한 HTML 리포트 생성 및 반환

### 3. 실시간 모니터링 대시보드

#### 접근 방법

React 컴포넌트로 구현되어 있습니다:
```jsx
import MonitoringDashboard from './components/MonitoringDashboard'
```

#### 주요 기능

1. **실시간 통계 카드**
   - 성능 메트릭 (응답 시간, 토큰 사용량 등)
   - 품질 메트릭 (신뢰도, 환각 탐지율 등)
   - 오류 및 이슈 카운트

2. **7일 트렌드 차트**
   - 일별 질의 수
   - 평균 신뢰도
   - 평균 응답 시간
   - 오류율

3. **최근 질의 목록**
   - 질의 텍스트
   - 신뢰도 점수 (색상 코딩)
   - 처리 시간
   - 타임스탬프

4. **품질 이슈 알림**
   - 저신뢰도 응답
   - 환각 탐지
   - 출처 없는 응답

5. **성능 이슈 알림**
   - 느린 질의
   - 높은 메모리 사용
   - 높은 토큰 사용

6. **제어 기능**
   - 날짜 선택
   - 자동 새로고침 (30초 간격)
   - 수동 새로고침
   - HTML 리포트 다운로드

## 로그 파일 구조

```
backend/logs/queries/
├── 2025-10-15/
│   ├── query_20251015_120000_123456.json
│   ├── query_20251015_120001_234567.json
│   └── report.html
├── 2025-10-16/
│   └── ...
```

각 JSON 파일 구조:
```json
{
  "timestamp": "2025-10-15T12:00:00.123456",
  "session_id": "uuid",
  "query": "질의 텍스트",
  "query_type": "normal",
  "extracted_keywords": ["키워드1", "키워드2"],
  "retrieval_metrics": {
    "bm25_count": 30,
    "vector_count": 30,
    "rrf_count": 50,
    "final_count": 10,
    "avg_bm25_score": 0.45,
    "avg_vector_score": 0.67,
    "top_bm25_score": 0.89
  },
  "search_results": [...],
  "model_name": "qwen3:4b",
  "model_response": "응답 텍스트",
  "response_sources": [...],
  "quality_metrics": {
    "confidence_score": 0.85,
    "evidence_jaccard": 0.72,
    "citation_coverage": 0.95,
    "hallucination_detected": false,
    "generic_response": false,
    "source_count": 3,
    "evidence_count": 5,
    "answer_length": 450,
    "key_facts_count": 4
  },
  "performance_metrics": {
    "search_time_ms": 234.5,
    "rerank_time_ms": 123.4,
    "generation_time_ms": 890.2,
    "total_time_ms": 1248.1,
    "prompt_tokens": 450,
    "completion_tokens": 120,
    "total_tokens": 570,
    "memory_used_mb": 234.5,
    "cpu_percent": 45.6
  },
  "error_info": {
    "has_error": false
  }
}
```

## 사용 예시

### 1. 일일 성능 리포트 확인
```bash
curl http://localhost:8000/admin/logs/statistics
```

### 2. 특정 질의 검색
```bash
curl "http://localhost:8000/admin/logs/search?query_text=홍티예술촌&min_confidence=0.5"
```

### 3. 품질 이슈 확인
```bash
curl http://localhost:8000/admin/logs/quality-issues
```

### 4. HTML 리포트 생성
```bash
curl http://localhost:8000/admin/logs/report > report.html
open report.html  # macOS
```

### 5. 트렌드 분석
```bash
curl "http://localhost:8000/admin/logs/trends?days=30"
```

## 모니터링 베스트 프랙티스

1. **일일 체크**
   - 매일 아침 대시보드 확인
   - 오류율, 환각 탐지율, 평균 신뢰도 확인

2. **주간 리뷰**
   - 7일 트렌드 확인
   - 성능 저하 패턴 식별
   - 품질 이슈 원인 분석

3. **알림 설정**
   - 오류율 > 5%
   - 환각 탐지율 > 1%
   - 평균 응답 시간 > 3초
   - 평균 신뢰도 < 0.7

4. **로그 보관**
   - 30일 이상 로그 보관 권장
   - 월별 통계 리포트 생성
   - 중요 이슈 사례 별도 보관

## 문제 해결

### 로그가 생성되지 않을 때
1. `backend/logs/queries/` 디렉토리 권한 확인
2. QueryLogger 초기화 확인
3. query.py 로깅 코드 확인

### 대시보드가 로드되지 않을 때
1. 백엔드 서버 실행 확인 (http://localhost:8000)
2. API 엔드포인트 접근 확인
3. 브라우저 콘솔 에러 확인

### 통계가 부정확할 때
1. 로그 파일 형식 확인
2. 날짜 파라미터 확인
3. 타임존 설정 확인

## 성능 최적화

1. **로그 파일 크기 관리**
   - search_results는 상위 10개만 저장
   - 텍스트 프리뷰는 200자로 제한
   - 오래된 로그 압축 또는 삭제

2. **API 응답 속도**
   - 날짜별 로그 캐싱
   - 통계 결과 캐싱 (5분)
   - 페이지네이션 활용

3. **대시보드 성능**
   - 자동 새로고침 간격 조정 (30초 권장)
   - 표시 항목 수 제한
   - 필요시 날짜 범위 제한

## 추가 개발 아이디어

1. **알림 시스템**
   - 이메일/슬랙 알림
   - 임계값 기반 경고

2. **고급 분석**
   - 질의 클러스터링
   - 사용자 패턴 분석
   - A/B 테스트 지원

3. **내보내기 기능**
   - CSV/Excel 내보내기
   - PDF 리포트 생성
   - 그래프 이미지 저장

4. **비교 분석**
   - 일별/주별/월별 비교
   - 모델 버전 비교
   - 파라미터 설정 비교
