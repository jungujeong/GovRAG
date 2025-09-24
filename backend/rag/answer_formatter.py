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
    
    def format_response(self, response: Dict, allowed_doc_ids: Optional[List[str]] = None) -> Dict:
        """Format response according to schema"""

        # Clean up response content first
        response = self._clean_response_content(response)

        # Skip invalid source removal for now - it's removing all citations
        # if allowed_doc_ids:
        #     response = self._remove_invalid_source_refs(response, allowed_doc_ids)

        # Filter sources to only include those cited in the answer
        response = self._filter_cited_sources(response)

        # Reorder citations in the answer text to be sequential
        response = self._reorder_citations(response)

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
    
    def _remove_invalid_source_refs(self, response: Dict, allowed_doc_ids: List[str]) -> Dict:
        """Remove invalid source references from answer text"""
        answer = response.get("answer", "")
        key_facts = response.get("key_facts", [])
        details = response.get("details", "")
        sources = response.get("sources", [])

        # Get valid citation numbers
        valid_citations = set()
        for idx, source in enumerate(sources, 1):
            if source.get("doc_id") in allowed_doc_ids:
                valid_citations.add(str(idx))

        # Remove invalid citations from answer
        answer = self._clean_invalid_citations(answer, valid_citations)
        response["answer"] = answer

        # Clean key facts
        cleaned_facts = []
        for fact in key_facts:
            cleaned_fact = self._clean_invalid_citations(fact, valid_citations)
            if cleaned_fact:  # Only keep non-empty facts
                cleaned_facts.append(cleaned_fact)
        response["key_facts"] = cleaned_facts

        # Clean details
        if details:
            response["details"] = self._clean_invalid_citations(details, valid_citations)

        return response

    def _clean_invalid_citations(self, text: str, valid_citations: set) -> str:
        """Remove invalid citation numbers from text"""
        if not text:
            return text

        # Find all citations in format [N]
        def replace_citation(match):
            citation_num = match.group(1)
            if citation_num in valid_citations:
                return match.group(0)  # Keep valid citation
            else:
                logger.warning(f"Removing invalid citation [{citation_num}] from text")
                return ""  # Remove invalid citation

        # Replace invalid citations
        cleaned_text = re.sub(r'\[(\d+)\]', replace_citation, text)

        # Clean up extra spaces
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

        return cleaned_text

    def _filter_cited_sources(self, response: Dict) -> Dict:
        """Keep all sources but mark which ones are cited, preserving original numbering"""
        answer_text = response.get("answer", "")
        sources = response.get("sources", [])
        key_facts = response.get("key_facts", [])
        details = response.get("details", "")
        
        if not sources:
            return response
        
        # Add original index to each source for reference
        for idx, source in enumerate(sources, 1):
            source["original_index"] = idx
            source["is_cited"] = False  # Default to not cited
        
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
            r'\[문서\s*(\d+),\s*\d+\]',  # [문서 1, 116]
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, full_text)
            for match in matches:
                try:
                    num = int(match)
                    cited_numbers.add(num)
                except ValueError:
                    continue
        
        # Mark cited sources
        if cited_numbers:
            for num in cited_numbers:
                if 0 < num <= len(sources):
                    sources[num - 1]["is_cited"] = True
                    logger.info(f"Marking source {num} as cited: {sources[num - 1].get('doc_id')}")
        else:
            # If no explicit citations, try content matching
            logger.info("No explicit citations found, analyzing content to match sources")
            for idx, source in enumerate(sources):
                source_text = source.get("text_snippet", "")
                if source_text and self._content_matches_source(full_text, source_text):
                    source["is_cited"] = True
                    cited_numbers.add(idx + 1)
        
        # If still no citations found, mark top 3 as cited
        if not any(s.get("is_cited") for s in sources):
            logger.warning("Could not match content to sources, marking top 3 as cited")
            for i in range(min(3, len(sources))):
                sources[i]["is_cited"] = True
                cited_numbers.add(i + 1)
        
        # Log the result
        cited_indices = [s["original_index"] for s in sources if s.get("is_cited")]
        logger.info(f"Citation analysis: {len(sources)} total sources, cited: {cited_indices}")
        
        # Check if we're in follow-up mode with fixed citations
        is_followup = response.get("metadata", {}).get("is_followup", False)

        # For follow-up questions with fixed citations, preserve original numbering
        if is_followup and sources and len(sources) > 0 and sources[0].get("display_index"):
            # Keep sources with their existing display_index
            cited_sources = []
            for source in sources:
                if source.get("index") in cited_numbers or source.get("display_index") in cited_numbers:
                    cited_sources.append(source.copy())
            response["sources"] = cited_sources
            return response

        # For new questions, renumber cited sources sequentially
        cited_sources = []
        renumber_map = {}  # Map old citation numbers to new ones
        new_index = 1

        for old_num in sorted(cited_numbers):
            if 0 < old_num <= len(sources):
                source = sources[old_num - 1].copy()
                source["display_index"] = new_index  # New sequential number
                source["original_index"] = old_num   # Keep original for reference
                source["index"] = new_index  # Also set index for compatibility
                cited_sources.append(source)
                renumber_map[old_num] = new_index
                new_index += 1
        
        # Update citation numbers in the answer text
        if renumber_map and response.get("answer"):
            answer_text = response["answer"]
            for old_num, new_num in sorted(renumber_map.items(), reverse=True):
                # Replace [old_num] with [new_num]
                answer_text = re.sub(rf'\[{old_num}\]', f'[{new_num}]', answer_text)
            response["answer"] = answer_text
        
        # Update citation numbers in key_facts
        if renumber_map and response.get("key_facts"):
            updated_facts = []
            for fact in response["key_facts"]:
                for old_num, new_num in sorted(renumber_map.items(), reverse=True):
                    fact = re.sub(rf'\[{old_num}\]', f'[{new_num}]', fact)
                updated_facts.append(fact)
            response["key_facts"] = updated_facts
        
        # Update citation numbers in details
        if renumber_map and response.get("details"):
            details = response["details"]
            for old_num, new_num in sorted(renumber_map.items(), reverse=True):
                details = re.sub(rf'\[{old_num}\]', f'[{new_num}]', details)
            response["details"] = details
        
        response["sources"] = cited_sources
        response["citation_map"] = renumber_map

        logger.info(f"Renumbered {len(cited_sources)} cited sources: {renumber_map}")

        return response

    def _reorder_citations(self, response: Dict) -> Dict:
        """Reorder citation numbers in answer text to be sequential [1], [2], [3]..."""
        answer_text = response.get("answer", "")
        key_facts = response.get("key_facts", [])
        details = response.get("details", "")
        sources = response.get("sources", [])

        if not sources:
            return response

        # Extract all citation numbers from answer text in order of appearance
        # Handle both [숫자] and [문서 숫자, 페이지] patterns
        citation_pattern = re.compile(r'\[(\d+)\]')
        doc_citation_pattern = re.compile(r'\[문서\s*(\d+),\s*\d+\]')

        # Process answer - look for both patterns
        citations_in_answer = citation_pattern.findall(answer_text)
        doc_citations_in_answer = doc_citation_pattern.findall(answer_text)
        citations_in_answer.extend(doc_citations_in_answer)

        # Process key facts
        citations_in_facts = []
        for fact in key_facts:
            citations_in_facts.extend(citation_pattern.findall(fact))
            citations_in_facts.extend(doc_citation_pattern.findall(fact))

        # Process details
        citations_in_details = []
        if details:
            citations_in_details.extend(citation_pattern.findall(details))
            citations_in_details.extend(doc_citation_pattern.findall(details))

        # Combine all citations while preserving order
        all_citations = citations_in_answer + citations_in_facts + citations_in_details

        # Create mapping from old number to new number
        citation_map = {}
        new_number = 1
        seen_citations = set()

        for old_num_str in all_citations:
            old_num = int(old_num_str)
            if old_num not in seen_citations:
                seen_citations.add(old_num)
                citation_map[old_num] = new_number
                new_number += 1

        # Replace citations in text with new numbers
        def replace_citation(match):
            old_num = int(match.group(1))
            if old_num in citation_map:
                return f"[{citation_map[old_num]}]"
            return match.group(0)

        # Update answer text - replace both patterns
        if answer_text:
            # First replace [문서 X, Y] with [X]
            answer_text = doc_citation_pattern.sub(lambda m: f"[{m.group(1)}]", answer_text)
            # Then apply the renumbering
            response["answer"] = citation_pattern.sub(replace_citation, answer_text)

        # Update key facts
        if key_facts:
            new_facts = []
            for fact in key_facts:
                # First replace [문서 X, Y] with [X]
                fact = doc_citation_pattern.sub(lambda m: f"[{m.group(1)}]", fact)
                # Then apply renumbering
                fact = citation_pattern.sub(replace_citation, fact)
                new_facts.append(fact)
            response["key_facts"] = new_facts

        # Update details
        if details:
            # First replace [문서 X, Y] with [X]
            details = doc_citation_pattern.sub(lambda m: f"[{m.group(1)}]", details)
            # Then apply renumbering
            response["details"] = citation_pattern.sub(replace_citation, details)

        # Reorder sources based on new citation numbers
        cited_sources = []
        for old_num, new_num in sorted(citation_map.items(), key=lambda x: x[1]):
            if 0 < old_num <= len(sources):
                source = sources[old_num - 1].copy()
                source["display_index"] = new_num
                source["original_index"] = old_num
                cited_sources.append(source)

        # Include non-cited sources at the end (optional)
        for idx, source in enumerate(sources, 1):
            if idx not in citation_map:
                source_copy = source.copy()
                source_copy["display_index"] = None
                source_copy["original_index"] = idx
                source_copy["is_cited"] = False
                # Don't add uncited sources to cited_sources list

        response["sources"] = cited_sources
        response["citation_map"] = citation_map

        logger.info(f"Reordered citations: {citation_map}")

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

        # First preserve existing line breaks if they exist
        if '\n\n' in text:
            # Keep existing formatting
            return text

        # Replace single line breaks with double for better spacing
        if '\n' in text:
            text = text.replace('\n', '\n\n')

        # Split long paragraphs at sentence boundaries
        sentences = re.split(r'([.!?]\s+)', text)

        result = []
        current_paragraph = ""
        sentence_count = 0

        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            separator = sentences[i + 1] if i + 1 < len(sentences) else ""

            # Add sentence to current paragraph
            current_paragraph += sentence + separator
            sentence_count += 1

            # Natural break points - comprehensive list
            natural_breaks = [
                '또한', '그리고', '하지만', '따라서', '즉,', '예를 들어',
                '첫째', '둘째', '셋째', '넷째', '다섯째',
                '마지막으로', '결론적으로', '요약하면',
                '특히', '반면', '그러나', '게다가', '아울러',
                '한편', '다만', '단,', '참고로', '추가로',
                '이와 관련하여', '이에 따라', '그 결과',
                '구체적으로', '세부적으로', '종합하면'
            ]

            # Check if we should start a new paragraph
            should_break = False

            # Break at natural transition points
            for marker in natural_breaks:
                if sentence.startswith(marker) or f' {marker}' in sentence:
                    should_break = True
                    break

            # Break after 1-2 sentences for readability
            if not should_break and sentence_count >= 2:
                should_break = True

            # Break at numbered items
            if re.match(r'^\d+[.)]\s', sentence):
                should_break = True

            # Break at bullet points
            if sentence.strip().startswith(('•', '-', '*', '○', '●')):
                should_break = True

            if should_break and current_paragraph.strip():
                result.append(current_paragraph.strip())
                current_paragraph = ""
                sentence_count = 0

        # Add remaining content
        if current_paragraph.strip():
            result.append(current_paragraph.strip())

        # Join with double line break for better spacing
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