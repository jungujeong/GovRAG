from typing import Dict, List, Optional
import json
import re
import logging

logger = logging.getLogger(__name__)

class AnswerFormatter:
    """Format answers according to 4-section schema"""
    
    def __init__(self):
        self.section_headers = {
            "answer": "📌 핵심 답변",
            "key_facts": "📊 주요 사실",
            "details": "📝 상세 설명",
            "sources": "📚 출처"
        }
    
    def format_response(self, response: Dict) -> Dict:
        """Format response according to schema"""
        
        formatted = {
            "formatted_text": self._format_as_text(response),
            "formatted_html": self._format_as_html(response),
            "formatted_json": self._format_as_json(response),
            "formatted_markdown": self._format_as_markdown(response)
        }
        
        # Add formatted versions to original response
        response.update(formatted)
        
        return response
    
    def _format_as_text(self, response: Dict) -> str:
        """Format as plain text"""
        lines = []
        
        # 1. Core answer
        if response.get("answer"):
            lines.append(f"{self.section_headers['answer']}")
            lines.append(response["answer"])
            lines.append("")
        
        # 2. Key facts
        if response.get("key_facts"):
            lines.append(f"{self.section_headers['key_facts']}")
            for fact in response["key_facts"]:
                lines.append(f"  • {fact}")
            lines.append("")
        
        # 3. Details (optional)
        if response.get("details"):
            lines.append(f"{self.section_headers['details']}")
            lines.append(response["details"])
            lines.append("")
        
        # 4. Sources
        if response.get("sources"):
            lines.append(f"{self.section_headers['sources']}")
            for idx, source in enumerate(response["sources"], 1):
                doc_id = source.get("doc_id", "unknown")
                page = source.get("page", 0)
                lines.append(f"  [{idx}] {doc_id}, {page}페이지")
        
        return "\n".join(lines)
    
    def _format_as_html(self, response: Dict) -> str:
        """Format as HTML"""
        html_parts = ['<div class="rag-response">']
        
        # Core answer
        if response.get("answer"):
            html_parts.append(
                f'<div class="answer-section">'
                f'<h3>{self.section_headers["answer"]}</h3>'
                f'<p>{self._escape_html(response["answer"])}</p>'
                f'</div>'
            )
        
        # Key facts
        if response.get("key_facts"):
            html_parts.append(
                f'<div class="facts-section">'
                f'<h3>{self.section_headers["key_facts"]}</h3>'
                f'<ul>'
            )
            for fact in response["key_facts"]:
                html_parts.append(f'<li>{self._escape_html(fact)}</li>')
            html_parts.append('</ul></div>')
        
        # Details
        if response.get("details"):
            html_parts.append(
                f'<div class="details-section">'
                f'<h3>{self.section_headers["details"]}</h3>'
                f'<p>{self._escape_html(response["details"])}</p>'
                f'</div>'
            )
        
        # Sources
        if response.get("sources"):
            html_parts.append(
                f'<div class="sources-section">'
                f'<h3>{self.section_headers["sources"]}</h3>'
                f'<ol>'
            )
            for source in response["sources"]:
                doc_id = self._escape_html(source.get("doc_id", "unknown"))
                page = source.get("page", 0)
                chunk_id = source.get("chunk_id", "")
                
                html_parts.append(
                    f'<li data-chunk-id="{chunk_id}">'
                    f'{doc_id}, {page}페이지'
                    f'</li>'
                )
            html_parts.append('</ol></div>')
        
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)
    
    def _format_as_markdown(self, response: Dict) -> str:
        """Format as Markdown"""
        md_parts = []
        
        # Core answer
        if response.get("answer"):
            md_parts.append(f"### {self.section_headers['answer']}")
            md_parts.append(response["answer"])
            md_parts.append("")
        
        # Key facts
        if response.get("key_facts"):
            md_parts.append(f"### {self.section_headers['key_facts']}")
            for fact in response["key_facts"]:
                md_parts.append(f"- {fact}")
            md_parts.append("")
        
        # Details
        if response.get("details"):
            md_parts.append(f"### {self.section_headers['details']}")
            md_parts.append(response["details"])
            md_parts.append("")
        
        # Sources
        if response.get("sources"):
            md_parts.append(f"### {self.section_headers['sources']}")
            for idx, source in enumerate(response["sources"], 1):
                doc_id = source.get("doc_id", "unknown")
                page = source.get("page", 0)
                md_parts.append(f"{idx}. `{doc_id}`, {page}페이지")
        
        return "\n".join(md_parts)
    
    def _format_as_json(self, response: Dict) -> str:
        """Format as JSON"""
        json_data = {
            "answer": response.get("answer", ""),
            "key_facts": response.get("key_facts", []),
            "details": response.get("details", ""),
            "sources": response.get("sources", []),
            "metadata": {
                "confidence": response.get("verification", {}).get("confidence", 0),
                "evidence_count": len(response.get("sources", [])),
                "hallucination_detected": response.get("verification", {}).get("hallucination_detected", False)
            }
        }
        
        return json.dumps(json_data, ensure_ascii=False, indent=2)
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters"""
        replacements = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#x27;"
        }
        
        for char, escape in replacements.items():
            text = text.replace(char, escape)
        
        return text
    
    def format_error_response(self, error: str, query: str) -> Dict:
        """Format error response"""
        return {
            "answer": "죄송합니다. 요청을 처리할 수 없습니다.",
            "key_facts": [
                "시스템 오류가 발생했습니다.",
                "잠시 후 다시 시도해주세요."
            ],
            "details": f"오류: {error}",
            "sources": [],
            "error": True,
            "error_message": error,
            "original_query": query
        }