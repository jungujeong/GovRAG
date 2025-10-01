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
        """Add citation tracking to response"""

        # Extract citations from response
        answer = response.get("answer", "")
        sources = response.get("sources", [])

        # Filter sources if allowed_doc_ids is provided
        if allowed_doc_ids:
            # Debug log the structure
            logger.info(f"DEBUG: allowed_doc_ids = {allowed_doc_ids}")
            if evidences:
                logger.info(f"DEBUG: First evidence structure: {evidences[0].keys() if evidences[0] else 'empty'}")
                first_doc_id = evidences[0].get('doc_id', 'NO DOC_ID')
                logger.info(f"DEBUG: First evidence doc_id field: {first_doc_id}")
                logger.info(f"DEBUG: First evidence doc_id repr: {repr(first_doc_id)}")
                logger.info(f"DEBUG: First evidence metadata: {evidences[0].get('metadata', {})}")
                # Also debug the allowed doc IDs in detail
                for allowed_id in allowed_doc_ids:
                    logger.info(f"DEBUG: Allowed doc_id repr: {repr(allowed_id)}")

            # Filter evidences to only allowed documents
            # Check both doc_id field and metadata.doc_id
            filtered_evidences = []
            for e in evidences:
                doc_id = e.get("doc_id") or e.get("metadata", {}).get("doc_id")
                if doc_id:
                    # Strip and normalize doc_id for comparison (Unicode normalization)
                    doc_id = unicodedata.normalize('NFC', doc_id.strip())
                    # Check if doc_id matches any allowed doc (with flexible matching)
                    matched = False
                    for allowed_id in allowed_doc_ids:
                        allowed_id_normalized = unicodedata.normalize('NFC', allowed_id.strip())
                        logger.info(f"Comparing normalized: '{doc_id}' with '{allowed_id_normalized}'")
                        if doc_id == allowed_id_normalized:
                            matched = True
                            logger.info(f"Matched exact: {doc_id}")
                            break
                        # Also try removing .pdf extension
                        doc_id_no_pdf = doc_id.replace('.pdf', '')
                        allowed_no_pdf = allowed_id_normalized.replace('.pdf', '')
                        if doc_id_no_pdf == allowed_no_pdf:
                            matched = True
                            logger.info(f"Matched without .pdf: {doc_id}")
                            break

                    if matched:
                        filtered_evidences.append(e)
                        logger.info(f"✓ Keeping evidence with doc_id: {doc_id}")
                    else:
                        logger.warning(f"✗ Filtering out evidence with doc_id: '{doc_id}' - no match found")
                else:
                    # Keep evidences without doc_id
                    logger.debug(f"Keeping evidence without doc_id: {e.get('chunk_id', 'unknown')}")
                    filtered_evidences.append(e)

            # Filter sources similarly
            filtered_sources = []
            for s in sources:
                doc_id = s.get("doc_id") or s.get("metadata", {}).get("doc_id")
                if doc_id:
                    if doc_id in allowed_doc_ids:
                        filtered_sources.append(s)
                else:
                    # Keep sources without doc_id
                    filtered_sources.append(s)

            logger.info(f"Citation tracking: filtered {len(evidences)} to {len(filtered_evidences)} evidences based on allowed docs: {allowed_doc_ids}")
            evidences = filtered_evidences
            sources = filtered_sources

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

            # Format source list
            formatted_sources = self._format_sources(sources, evidences)
            logger.info(f"[track_citations] After _format_sources: {len(formatted_sources)} sources")
            if formatted_sources:
                logger.info(f"[track_citations] First formatted source keys: {formatted_sources[0].keys()}")
                logger.info(f"[track_citations] First formatted source: {formatted_sources[0]}")

            deduped_sources = self._dedupe_sources(formatted_sources)
            logger.info(f"[track_citations] After _dedupe_sources: {len(deduped_sources)} sources")
            if deduped_sources:
                logger.info(f"[track_citations] First deduped source keys: {deduped_sources[0].keys()}")
                logger.info(f"[track_citations] First deduped source: {deduped_sources[0]}")

            response["sources"] = deduped_sources

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

        logger.info(f"[_format_sources] Input - sources: {len(sources)}, evidences: {len(evidences)}")
        if sources:
            logger.info(f"[_format_sources] First source keys: {sources[0].keys() if sources else 'N/A'}")

        formatted = []

        # If sources are empty, create from evidences
        if not sources and evidences:
            logger.info("[_format_sources] Branch: Creating sources from evidences")
            for idx, evidence in enumerate(evidences, 1):
                formatted.append({
                    "index": idx,
                    "citation_number": idx,  # Add citation_number field
                    "doc_id": evidence.get("doc_id", "unknown"),
                    "page": evidence.get("page", 0),
                    "start_char": evidence.get("start_char", -1),
                    "end_char": evidence.get("end_char", -1),
                    "chunk_id": evidence.get("chunk_id", ""),
                    "text_snippet": evidence.get("text", ""),
                    "score": evidence.get("score", evidence.get("normalized_score", 0.0))  # Add score
                })
        else:
            logger.info("[_format_sources] Branch: Enhancing existing sources with evidence data")
            # Enhance existing sources with evidence data
            idx = 1
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
                        "index": idx,  # Add index
                        "citation_number": idx,  # Add citation_number
                        "doc_id": doc_id,
                        "page": page,
                        "start_char": matching_evidence.get("start_char", -1),
                        "end_char": matching_evidence.get("end_char", -1),
                        "chunk_id": matching_evidence.get("chunk_id", ""),
                        "text_snippet": matching_evidence.get("text", ""),
                        "score": matching_evidence.get("score", matching_evidence.get("normalized_score", 0.0))  # Add score
                    })
                    idx += 1
                else:
                    # No matching evidence, still add index
                    formatted.append({
                        "index": idx,
                        "citation_number": idx,
                        **source
                    })
                    idx += 1

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
        """Add inline citations and track the mapping used"""
        cited_evidences = {}

        # Process text to fix citations
        lines = answer.split('\n')
        fixed_lines = []
        next_citation_num = 1

        for line in lines:
            # Check if this line contains numbered items with citations
            if re.match(r'^\d+\.\[', line):
                # Extract the content and find matching evidence
                fixed_line = self._fix_line_citation_sequential(line, evidences, cited_evidences, next_citation_num)
                # Update next citation number if new citation was added
                if fixed_line != line:
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

        return '\n'.join(fixed_lines), cited_evidences

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

                formatted.append({
                    "index": cite_num,
                    "display_index": cite_num,  # Add display_index for frontend
                    "doc_id": evidence.get("doc_id", "unknown"),
                    "page": evidence.get("page", 0),
                    "start_char": evidence.get("start_char", -1),
                    "end_char": evidence.get("end_char", -1),
                    "chunk_id": evidence.get("chunk_id", ""),
                    "text_snippet": evidence.get("text", "")
                })

        return formatted
    
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
