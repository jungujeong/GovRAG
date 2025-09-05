import re
from typing import Dict, List, Tuple, Optional
import json
import logging

logger = logging.getLogger(__name__)

class CitationTracker:
    """Track and format citations with coordinates"""
    
    def __init__(self):
        self.citations = []
        self.citation_map = {}
    
    def track_citations(self, 
                       response: Dict,
                       evidences: List[Dict]) -> Dict:
        """Add citation tracking to response"""
        
        # Extract citations from response
        answer = response.get("answer", "")
        sources = response.get("sources", [])
        
        # Create citation map from evidences
        self.citation_map = self._build_citation_map(evidences)
        
        # Add inline citations to answer
        answer_with_citations = self._add_inline_citations(answer, evidences)
        response["answer"] = answer_with_citations
        
        # Format source list
        formatted_sources = self._format_sources(sources, evidences)
        response["sources"] = formatted_sources
        
        # Add citation JSON
        response["citations_json"] = json.dumps(
            formatted_sources,
            ensure_ascii=False,
            indent=2
        )
        
        return response
    
    def _build_citation_map(self, evidences: List[Dict]) -> Dict:
        """Build map of evidence to citation format"""
        citation_map = {}
        
        for idx, evidence in enumerate(evidences, 1):
            key = f"{evidence.get('doc_id', '')}_{evidence.get('page', 0)}"
            citation_map[key] = {
                "index": idx,
                "doc_id": evidence.get("doc_id", "unknown"),
                "page": evidence.get("page", 0),
                "start_char": evidence.get("start_char", 0),
                "end_char": evidence.get("end_char", 0),
                "chunk_id": evidence.get("chunk_id", "")
            }
        
        return citation_map
    
    def _add_inline_citations(self, text: str, evidences: List[Dict]) -> str:
        """Add inline citation markers to text"""
        
        # Find sentences that match evidence
        sentences = self._split_sentences(text)
        cited_sentences = []
        
        for sentence in sentences:
            citation_added = False
            
            for idx, evidence in enumerate(evidences, 1):
                evidence_text = evidence.get("text", "")
                
                # Check if sentence is from this evidence
                if self._sentence_from_evidence(sentence, evidence_text):
                    # Add citation
                    cited_sentence = f"{sentence}[{idx}]"
                    cited_sentences.append(cited_sentence)
                    citation_added = True
                    break
            
            if not citation_added:
                cited_sentences.append(sentence)
        
        # Reconstruct text
        return " ".join(cited_sentences)
    
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
                    "start_char": evidence.get("start_char", 0),
                    "end_char": evidence.get("end_char", 0),
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
                        "start_char": matching_evidence.get("start_char", 0),
                        "end_char": matching_evidence.get("end_char", 0),
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
            
            start = citation.get("start_char", 0)
            end = citation.get("end_char", 0)
            if start and end:
                line += f" ({start}-{end})"
            
            display_lines.append(line)
        
        return "\n".join(display_lines)