import re
from typing import Dict, List, Tuple, Optional
import json
import logging
import numpy as np
import unicodedata
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class CitationTracker:
    """Track and format citations with coordinates"""
    
    def __init__(self):
        self.citations = []
        self.citation_map = {}
        self.embedder = None
        self._init_embedder()
    
    def track_citations(self,
                       response: Dict,
                       evidences: List[Dict],
                       allowed_doc_ids: Optional[List[str]] = None,
                       fixed_citation_map: Optional[Dict[str, int]] = None) -> Dict:
        """Add citation tracking to response

        SIMPLIFIED APPROACH:
        - NO filtering here - evidences are already filtered in chat.py
        - Focus only on citation numbering consistency
        - Use fixed_citation_map when provided for follow-up questions
        """

        # Extract citations from response
        answer = response.get("answer", "")
        sources = response.get("sources", [])

        # NO FILTERING - Trust that evidences are already correctly filtered
        # This eliminates duplicate filtering logic and Unicode normalization issues

        # Just log for debugging
        if allowed_doc_ids:
            logger.info(f"Citation tracking with allowed_doc_ids: {allowed_doc_ids}")
            logger.info(f"Evidence count: {len(evidences)}, Source count: {len(sources)}")

        # Create citation map from evidences
        self.citation_map = self._build_citation_map(evidences)

        # Use fixed citation map if provided (for follow-up questions)
        if fixed_citation_map:
            # Add inline citations using fixed mapping
            answer_with_citations = self._add_inline_citations_with_fixed_map(answer, evidences, fixed_citation_map)
            response["answer"] = answer_with_citations

            # Format sources using fixed mapping
            formatted_sources = self._format_sources_with_fixed_map(sources, evidences, fixed_citation_map)
            response["sources"] = self._dedupe_sources(formatted_sources)

            # Store the citation map for return
            response["citation_map"] = fixed_citation_map
        else:
            # Add inline citations to answer (first response)
            answer_with_citations, used_citation_map = self._add_inline_citations_with_map_tracking(answer, evidences)
            response["answer"] = answer_with_citations

            # FIXED: Format sources using the cited evidence map
            # This ensures ALL cited evidences become sources
            formatted_sources = self._format_sources_from_cited_map(evidences, used_citation_map)
            response["sources"] = self._dedupe_sources(formatted_sources)

            # Store the citation map for future use
            response["citation_map"] = used_citation_map

        # Add citation JSON
        response["citations_json"] = json.dumps(
            formatted_sources if "sources" in response else [],
            ensure_ascii=False,
            indent=2
        )

        return response
    
    def _build_citation_map(self, evidences: List[Dict]) -> Dict:
        """Build map of evidence to citation format"""
        citation_map = {}
        
        for idx, evidence in enumerate(evidences, 1):
            raw_id = evidence.get('doc_id', '') or ''
            norm_id = unicodedata.normalize('NFC', str(raw_id).strip())
            key = f"{norm_id}_{evidence.get('page', 0)}"
            citation_map[key] = {
                "index": idx,
                "doc_id": norm_id or "unknown",
                "page": evidence.get("page", 0),
                "start_char": evidence.get("start_char", -1),
                "end_char": evidence.get("end_char", -1),
                "chunk_id": evidence.get("chunk_id", "")
            }
        
        return citation_map

    def _dedupe_sources(self, sources: List[Dict]) -> List[Dict]:
        """Remove duplicate sources by normalized (doc_id, page, chunk_id)."""
        seen = set()
        deduped: List[Dict] = []
        for s in sources or []:
            raw_id = s.get('doc_id') or s.get('metadata', {}).get('doc_id') or ''
            norm_id = unicodedata.normalize('NFC', str(raw_id).strip())
            page = s.get('page', 0)
            chunk_id = s.get('chunk_id', '')
            key = (norm_id, page, chunk_id)
            if key in seen:
                continue
            seen.add(key)
            s = dict(s)
            s['doc_id'] = norm_id
            deduped.append(s)
        return deduped
    
    def _add_inline_citations(self, text: str, evidences: List[Dict]) -> str:
        """Add inline citation markers to text - ensuring sequential numbering"""

        # Track which evidences have been cited
        cited_evidences = {}
        next_citation_num = 1

        # Process text to fix citations
        lines = text.split('\n')
        fixed_lines = []

        for line in lines:
            # Check if this line contains numbered items with citations
            if re.match(r'^\d+\.\[', line):
                # Extract the content and find matching evidence
                fixed_line = self._fix_line_citation_sequential(line, evidences, cited_evidences, next_citation_num)
                # Update next citation number if new citation was added
                if fixed_line != line:
                    # Check if a new citation was added
                    match = re.search(r'\[(\d+)\]', fixed_line)
                    if match:
                        cite_num = int(match.group(1))
                        if cite_num >= next_citation_num:
                            next_citation_num = cite_num + 1
                fixed_lines.append(fixed_line)
            else:
                # For non-numbered lines, add citations based on content matching
                fixed_line = self._add_citations_to_line_sequential(line, evidences, cited_evidences, next_citation_num)
                # Update next citation number if new citation was added
                if fixed_line != line:
                    match = re.search(r'\[(\d+)\]', fixed_line)
                    if match:
                        cite_num = int(match.group(1))
                        if cite_num >= next_citation_num:
                            next_citation_num = cite_num + 1
                fixed_lines.append(fixed_line)

        return '\n'.join(fixed_lines)
    
    def _fix_line_citation_sequential(self, line: str, evidences: List[Dict], cited_evidences: Dict, next_num: int) -> str:
        """Fix citation number in a numbered line with sequential numbering"""
        # Extract item number and content
        match = re.match(r'^(\d+)\.\[(\d+)\]\s*(.*)', line)
        if not match:
            return line

        item_num = match.group(1)
        old_cite = match.group(2)
        content = match.group(3)

        # Find the best matching evidence for this content
        best_match_evidence = None
        best_score = 0

        for evidence in evidences:
            evidence_text = evidence.get("text", "")
            score = self._calculate_content_similarity(content, evidence_text)

            if score > best_score:
                best_score = score
                best_match_evidence = evidence

        # If we found a good match, assign sequential citation number
        if best_match_evidence and best_score > 0.3:
            # Create unique key for this evidence
            evidence_key = f"{best_match_evidence.get('doc_id', '')}_{best_match_evidence.get('page', 0)}_{best_match_evidence.get('chunk_id', '')}"

            # Check if already cited
            if evidence_key in cited_evidences:
                cite_num = cited_evidences[evidence_key]
            else:
                # Assign new sequential number
                cite_num = len(cited_evidences) + 1
                cited_evidences[evidence_key] = cite_num

            return f"{item_num}.[{cite_num}] {content}"
        else:
            # Keep original if no good match found
            return line
    
    def _add_citations_to_line_sequential(self, line: str, evidences: List[Dict], cited_evidences: Dict, next_num: int) -> str:
        """Add citations to a line based on content matching with sequential numbering"""
        if not line.strip():
            return line

        # Check which evidence this line matches
        best_match_evidence = None
        best_score = 0

        for evidence in evidences:
            evidence_text = evidence.get("text", "")
            score = self._calculate_content_similarity(line, evidence_text)

            if score > best_score:
                best_score = score
                best_match_evidence = evidence

        # Add citation if good match found and not already present
        if best_match_evidence and best_score > 0.3 and not re.search(r'\[\d+\]', line):
            # Create unique key for this evidence
            evidence_key = f"{best_match_evidence.get('doc_id', '')}_{best_match_evidence.get('page', 0)}_{best_match_evidence.get('chunk_id', '')}"

            # Check if already cited
            if evidence_key in cited_evidences:
                cite_num = cited_evidences[evidence_key]
            else:
                # Assign new sequential number
                cite_num = len(cited_evidences) + 1
                cited_evidences[evidence_key] = cite_num

            return f"{line}[{cite_num}]"

        return line
    
    def _calculate_content_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text segments"""
        # Normalize texts
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Check for substring match
        if norm1 in norm2:
            return 1.0
        
        # Calculate word overlap
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        
        # Use Jaccard similarity
        union = words1.union(words2)
        jaccard = len(intersection) / len(union) if union else 0.0
        
        # Also consider partial matches for Korean text
        # (important keywords matching is more important than exact phrase matching)
        important_keywords = self._extract_important_keywords(norm1)
        if important_keywords:
            keyword_matches = sum(1 for kw in important_keywords if kw in norm2)
            keyword_score = keyword_matches / len(important_keywords)
            
            # Weighted average of jaccard and keyword matching
            return 0.6 * jaccard + 0.4 * keyword_score
        
        return jaccard
    
    def _extract_important_keywords(self, text: str) -> List[str]:
        """Extract important keywords from text"""
        # Remove common Korean particles and short words
        words = text.split()
        keywords = []
        
        for word in words:
            # Keep words that are likely to be meaningful (longer than 2 chars)
            if len(word) > 2:
                keywords.append(word)
        
        return keywords
    
    def _sentence_from_evidence(self, sentence: str, evidence: str) -> bool:
        """Check if sentence comes from evidence"""
        # Normalize for comparison
        norm_sentence = self._normalize_text(sentence)
        norm_evidence = self._normalize_text(evidence)
        
        # Check for substring match
        return norm_sentence in norm_evidence or self._fuzzy_match(norm_sentence, norm_evidence)
    
    def _fuzzy_match(self, text1: str, text2: str, threshold: float = 0.8) -> bool:
        """Fuzzy matching for text similarity"""
        from rapidfuzz import fuzz
        
        ratio = fuzz.partial_ratio(text1, text2) / 100.0
        return ratio >= threshold
    
    def _format_sources(self, 
                       sources: List[Dict],
                       evidences: List[Dict]) -> List[Dict]:
        """Format source citations with full information"""
        
        formatted = []
        
        # If sources are empty, create from evidences
        if not sources and evidences:
            for idx, evidence in enumerate(evidences, 1):
                formatted.append({
                    "index": idx,
                    "doc_id": evidence.get("doc_id", "unknown"),
                    "page": evidence.get("page", 0),
                    "start_char": evidence.get("start_char", -1),
                    "end_char": evidence.get("end_char", -1),
                    "chunk_id": evidence.get("chunk_id", ""),
                    "text_snippet": evidence.get("text", "")
                })
        else:
            # Enhance existing sources with evidence data
            for source in sources:
                doc_id = source.get("doc_id")
                page = source.get("page", 0)
                
                # Find matching evidence
                matching_evidence = None
                for evidence in evidences:
                    if (evidence.get("doc_id") == doc_id and 
                        evidence.get("page", 0) == page):
                        matching_evidence = evidence
                        break
                
                if matching_evidence:
                    formatted.append({
                        "doc_id": doc_id,
                        "page": page,
                        "start_char": matching_evidence.get("start_char", -1),
                        "end_char": matching_evidence.get("end_char", -1),
                        "chunk_id": matching_evidence.get("chunk_id", ""),
                        "text_snippet": matching_evidence.get("text", "")
                    })
                else:
                    formatted.append(source)
        
        return formatted
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove punctuation
        text = re.sub(r'[^\w\s가-힣]', '', text)
        # Lowercase
        text = text.lower().strip()
        return text
    
    def format_citation_display(self, citations: List[Dict]) -> str:
        """Format citations for display"""
        
        if not citations:
            return "출처 없음"
        
        display_lines = ["참고 문헌:"]
        
        for idx, citation in enumerate(citations, 1):
            line = f"[{idx}] {citation.get('doc_id', 'unknown')}"
            
            page = citation.get("page", 0)
            if page:
                line += f", {page}페이지"
            
            start = citation.get("start_char", -1)
            end = citation.get("end_char", -1)
            if start >= 0 and end >= 0:
                line += f" ({start}-{end})"
            
            display_lines.append(line)

        return "\n".join(display_lines)

    def _add_inline_citations_with_map_tracking(self, answer: str, evidences: List[Dict]) -> Tuple[str, Dict[str, int]]:
        """Add inline citations and track the mapping used

        CRITICAL FIX: Parse existing [1], [2] citations from LLM response FIRST,
        then match them to evidences to build cited_evidences map.

        Previous bug: Method tried to add NEW citations based on content similarity,
        but ignored citations that LLM already generated, resulting in incomplete
        cited_evidences map and missing sources.
        """
        cited_evidences = {}

        # STEP 1: Extract ALL citation numbers that LLM already used in the answer
        # This finds [1], [2], etc. anywhere in the text
        citation_pattern = re.compile(r'\[(\d+)\]')
        all_cited_numbers = set()
        for match in citation_pattern.finditer(answer):
            cite_num = int(match.group(1))
            all_cited_numbers.add(cite_num)

        logger.info(f"🔍 Found {len(all_cited_numbers)} citation numbers in LLM response: {sorted(all_cited_numbers)}")

        # STEP 2: Match each citation number to its corresponding evidence
        # Build the cited_evidences map by matching content to evidences
        for cite_num in sorted(all_cited_numbers):
            # Extract text segments that have this citation number
            # Find the context around each [cite_num] to match to evidence
            segments = []
            lines = answer.split('\n')
            for line in lines:
                if f'[{cite_num}]' in line:
                    # Extract meaningful content (remove citation markers for matching)
                    clean_line = re.sub(r'\[(\d+)\]', '', line).strip()
                    if clean_line:
                        segments.append(clean_line)

            if not segments:
                continue

            # Find best matching evidence for this citation number
            best_evidence = None
            best_score = 0.0

            for evidence in evidences:
                evidence_text = evidence.get("text", "")

                # Calculate similarity with all segments that use this citation
                total_score = 0.0
                for segment in segments:
                    score = self._calculate_content_similarity(segment, evidence_text)
                    total_score += score

                avg_score = total_score / len(segments) if segments else 0.0

                if avg_score > best_score:
                    best_score = avg_score
                    best_evidence = evidence

            # Assign this evidence to this citation number
            if best_evidence and best_score > 0.2:  # Lower threshold for existing citations
                evidence_key = f"{best_evidence.get('doc_id', '')}_{best_evidence.get('page', 0)}_{best_evidence.get('chunk_id', '')}"
                cited_evidences[evidence_key] = cite_num
                logger.info(f"  ✅ Citation [{cite_num}] matched to {best_evidence.get('doc_id')} (score: {best_score:.2f})")
            else:
                logger.warning(f"  ⚠️ Citation [{cite_num}] could not be matched to any evidence (best score: {best_score:.2f})")

        logger.info(f"📋 Built citation map with {len(cited_evidences)} evidences")

        # STEP 3: Return answer as-is (LLM already added citations correctly)
        # and return the cited_evidences map
        return answer, cited_evidences

    def _add_inline_citations_with_fixed_map(self, answer: str, evidences: List[Dict], fixed_map: Dict[str, int]) -> str:
        """Add inline citations using fixed citation mapping"""
        lines = answer.split('\n')
        fixed_lines = []

        for line in lines:
            # Check for numbered list with citation
            if re.match(r'^\d+\.\[', line):
                fixed_line = self._fix_line_citation_with_fixed_map(line, evidences, fixed_map)
                fixed_lines.append(fixed_line)
            else:
                # For non-numbered lines, add citations based on content matching
                fixed_line = self._add_citations_to_line_with_fixed_map(line, evidences, fixed_map)
                fixed_lines.append(fixed_line)

        return '\n'.join(fixed_lines)

    def _fix_line_citation_with_fixed_map(self, line: str, evidences: List[Dict], fixed_map: Dict[str, int]) -> str:
        """Fix citation number in a numbered line using fixed mapping"""
        # Extract item number and content
        match = re.match(r'^(\d+)\.\[(\d+)\]\s*(.*)', line)
        if not match:
            return line

        item_num = match.group(1)
        content = match.group(3)

        # Find the best matching evidence for this content
        best_match_evidence = None
        best_score = 0

        for evidence in evidences:
            evidence_text = evidence.get("text", "")
            score = self._calculate_content_similarity(content, evidence_text)

            if score > best_score:
                best_score = score
                best_match_evidence = evidence

        # If we found a good match, use fixed citation number
        if best_match_evidence and best_score > 0.3:
            # Create unique key for this evidence
            evidence_key = f"{best_match_evidence.get('doc_id', '')}_{best_match_evidence.get('page', 0)}_{best_match_evidence.get('chunk_id', '')}"

            # Get fixed citation number
            if evidence_key in fixed_map:
                cite_num = fixed_map[evidence_key]
                return f"{item_num}.[{cite_num}] {content}"

        # Keep original if no match in fixed map
        return line

    def _add_citations_to_line_with_fixed_map(self, line: str, evidences: List[Dict], fixed_map: Dict[str, int]) -> str:
        """Add citations to a line using fixed mapping"""
        if not line.strip():
            return line

        # Check which evidence this line matches
        best_match_evidence = None
        best_score = 0

        for evidence in evidences:
            evidence_text = evidence.get("text", "")
            score = self._calculate_content_similarity(line, evidence_text)

            if score > best_score:
                best_score = score
                best_match_evidence = evidence

        # Add citation if good match found and not already present
        if best_match_evidence and best_score > 0.3 and not re.search(r'\[\d+\]', line):
            # Create unique key for this evidence
            evidence_key = f"{best_match_evidence.get('doc_id', '')}_{best_match_evidence.get('page', 0)}_{best_match_evidence.get('chunk_id', '')}"

            # Get fixed citation number
            if evidence_key in fixed_map:
                cite_num = fixed_map[evidence_key]
                return f"{line}[{cite_num}]"

        return line

    def _format_sources_with_fixed_map(self, sources: List[Dict], evidences: List[Dict], fixed_map: Dict[str, int]) -> List[Dict]:
        """Format sources using fixed citation mapping"""
        formatted = []

        # Create reverse map (citation_number -> evidence_key)
        reverse_map = {v: k for k, v in fixed_map.items()}

        # Keep original evidence order instead of sorting by citation number
        # This preserves the logical flow of information
        seen_citations = set()
        for evidence in evidences:
            evidence_key = f"{evidence.get('doc_id', '')}_{evidence.get('page', 0)}_{evidence.get('chunk_id', '')}"
            if evidence_key in fixed_map and fixed_map[evidence_key] not in seen_citations:
                cite_num = fixed_map[evidence_key]
                seen_citations.add(cite_num)

                # Clean text_snippet for fixed map sources too
                text_snippet = evidence.get("text", "")
                cleaned_snippet = self._clean_text_snippet(text_snippet)

                formatted.append({
                    "index": cite_num,
                    "display_index": cite_num,  # Add display_index for frontend
                    "doc_id": evidence.get("doc_id", "unknown"),
                    "page": evidence.get("page", 0),
                    "start_char": evidence.get("start_char", -1),
                    "end_char": evidence.get("end_char", -1),
                    "chunk_id": evidence.get("chunk_id", ""),
                    "text_snippet": cleaned_snippet  # Use cleaned version
                })

        return formatted

    def _format_sources_from_cited_map(self, evidences: List[Dict], cited_map: Dict[str, int]) -> List[Dict]:
        """Format sources from cited evidence map

        This ensures that ALL cited evidences become sources in the response.
        Addresses the bug where search_results had more items than response_sources.

        Args:
            evidences: List of all evidence documents
            cited_map: Dictionary mapping evidence_key to citation_number
                      e.g., {"구청장 지시사항(제116호)_2_directive-5": 1, ...}

        Returns:
            List of formatted source dictionaries with citation numbers
        """
        formatted = []

        # Process each evidence and check if it was cited
        for evidence in evidences:
            # Create the same key format used during citation tracking
            evidence_key = f"{evidence.get('doc_id', '')}_{evidence.get('page', 0)}_{evidence.get('chunk_id', '')}"

            # Only include this evidence if it was actually cited
            if evidence_key in cited_map:
                cite_num = cited_map[evidence_key]

                # Clean text_snippet: remove special characters and normalize
                text_snippet = evidence.get("text", "")
                cleaned_snippet = self._clean_text_snippet(text_snippet)

                formatted.append({
                    "index": cite_num,
                    "display_index": cite_num,
                    "doc_id": evidence.get("doc_id", "unknown"),
                    "page": evidence.get("page", 0),
                    "start_char": evidence.get("start_char", -1),
                    "end_char": evidence.get("end_char", -1),
                    "chunk_id": evidence.get("chunk_id", ""),
                    "text_snippet": cleaned_snippet,  # Use cleaned version
                    "original_index": evidences.index(evidence) + 1,  # Track original position
                    "is_cited": True  # Mark as cited
                })

        # Sort by citation number to maintain sequential order [1], [2], [3]...
        formatted.sort(key=lambda x: x["index"])

        logger.info(f"Formatted {len(formatted)} sources from {len(cited_map)} cited evidences (out of {len(evidences)} total)")

        return formatted

    def _clean_text_snippet(self, text: str) -> str:
        """Clean text snippet by removing special characters and normalizing

        Removes problematic characters like private use area Unicode (󰏅)
        and other non-printable or special characters that harm readability.
        """
        if not text:
            return ""

        # Remove private use area Unicode characters (U+E0000 to U+F8FF)
        # These include characters like 󰏅 that appear in PDF extractions
        cleaned = re.sub(r'[\uE000-\uF8FF]', '', text)

        # Remove other problematic Unicode categories
        # Cc: Control characters, Cf: Format characters
        import unicodedata
        cleaned = ''.join(
            char for char in cleaned
            if unicodedata.category(char) not in ('Cc', 'Cf', 'Cn')
            or char in ('\n', '\t', ' ')  # Keep whitespace
        )

        # Normalize multiple spaces
        cleaned = re.sub(r' {2,}', ' ', cleaned)

        # Normalize multiple newlines (max 2 consecutive)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

        return cleaned.strip()

    def _init_embedder(self):
        """Initialize sentence embedder for semantic similarity"""
        try:
            # Try Korean model first
            self.embedder = SentenceTransformer('nlpai-lab/KoE5')
            logger.info("Loaded Korean embedder: nlpai-lab/KoE5")
        except Exception as e:
            try:
                # Fallback to multilingual model
                self.embedder = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
                logger.info("Loaded multilingual embedder")
            except Exception as e2:
                logger.warning(f"Failed to load embedders: {e}, {e2}")
                self.embedder = None
    
    def validate_citation_accuracy(self, answer: str, evidences: List[Dict]) -> Dict:
        """Validate citation accuracy using multiple metrics"""
        validation_result = {
            "overall_score": 0.0,
            "jaccard_score": 0.0,
            "semantic_score": 0.0,
            "length_ratio": 0.0,
            "citation_coverage": 0.0,
            "is_valid": False,
            "details": []
        }
        
        if not evidences:
            return validation_result
        
        # Combine all evidence texts
        combined_evidence = " ".join([ev.get("text", "") for ev in evidences])
        
        # 1. Jaccard similarity
        jaccard_score = self._calculate_jaccard_similarity(answer, combined_evidence)
        validation_result["jaccard_score"] = jaccard_score
        
        # 2. Semantic similarity (if embedder available)
        semantic_score = 0.0
        if self.embedder:
            semantic_score = self._calculate_semantic_similarity(answer, combined_evidence)
        validation_result["semantic_score"] = semantic_score
        
        # 3. Length ratio check
        answer_length = len(answer.strip())
        evidence_length = len(combined_evidence.strip())
        length_ratio = min(answer_length / max(evidence_length, 1), 1.0)
        validation_result["length_ratio"] = length_ratio
        
        # 4. Citation coverage (how much of answer is covered by evidences)
        coverage = self._calculate_citation_coverage(answer, evidences)
        validation_result["citation_coverage"] = coverage
        
        # 5. Overall score calculation
        weights = {
            "jaccard": 0.3,
            "semantic": 0.3 if self.embedder else 0.0,
            "length": 0.2,
            "coverage": 0.2
        }
        
        # Adjust weights if no semantic model
        if not self.embedder:
            weights["jaccard"] = 0.4
            weights["length"] = 0.3
            weights["coverage"] = 0.3
        
        overall_score = (
            jaccard_score * weights["jaccard"] +
            semantic_score * weights["semantic"] +
            length_ratio * weights["length"] +
            coverage * weights["coverage"]
        )
        
        validation_result["overall_score"] = overall_score
        validation_result["is_valid"] = overall_score >= 0.7  # Threshold
        
        # Add detailed analysis
        validation_result["details"] = self._generate_validation_details(
            answer, evidences, validation_result
        )
        
        return validation_result
    
    def _calculate_jaccard_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity between two texts"""
        # Normalize texts
        norm_text1 = set(self._normalize_text(text1).split())
        norm_text2 = set(self._normalize_text(text2).split())
        
        if not norm_text1 or not norm_text2:
            return 0.0
        
        intersection = norm_text1.intersection(norm_text2)
        union = norm_text1.union(norm_text2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity using embeddings"""
        if not self.embedder:
            return 0.0
        
        try:
            embeddings = self.embedder.encode([text1, text2])
            similarity = np.dot(embeddings[0], embeddings[1]) / (
                np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
            )
            return float(similarity)
        except Exception as e:
            logger.warning(f"Semantic similarity calculation failed: {e}")
            return 0.0
    
    def _calculate_citation_coverage(self, answer: str, evidences: List[Dict]) -> float:
        """Calculate how much of the answer is covered by evidences"""
        answer_sentences = self._split_sentences(answer)
        covered_sentences = 0
        
        for sentence in answer_sentences:
            for evidence in evidences:
                evidence_text = evidence.get("text", "")
                if self._sentence_from_evidence(sentence, evidence_text):
                    covered_sentences += 1
                    break
        
        return covered_sentences / len(answer_sentences) if answer_sentences else 0.0
    
    def _generate_validation_details(self, answer: str, evidences: List[Dict], 
                                   validation_result: Dict) -> List[str]:
        """Generate detailed validation analysis"""
        details = []
        
        # Jaccard analysis
        jaccard = validation_result["jaccard_score"]
        if jaccard < 0.5:
            details.append(f"낮은 어휘 유사도 ({jaccard:.2f}): 답변이 원문과 다른 표현을 많이 사용")
        elif jaccard > 0.8:
            details.append(f"높은 어휘 유사도 ({jaccard:.2f}): 원문을 잘 반영")
        
        # Semantic analysis
        semantic = validation_result["semantic_score"]
        if semantic > 0 and semantic < 0.6:
            details.append(f"낮은 의미 유사도 ({semantic:.2f}): 의미적으로 원문과 차이")
        elif semantic > 0.8:
            details.append(f"높은 의미 유사도 ({semantic:.2f}): 의미가 원문과 일치")
        
        # Coverage analysis
        coverage = validation_result["citation_coverage"]
        if coverage < 0.7:
            details.append(f"낮은 인용 커버리지 ({coverage:.2f}): 근거 없는 내용 포함 가능성")
        elif coverage > 0.9:
            details.append(f"높은 인용 커버리지 ({coverage:.2f}): 대부분 근거에 기반")
        
        # Overall assessment
        overall = validation_result["overall_score"]
        if overall < 0.5:
            details.append("전체 평가: 부정확한 인용 - 재생성 권장")
        elif overall < 0.7:
            details.append("전체 평가: 보통 수준 - 검토 필요")
        else:
            details.append("전체 평가: 정확한 인용")
        
        return details
