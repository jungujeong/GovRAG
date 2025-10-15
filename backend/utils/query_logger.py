"""Enhanced query logging system with comprehensive monitoring and quality metrics"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
import os
import psutil
import traceback

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Single search result metadata"""
    chunk_id: str
    doc_id: str
    page: int
    text_preview: str  # First 200 chars
    rrf_score: float
    keyword_relevance: float
    bm25_score: float
    vector_score: float
    include_reason: str


@dataclass
class QualityMetrics:
    """Quality and accuracy metrics"""
    confidence_score: float = 0.0
    evidence_jaccard: float = 0.0
    citation_coverage: float = 0.0
    hallucination_detected: bool = False
    generic_response: bool = False
    has_sources: bool = True
    source_count: int = 0
    evidence_count: int = 0
    answer_length: int = 0
    key_facts_count: int = 0


@dataclass
class PerformanceMetrics:
    """Performance and resource metrics"""
    search_time_ms: float = 0.0
    rerank_time_ms: float = 0.0
    generation_time_ms: float = 0.0
    total_time_ms: float = 0.0

    # Token counts
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    # Resource usage
    memory_used_mb: float = 0.0
    cpu_percent: float = 0.0

    # Cache performance
    cache_hits: int = 0
    cache_misses: int = 0


@dataclass
class RetrievalMetrics:
    """Retrieval pipeline metrics"""
    bm25_count: int = 0
    vector_count: int = 0
    rrf_count: int = 0
    filtered_count: int = 0
    final_count: int = 0

    # Average scores
    avg_bm25_score: float = 0.0
    avg_vector_score: float = 0.0
    avg_rrf_score: float = 0.0
    avg_rerank_score: float = 0.0

    # Top scores
    top_bm25_score: float = 0.0
    top_vector_score: float = 0.0
    top_rrf_score: float = 0.0
    top_rerank_score: float = 0.0


@dataclass
class ErrorInfo:
    """Error information"""
    has_error: bool = False
    error_type: str = ""
    error_message: str = ""
    error_traceback: str = ""
    retry_count: int = 0


@dataclass
class QueryLog:
    """Enhanced comprehensive query log entry"""
    # Basic info
    timestamp: str
    session_id: str
    query: str
    query_type: str = "normal"  # normal, greeting, no_evidence, error
    extracted_keywords: List[str] = field(default_factory=list)

    # Retrieval
    retrieval_metrics: RetrievalMetrics = field(default_factory=RetrievalMetrics)
    search_results: List[SearchResult] = field(default_factory=list)

    # Generation
    model_name: str = ""
    model_response: str = ""
    response_sources: List[Dict] = field(default_factory=list)

    # Quality metrics
    quality_metrics: QualityMetrics = field(default_factory=QualityMetrics)

    # Performance metrics
    performance_metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)

    # Error tracking
    error_info: ErrorInfo = field(default_factory=ErrorInfo)

    # User feedback (can be updated later)
    user_feedback: Optional[str] = None
    user_rating: Optional[int] = None  # 1-5

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class QueryLogger:
    """Enhanced centralized query logging with comprehensive metrics"""

    def __init__(self, log_dir: str = "logs/queries"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create dated subdirectory
        today = datetime.now().strftime("%Y-%m-%d")
        self.today_dir = self.log_dir / today
        self.today_dir.mkdir(exist_ok=True)

        # Performance tracking
        self._process = psutil.Process()

        logger.info(f"QueryLogger initialized: {self.today_dir}")

    def log_query(self, query_log: QueryLog):
        """Save enhanced query log to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"query_{timestamp}.json"
        filepath = self.today_dir / filename

        try:
            # Convert dataclass to dict (handle nested dataclasses)
            log_dict = self._dataclass_to_dict(query_log)

            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(log_dict, f, ensure_ascii=False, indent=2)

            # Also log summary to console
            self._log_summary(query_log)

            logger.info(f"Query log saved: {filepath}")

        except Exception as e:
            logger.error(f"Failed to save query log: {e}")
            logger.error(traceback.format_exc())

    def _dataclass_to_dict(self, obj):
        """Convert dataclass to dict recursively"""
        if hasattr(obj, '__dataclass_fields__'):
            return {
                key: self._dataclass_to_dict(value)
                for key, value in asdict(obj).items()
            }
        elif isinstance(obj, list):
            return [self._dataclass_to_dict(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self._dataclass_to_dict(value) for key, value in obj.items()}
        else:
            return obj

    def capture_performance_metrics(self) -> PerformanceMetrics:
        """Capture current performance metrics"""
        try:
            memory_info = self._process.memory_info()
            cpu_percent = self._process.cpu_percent()

            return PerformanceMetrics(
                memory_used_mb=memory_info.rss / 1024 / 1024,
                cpu_percent=cpu_percent
            )
        except Exception as e:
            logger.warning(f"Failed to capture performance metrics: {e}")
            return PerformanceMetrics()

    def calculate_quality_metrics(
        self,
        response: Dict,
        evidences: List,
        answer_text: str
    ) -> QualityMetrics:
        """Calculate quality metrics from response"""
        try:
            verification = response.get("verification", {})
            sources = response.get("sources", [])
            key_facts = response.get("key_facts", [])

            return QualityMetrics(
                confidence_score=verification.get("confidence", 0.0),
                evidence_jaccard=verification.get("jaccard_similarity", 0.0),
                citation_coverage=verification.get("citation_coverage", 0.0),
                hallucination_detected=verification.get("hallucination_detected", False),
                generic_response=len(sources) == 0 or verification.get("confidence", 0) < 0.3,
                has_sources=len(sources) > 0,
                source_count=len(sources),
                evidence_count=len(evidences),
                answer_length=len(answer_text),
                key_facts_count=len(key_facts)
            )
        except Exception as e:
            logger.warning(f"Failed to calculate quality metrics: {e}")
            return QualityMetrics()

    def calculate_retrieval_metrics(self, search_results: List[SearchResult]) -> RetrievalMetrics:
        """Calculate retrieval metrics from search results"""
        try:
            if not search_results:
                return RetrievalMetrics()

            bm25_scores = [r.bm25_score for r in search_results if r.bm25_score > 0]
            vector_scores = [r.vector_score for r in search_results if r.vector_score > 0]
            rrf_scores = [r.rrf_score for r in search_results if r.rrf_score > 0]

            return RetrievalMetrics(
                final_count=len(search_results),
                avg_bm25_score=sum(bm25_scores) / len(bm25_scores) if bm25_scores else 0.0,
                avg_vector_score=sum(vector_scores) / len(vector_scores) if vector_scores else 0.0,
                avg_rrf_score=sum(rrf_scores) / len(rrf_scores) if rrf_scores else 0.0,
                top_bm25_score=max(bm25_scores) if bm25_scores else 0.0,
                top_vector_score=max(vector_scores) if vector_scores else 0.0,
                top_rrf_score=max(rrf_scores) if rrf_scores else 0.0
            )
        except Exception as e:
            logger.warning(f"Failed to calculate retrieval metrics: {e}")
            return RetrievalMetrics()

    def _log_summary(self, query_log: QueryLog):
        """Log enhanced summary to console for quick debugging"""
        logger.info("=" * 80)
        logger.info(f"QUERY [{query_log.query_type}]: {query_log.query}")
        logger.info(f"KEYWORDS: {query_log.extracted_keywords}")

        # Retrieval metrics
        rm = query_log.retrieval_metrics
        logger.info(f"SEARCH PIPELINE: BM25({rm.bm25_count}) + Vector({rm.vector_count}) "
                   f"→ RRF({rm.rrf_count}) → Filtered({rm.filtered_count}) "
                   f"→ Final({rm.final_count})")

        # Log search results
        logger.info(f"\nFINAL {rm.final_count} RESULTS:")
        for i, result in enumerate(query_log.search_results[:5], 1):  # Top 5 only
            logger.info(f"  [{i}] {result.doc_id} (p{result.page})")
            logger.info(f"      BM25={result.bm25_score:.3f}, Vector={result.vector_score:.3f}, "
                       f"RRF={result.rrf_score:.3f}")
            logger.info(f"      Preview: {result.text_preview[:100]}...")

        # Log response summary
        logger.info(f"\nMODEL RESPONSE ({len(query_log.model_response)} chars):")
        logger.info(f"  {query_log.model_response[:200]}...")

        # Quality metrics
        qm = query_log.quality_metrics
        logger.info(f"\nQUALITY METRICS:")
        logger.info(f"  Confidence: {qm.confidence_score:.2f}, Jaccard: {qm.evidence_jaccard:.2f}")
        logger.info(f"  Sources: {qm.source_count}, Evidences: {qm.evidence_count}")
        logger.info(f"  Hallucination: {qm.hallucination_detected}, Generic: {qm.generic_response}")

        # Performance metrics
        pm = query_log.performance_metrics
        logger.info(f"\nPERFORMANCE:")
        logger.info(f"  Search: {pm.search_time_ms:.0f}ms, Rerank: {pm.rerank_time_ms:.0f}ms, "
                   f"Generation: {pm.generation_time_ms:.0f}ms, Total: {pm.total_time_ms:.0f}ms")
        logger.info(f"  Memory: {pm.memory_used_mb:.1f}MB, CPU: {pm.cpu_percent:.1f}%")
        logger.info(f"  Tokens: {pm.total_tokens} (prompt: {pm.prompt_tokens}, completion: {pm.completion_tokens})")

        # Error info
        if query_log.error_info.has_error:
            logger.error(f"\nERROR: {query_log.error_info.error_type}")
            logger.error(f"  Message: {query_log.error_info.error_message}")

        logger.info("=" * 80)

    def load_logs(
        self,
        date: Optional[str] = None,
        limit: Optional[int] = None,
        query_type: Optional[str] = None
    ) -> List[Dict]:
        """Load query logs with filtering"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        report_dir = self.log_dir / date
        if not report_dir.exists():
            return []

        logs = []
        for filepath in sorted(report_dir.glob("query_*.json"), reverse=True):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    log = json.load(f)

                    # Apply filters
                    if query_type and log.get("query_type") != query_type:
                        continue

                    logs.append(log)

                    if limit and len(logs) >= limit:
                        break
            except Exception as e:
                logger.warning(f"Failed to load log {filepath}: {e}")

        return logs

    def get_statistics(self, date: Optional[str] = None) -> Dict:
        """Calculate comprehensive statistics from logs"""
        logs = self.load_logs(date)

        if not logs:
            return {"error": "No logs found"}

        total = len(logs)
        query_types = {}
        total_time = 0
        total_tokens = 0
        total_sources = 0
        total_evidences = 0
        errors = 0
        hallucinations = 0
        generic_responses = 0
        high_confidence = 0

        confidence_scores = []
        search_times = []
        generation_times = []

        for log in logs:
            # Query types
            qtype = log.get("query_type", "normal")
            query_types[qtype] = query_types.get(qtype, 0) + 1

            # Performance
            perf = log.get("performance_metrics", {})
            total_time += perf.get("total_time_ms", 0)
            total_tokens += perf.get("total_tokens", 0)
            search_times.append(perf.get("search_time_ms", 0))
            generation_times.append(perf.get("generation_time_ms", 0))

            # Quality
            qual = log.get("quality_metrics", {})
            total_sources += qual.get("source_count", 0)
            total_evidences += qual.get("evidence_count", 0)
            confidence_scores.append(qual.get("confidence_score", 0))

            if qual.get("hallucination_detected"):
                hallucinations += 1
            if qual.get("generic_response"):
                generic_responses += 1
            if qual.get("confidence_score", 0) >= 0.7:
                high_confidence += 1

            # Errors
            if log.get("error_info", {}).get("has_error"):
                errors += 1

        return {
            "total_queries": total,
            "query_types": query_types,
            "performance": {
                "avg_total_time_ms": total_time / total if total > 0 else 0,
                "avg_search_time_ms": sum(search_times) / len(search_times) if search_times else 0,
                "avg_generation_time_ms": sum(generation_times) / len(generation_times) if generation_times else 0,
                "total_tokens": total_tokens,
                "avg_tokens_per_query": total_tokens / total if total > 0 else 0
            },
            "quality": {
                "avg_confidence": sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0,
                "high_confidence_rate": high_confidence / total if total > 0 else 0,
                "avg_sources_per_query": total_sources / total if total > 0 else 0,
                "avg_evidences_per_query": total_evidences / total if total > 0 else 0,
                "hallucination_rate": hallucinations / total if total > 0 else 0,
                "generic_response_rate": generic_responses / total if total > 0 else 0
            },
            "errors": {
                "error_count": errors,
                "error_rate": errors / total if total > 0 else 0
            }
        }

    def search_logs(
        self,
        query_text: Optional[str] = None,
        date: Optional[str] = None,
        min_confidence: Optional[float] = None,
        has_error: Optional[bool] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Search logs with various filters"""
        logs = self.load_logs(date, limit=limit * 2)  # Load more for filtering

        filtered = []
        for log in logs:
            # Text search
            if query_text and query_text.lower() not in log.get("query", "").lower():
                continue

            # Confidence filter
            if min_confidence is not None:
                confidence = log.get("quality_metrics", {}).get("confidence_score", 0)
                if confidence < min_confidence:
                    continue

            # Error filter
            if has_error is not None:
                log_has_error = log.get("error_info", {}).get("has_error", False)
                if log_has_error != has_error:
                    continue

            filtered.append(log)

            if len(filtered) >= limit:
                break

        return filtered

    def generate_report(self, date: Optional[str] = None) -> str:
        """Generate comprehensive HTML report"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        logs = self.load_logs(date)
        if not logs:
            return f"No logs found for {date}"

        stats = self.get_statistics(date)

        # Generate HTML report
        html = self._generate_html_report(logs, stats, date)

        # Save report
        report_dir = self.log_dir / date
        report_path = report_dir / "report.html"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info(f"Report generated: {report_path}")
        return str(report_path)

    def _generate_html_report(self, logs: List[Dict], stats: Dict, date: str) -> str:
        """Generate enhanced HTML report with comprehensive statistics"""
        html_parts = [
            "<!DOCTYPE html>",
            "<html><head>",
            "<meta charset='utf-8'>",
            f"<title>RAG 시스템 로그 분석 - {date}</title>",
            "<style>",
            "body { font-family: 'Malgun Gothic', Arial, sans-serif; margin: 0; padding: 20px; background: #f5f7fa; }",
            ".container { max-width: 1400px; margin: 0 auto; }",
            "h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }",
            ".stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 30px 0; }",
            ".stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }",
            ".stat-card h3 { margin-top: 0; color: #3498db; border-bottom: 2px solid #ecf0f1; padding-bottom: 8px; }",
            ".stat-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #ecf0f1; }",
            ".stat-label { color: #7f8c8d; }",
            ".stat-value { font-weight: bold; color: #2c3e50; }",
            ".good { color: #27ae60; }",
            ".warning { color: #f39c12; }",
            ".error { color: #e74c3c; }",
            ".query { background: white; margin: 20px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }",
            ".query-header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 8px 8px 0 0; margin: -20px -20px 20px; }",
            ".query-text { font-size: 18px; font-weight: bold; margin-bottom: 8px; }",
            ".query-meta { font-size: 14px; opacity: 0.9; }",
            ".metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 15px 0; }",
            ".metric-box { background: #f8f9fa; padding: 12px; border-radius: 6px; border-left: 4px solid #3498db; }",
            ".metric-label { font-size: 12px; color: #7f8c8d; text-transform: uppercase; }",
            ".metric-value { font-size: 20px; font-weight: bold; color: #2c3e50; margin-top: 5px; }",
            ".search-results { background: #f8f9fa; padding: 15px; border-radius: 6px; margin: 15px 0; }",
            ".result-item { background: white; padding: 12px; margin: 8px 0; border-radius: 4px; border-left: 4px solid #27ae60; }",
            ".doc-id { font-weight: bold; color: #1976D2; margin-bottom: 5px; }",
            ".scores { font-size: 12px; color: #7f8c8d; margin: 5px 0; }",
            ".response-box { background: #e8f5e9; padding: 20px; border-radius: 8px; margin: 15px 0; border: 2px solid #4caf50; }",
            ".response-text { line-height: 1.6; white-space: pre-wrap; }",
            ".quality-indicators { display: flex; gap: 10px; flex-wrap: wrap; margin: 10px 0; }",
            ".indicator { padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }",
            ".ind-good { background: #d4edda; color: #155724; }",
            ".ind-warning { background: #fff3cd; color: #856404; }",
            ".ind-error { background: #f8d7da; color: #721c24; }",
            "</style>",
            "</head><body>",
            "<div class='container'>",
            f"<h1>📊 RAG 시스템 로그 분석 리포트</h1>",
            f"<p style='font-size: 16px; color: #7f8c8d;'>날짜: {date} | 총 {stats['total_queries']}개 질의</p>",
        ]

        # Statistics cards
        perf = stats.get('performance', {})
        qual = stats.get('quality', {})
        errs = stats.get('errors', {})

        # Calculate CSS classes
        conf_class = "good" if qual.get("avg_confidence", 0) >= 0.7 else "warning"
        hall_class = "good" if qual.get("hallucination_rate", 0) == 0 else "error"
        generic_class = "warning" if qual.get("generic_response_rate", 0) > 0.2 else "good"
        error_class = "good" if errs.get("error_count", 0) == 0 else "error"

        html_parts.extend([
            "<div class='stats-grid'>",
            "<div class='stat-card'>",
            "<h3>⚡ 성능 메트릭</h3>",
            f"<div class='stat-row'><span class='stat-label'>평균 응답 시간</span><span class='stat-value'>{perf.get('avg_total_time_ms', 0):.0f}ms</span></div>",
            f"<div class='stat-row'><span class='stat-label'>평균 검색 시간</span><span class='stat-value'>{perf.get('avg_search_time_ms', 0):.0f}ms</span></div>",
            f"<div class='stat-row'><span class='stat-label'>평균 생성 시간</span><span class='stat-value'>{perf.get('avg_generation_time_ms', 0):.0f}ms</span></div>",
            f"<div class='stat-row'><span class='stat-label'>총 토큰 사용</span><span class='stat-value'>{perf.get('total_tokens', 0):,}</span></div>",
            f"<div class='stat-row'><span class='stat-label'>질의당 평균 토큰</span><span class='stat-value'>{perf.get('avg_tokens_per_query', 0):.1f}</span></div>",
            "</div>",

            "<div class='stat-card'>",
            "<h3>✅ 품질 메트릭</h3>",
            f"<div class='stat-row'><span class='stat-label'>평균 신뢰도</span><span class='stat-value {conf_class}'>{qual.get('avg_confidence', 0):.2%}</span></div>",
            f"<div class='stat-row'><span class='stat-label'>고신뢰도 응답 비율</span><span class='stat-value good'>{qual.get('high_confidence_rate', 0):.1%}</span></div>",
            f"<div class='stat-row'><span class='stat-label'>질의당 평균 출처</span><span class='stat-value'>{qual.get('avg_sources_per_query', 0):.1f}</span></div>",
            f"<div class='stat-row'><span class='stat-label'>환각 탐지율</span><span class='stat-value {hall_class}'>{qual.get('hallucination_rate', 0):.1%}</span></div>",
            f"<div class='stat-row'><span class='stat-label'>일반응답 비율</span><span class='stat-value {generic_class}'>{qual.get('generic_response_rate', 0):.1%}</span></div>",
            "</div>",

            "<div class='stat-card'>",
            "<h3>🔴 오류 및 상태</h3>",
            f"<div class='stat-row'><span class='stat-label'>오류 발생 건수</span><span class='stat-value {error_class}'>{errs.get('error_count', 0)}</span></div>",
            f"<div class='stat-row'><span class='stat-label'>오류율</span><span class='stat-value'>{errs.get('error_rate', 0):.1%}</span></div>",
            "</div>",
            "</div>",

            "<h2 style='margin-top: 40px;'>📝 질의 상세 로그</h2>",
        ])

        # Individual queries
        for i, log in enumerate(logs[:20], 1):  # Show first 20
            qtype = log.get('query_type', 'normal')
            qual_metrics = log.get('quality_metrics', {})
            perf_metrics = log.get('performance_metrics', {})
            retr_metrics = log.get('retrieval_metrics', {})

            html_parts.extend([
                "<div class='query'>",
                "<div class='query-header'>",
                f"<div class='query-text'>질의 #{i}: {log.get('query', 'N/A')}</div>",
                f"<div class='query-meta'>타입: {qtype} | 시간: {log.get('timestamp', 'N/A')}</div>",
                "</div>",

                "<div class='quality-indicators'>",
            ])

            # Quality indicators
            conf = qual_metrics.get('confidence_score', 0)
            if conf >= 0.7:
                html_parts.append("<span class='indicator ind-good'>고신뢰도</span>")
            elif conf >= 0.4:
                html_parts.append("<span class='indicator ind-warning'>중간신뢰도</span>")
            else:
                html_parts.append("<span class='indicator ind-error'>저신뢰도</span>")

            if qual_metrics.get('hallucination_detected'):
                html_parts.append("<span class='indicator ind-error'>환각 탐지</span>")
            if qual_metrics.get('generic_response'):
                html_parts.append("<span class='indicator ind-warning'>일반응답</span>")
            if qual_metrics.get('source_count', 0) > 0:
                html_parts.append(f"<span class='indicator ind-good'>{qual_metrics.get('source_count', 0)}개 출처</span>")

            html_parts.append("</div>")

            # Metrics grid
            html_parts.extend([
                "<div class='metrics-grid'>",
                f"<div class='metric-box'><div class='metric-label'>검색 시간</div><div class='metric-value'>{perf_metrics.get('search_time_ms', 0):.0f}ms</div></div>",
                f"<div class='metric-box'><div class='metric-label'>생성 시간</div><div class='metric-value'>{perf_metrics.get('generation_time_ms', 0):.0f}ms</div></div>",
                f"<div class='metric-box'><div class='metric-label'>총 시간</div><div class='metric-value'>{perf_metrics.get('total_time_ms', 0):.0f}ms</div></div>",
                f"<div class='metric-box'><div class='metric-label'>토큰 수</div><div class='metric-value'>{perf_metrics.get('total_tokens', 0)}</div></div>",
                f"<div class='metric-box'><div class='metric-label'>신뢰도</div><div class='metric-value'>{qual_metrics.get('confidence_score', 0):.2f}</div></div>",
                f"<div class='metric-box'><div class='metric-label'>검색 결과</div><div class='metric-value'>{retr_metrics.get('final_count', 0)}</div></div>",
                "</div>",
            ])

            # Response
            response_text = log.get('model_response', 'N/A')
            html_parts.extend([
                "<div class='response-box'>",
                f"<strong>모델 응답 ({log.get('model_name', 'unknown')})</strong>",
                f"<div class='response-text'>{response_text[:500]}{'...' if len(response_text) > 500 else ''}</div>",
                "</div>",
                "</div>",
            ])

        if len(logs) > 20:
            html_parts.append(f"<p style='text-align: center; color: #7f8c8d; margin-top: 20px;'>... 그 외 {len(logs) - 20}개 질의 생략</p>")

        html_parts.extend(["</div></body></html>"])
        return "\n".join(html_parts)


# Global logger instance
_query_logger = None

def get_query_logger() -> QueryLogger:
    """Get singleton query logger instance"""
    global _query_logger
    if _query_logger is None:
        _query_logger = QueryLogger()
    return _query_logger