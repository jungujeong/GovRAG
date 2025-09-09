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
        
        # Clean up response content first
        response = self._clean_response_content(response)
        
        # Filter sources to only include those cited in the answer
        response = self._filter_cited_sources(response)
        
        formatted = {
            "formatted_text": self._format_as_text(response),
            "formatted_html": self._format_as_html(response),
            "formatted_json": self._format_as_json(response),
            "formatted_markdown": self._format_as_markdown(response)
        }
        
        # Add formatted versions to original response
        response.update(formatted)
        
        return response
    
    def _clean_response_content(self, response: Dict) -> Dict:
        """Clean up response content to ensure Korean-only and accurate department names"""
        # Clean answer
        if response.get("answer"):
            response["answer"] = self._clean_text(response["answer"])
        
        # Clean key facts
        if response.get("key_facts"):
            response["key_facts"] = [self._clean_text(fact) for fact in response["key_facts"]]
        
        # Clean details
        if response.get("details"):
            response["details"] = self._clean_text(response["details"])
        
        return response
    
    def _clean_text(self, text: str) -> str:
        """Clean text to keep only Korean and necessary characters"""
        if not text:
            return text
        
        # Filter to keep only Korean, ASCII, and common punctuation
        cleaned_chars = []
        for char in text:
            code = ord(char)
            # Keep Korean characters
            if (0xAC00 <= code <= 0xD7AF or  # Hangul Syllables
                0x1100 <= code <= 0x11FF or  # Hangul Jamo
                0x3130 <= code <= 0x318F or  # Hangul Compatibility Jamo
                0xA960 <= code <= 0xA97F or  # Hangul Jamo Extended-A
                0xD7B0 <= code <= 0xD7FF):   # Hangul Jamo Extended-B
                cleaned_chars.append(char)
            # Keep ASCII printable characters
            elif 0x0020 <= code <= 0x007E:
                cleaned_chars.append(char)
            # Keep common Korean punctuation
            elif char in '·、。「」『』〈〉《》【】〔〕':
                cleaned_chars.append(char)
            # Replace other characters with space
            else:
                cleaned_chars.append(' ')
        
        result = ''.join(cleaned_chars)
        
        # Clean up multiple spaces
        result = re.sub(r'\s+', ' ', result)
        
        # Ensure department names are properly formatted (comma-separated)
        result = re.sub(r'([가-힣]+과)\s+([가-힣]+과)', r'\1, \2', result)
        
        return result.strip()
    
    def _format_as_text(self, response: Dict) -> str:
        """Format as plain text"""
        lines = []
        
        # 1. Core answer - ensure proper line breaks
        if response.get("answer"):
            lines.append(f"{self.section_headers['answer']}")
            # Add line breaks for better readability
            answer_text = self._add_natural_line_breaks(response["answer"])
            lines.append(answer_text)
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
            details_text = self._add_natural_line_breaks(response["details"])
            lines.append(details_text)
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
    
    def _filter_cited_sources(self, response: Dict) -> Dict:
        """Filter sources to only include those actually cited in the answer text"""
        answer_text = response.get("answer", "")
        sources = response.get("sources", [])
        key_facts = response.get("key_facts", [])
        details = response.get("details", "")
        
        if not sources:
            return response
        
        # Combine all text to check for citations
        full_text = answer_text
        if key_facts:
            full_text += " " + " ".join(key_facts)
        if details:
            full_text += " " + details
        
        if not full_text:
            return response
        
        # Extract all citation numbers from the combined text
        cited_numbers = set()
        
        # Look for various citation patterns
        patterns = [
            r'\[(\d+)\]',          # [1], [2]
            r'\d+\.\[(\d+)\]',     # 1.[1], 2.[1]
            r'문서\s*(\d+)',        # 문서 1, 문서1
            r'\*\*문서\s*(\d+)',    # **문서 1
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, full_text)
            for match in matches:
                try:
                    num = int(match)
                    cited_numbers.add(num)
                except ValueError:
                    continue
        
        # If no citations found, analyze content to determine which sources were used
        if not cited_numbers:
            logger.info("No explicit citations found, analyzing content to match sources")
            # Try to match content with sources
            for idx, source in enumerate(sources, 1):
                source_text = source.get("text_snippet", "")
                if source_text and self._content_matches_source(full_text, source_text):
                    cited_numbers.add(idx)
            
            # If still no matches, keep top sources
            if not cited_numbers:
                logger.warning("Could not match content to sources, keeping top 3")
                response["sources"] = sources[:3]
                return response
        
        # Ensure all cited numbers are valid
        valid_cited = set()
        for num in cited_numbers:
            if 0 < num <= len(sources):
                valid_cited.add(num)
        
        # Filter sources based on cited numbers
        filtered_sources = []
        for num in sorted(valid_cited):
            if num <= len(sources):
                filtered_sources.append(sources[num - 1])
        
        # Log the filtering result
        logger.info(f"Citation filtering: {len(sources)} sources -> {len(filtered_sources)} cited sources {sorted(valid_cited)}")
        
        # Update response with filtered sources
        response["sources"] = filtered_sources
        
        return response
    
    def _content_matches_source(self, answer_text: str, source_text: str) -> bool:
        """Check if answer content matches source text"""
        if not answer_text or not source_text:
            return False
        
        # Normalize both texts
        norm_answer = re.sub(r'\s+', ' ', answer_text.lower())
        norm_source = re.sub(r'\s+', ' ', source_text.lower())
        
        # Extract key terms from answer (Korean words > 2 chars)
        answer_words = set(re.findall(r'[가-힣]{3,}', norm_answer))
        source_words = set(re.findall(r'[가-힣]{3,}', norm_source))
        
        if not answer_words or not source_words:
            return False
        
        # Calculate overlap
        overlap = len(answer_words.intersection(source_words))
        min_words = min(len(answer_words), len(source_words))
        
        # If significant overlap (> 30%), consider it a match
        return (overlap / min_words) > 0.3 if min_words > 0 else False
    
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
    
    def _add_natural_line_breaks(self, text: str) -> str:
        """Add natural line breaks for better readability"""
        if not text:
            return text
        
        # Split long paragraphs at sentence boundaries
        sentences = re.split(r'([.!?]\s+)', text)
        
        result = []
        current_paragraph = ""
        
        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            separator = sentences[i + 1] if i + 1 < len(sentences) else ""
            
            # Add sentence to current paragraph
            current_paragraph += sentence + separator
            
            # Check if we should start a new paragraph
            # (after 2-3 sentences or at natural breaks)
            sentence_count = len(re.findall(r'[.!?]', current_paragraph))
            
            # Natural break points
            if any(marker in sentence for marker in ['또한', '그리고', '하지만', '따라서', '즉,', '예를 들어']):
                if current_paragraph.strip():
                    result.append(current_paragraph.strip())
                    current_paragraph = ""
            # Or after 2-3 sentences
            elif sentence_count >= 2:
                if current_paragraph.strip():
                    result.append(current_paragraph.strip())
                    current_paragraph = ""
        
        # Add remaining content
        if current_paragraph.strip():
            result.append(current_paragraph.strip())
        
        # Join with double line breaks for paragraphs
        return "\n\n".join(result)
    
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