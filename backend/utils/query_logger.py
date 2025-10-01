"""Query logging system for debugging RAG retrieval and generation"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import os

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
class QueryLog:
    """Complete query log entry"""
    timestamp: str
    session_id: str
    query: str
    extracted_keywords: List[str]

    # Search stage
    bm25_count: int
    vector_count: int
    rrf_count: int
    filtered_count: int
    final_count: int

    # Final results
    search_results: List[SearchResult]

    # Generation stage
    model_name: str
    model_response: str
    response_sources: List[Dict]

    # Timing
    search_time_ms: float
    generation_time_ms: float
    total_time_ms: float


class QueryLogger:
    """Centralized query logging for debugging"""

    def __init__(self, log_dir: str = "logs/queries"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create dated subdirectory
        today = datetime.now().strftime("%Y-%m-%d")
        self.today_dir = self.log_dir / today
        self.today_dir.mkdir(exist_ok=True)

        logger.info(f"QueryLogger initialized: {self.today_dir}")

    def log_query(self, query_log: QueryLog):
        """Save query log to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"query_{timestamp}.json"
        filepath = self.today_dir / filename

        try:
            # Convert dataclass to dict
            log_dict = asdict(query_log)

            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(log_dict, f, ensure_ascii=False, indent=2)

            # Also log summary to console
            self._log_summary(query_log)

            logger.info(f"Query log saved: {filepath}")

        except Exception as e:
            logger.error(f"Failed to save query log: {e}")

    def _log_summary(self, query_log: QueryLog):
        """Log summary to console for quick debugging"""
        logger.info("=" * 80)
        logger.info(f"QUERY: {query_log.query}")
        logger.info(f"KEYWORDS: {query_log.extracted_keywords}")
        logger.info(f"SEARCH PIPELINE: BM25({query_log.bm25_count}) + Vector({query_log.vector_count}) "
                   f"→ RRF({query_log.rrf_count}) → Filtered({query_log.filtered_count}) "
                   f"→ Final({query_log.final_count})")

        # Log each final result
        logger.info(f"\nFINAL {query_log.final_count} RESULTS:")
        for i, result in enumerate(query_log.search_results, 1):
            logger.info(f"  [{i}] {result.doc_id} (p{result.page})")
            logger.info(f"      RRF={result.rrf_score:.3f}, KW={result.keyword_relevance:.3f}, "
                       f"Reason={result.include_reason}")
            logger.info(f"      Preview: {result.text_preview[:100]}...")

        # Log response summary
        logger.info(f"\nMODEL RESPONSE ({len(query_log.model_response)} chars):")
        logger.info(f"  {query_log.model_response[:200]}...")

        # Log sources
        logger.info(f"\nCITED SOURCES: {len(query_log.response_sources)}")
        for src in query_log.response_sources:
            logger.info(f"  - {src.get('doc_id', 'unknown')} (page {src.get('page', 'unknown')})")

        # Log timing
        logger.info(f"\nTIMING: Search={query_log.search_time_ms:.0f}ms, "
                   f"Generation={query_log.generation_time_ms:.0f}ms, "
                   f"Total={query_log.total_time_ms:.0f}ms")
        logger.info("=" * 80)

    def generate_report(self, date: Optional[str] = None) -> str:
        """Generate HTML report for a given date"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        report_dir = self.log_dir / date
        if not report_dir.exists():
            return f"No logs found for {date}"

        # Load all logs for the date
        logs = []
        for filepath in sorted(report_dir.glob("query_*.json")):
            with open(filepath, 'r', encoding='utf-8') as f:
                logs.append(json.load(f))

        # Generate HTML report
        html = self._generate_html_report(logs, date)

        # Save report
        report_path = report_dir / "report.html"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info(f"Report generated: {report_path}")
        return str(report_path)

    def _generate_html_report(self, logs: List[Dict], date: str) -> str:
        """Generate HTML report from logs"""
        html_parts = [
            "<!DOCTYPE html>",
            "<html><head>",
            "<meta charset='utf-8'>",
            f"<title>Query Log Report - {date}</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }",
            ".query { background: white; margin: 20px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
            ".header { border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 15px; }",
            ".query-text { font-size: 18px; font-weight: bold; color: #333; }",
            ".keywords { color: #666; margin: 5px 0; }",
            ".pipeline { background: #f0f0f0; padding: 10px; margin: 10px 0; border-radius: 4px; }",
            ".result { border-left: 3px solid #4CAF50; padding-left: 10px; margin: 10px 0; }",
            ".irrelevant { border-left-color: #f44336; }",
            ".doc-id { font-weight: bold; color: #1976D2; }",
            ".scores { color: #666; font-size: 14px; }",
            ".response { background: #e3f2fd; padding: 15px; margin: 15px 0; border-radius: 4px; }",
            ".timing { color: #666; font-size: 14px; margin-top: 10px; }",
            "</style>",
            "</head><body>",
            f"<h1>Query Log Report - {date}</h1>",
            f"<p>Total queries: {len(logs)}</p>",
        ]

        for log in logs:
            html_parts.extend([
                "<div class='query'>",
                "<div class='header'>",
                f"<div class='query-text'>Q: {log['query']}</div>",
                f"<div class='keywords'>Keywords: {', '.join(log['extracted_keywords'])}</div>",
                "</div>",

                "<div class='pipeline'>",
                f"Pipeline: BM25({log['bm25_count']}) + Vector({log['vector_count']}) "
                f"→ RRF({log['rrf_count']}) → Filtered({log['filtered_count']}) → Final({log['final_count']})",
                "</div>",

                "<h3>Search Results:</h3>",
            ])

            for result in log['search_results']:
                relevance_class = "result" if result['keyword_relevance'] > 0.15 else "result irrelevant"
                html_parts.extend([
                    f"<div class='{relevance_class}'>",
                    f"<div class='doc-id'>{result['doc_id']} (page {result['page']})</div>",
                    f"<div class='scores'>RRF: {result['rrf_score']:.3f}, "
                    f"Keyword: {result['keyword_relevance']:.3f}, "
                    f"Reason: {result['include_reason']}</div>",
                    f"<div>{result['text_preview']}</div>",
                    "</div>",
                ])

            html_parts.extend([
                "<div class='response'>",
                f"<h3>Model Response ({log['model_name']}):</h3>",
                f"<p>{log['model_response'][:500]}...</p>",
                f"<p><strong>Cited sources:</strong> {len(log['response_sources'])}</p>",
                "</div>",

                "<div class='timing'>",
                f"⏱️ Search: {log['search_time_ms']:.0f}ms | "
                f"Generation: {log['generation_time_ms']:.0f}ms | "
                f"Total: {log['total_time_ms']:.0f}ms",
                "</div>",
                "</div>",
            ])

        html_parts.extend(["</body></html>"])
        return "\n".join(html_parts)


# Global logger instance
_query_logger = None

def get_query_logger() -> QueryLogger:
    """Get singleton query logger instance"""
    global _query_logger
    if _query_logger is None:
        _query_logger = QueryLogger()
    return _query_logger