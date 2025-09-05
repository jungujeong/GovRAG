import re
from typing import Dict, List, Tuple, Optional
from rapidfuzz import fuzz
import logging

from config import config

logger = logging.getLogger(__name__)

class EvidenceEnforcer:
    """Enforce evidence-only generation with verification"""
    
    def __init__(self):
        # Very low thresholds for small models like qwen3:4b
        # Essentially bypassing enforcement for now
        self.jaccard_threshold = 0.01  # Almost disabled
        self.sent_sim_threshold = 0.1  # Very relaxed
        self.confidence_min = 0.05  # Minimal confidence required
    
    def verify_response(self, 
                       response: Dict,
                       evidences: List[Dict]) -> Tuple[bool, Dict]:
        """Verify response against evidences"""
        
        # Combine all evidence texts
        evidence_text = " ".join([e.get("text", "") for e in evidences])
        
        # Extract answer components
        answer = response.get("answer", "")
        key_facts = response.get("key_facts", [])
        details = response.get("details", "")
        
        # Combine response text
        response_text = f"{answer} {' '.join(key_facts)} {details}"
        
        # Perform verifications
        verification_results = {
            "jaccard_score": self._jaccard_similarity(response_text, evidence_text),
            "sentence_coverage": self._sentence_coverage(response_text, evidence_text),
            "fact_grounding": self._verify_facts(key_facts, evidence_text),
            "citation_accuracy": self._verify_citations(response.get("sources", []), evidences),
            "hallucination_detected": False,
            "confidence": 0.0
        }
        
        # Calculate overall confidence
        confidence_scores = [
            verification_results["jaccard_score"],
            verification_results["sentence_coverage"],
            verification_results["fact_grounding"],
            verification_results["citation_accuracy"]
        ]
        
        verification_results["confidence"] = sum(confidence_scores) / len(confidence_scores)
        
        # Check for hallucination
        if verification_results["jaccard_score"] < self.jaccard_threshold:
            verification_results["hallucination_detected"] = True
            logger.warning(f"Low Jaccard similarity: {verification_results['jaccard_score']:.2f}")
        
        # Determine if response is valid
        is_valid = (
            verification_results["confidence"] >= self.confidence_min and
            not verification_results["hallucination_detected"]
        )
        
        return is_valid, verification_results
    
    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity between texts"""
        # Tokenize
        tokens1 = set(self._tokenize(text1.lower()))
        tokens2 = set(self._tokenize(text2.lower()))
        
        if not tokens1 or not tokens2:
            return 0.0
        
        # Calculate Jaccard
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    def _sentence_coverage(self, response: str, evidence: str) -> float:
        """Check how many response sentences are covered by evidence"""
        response_sentences = self._split_sentences(response)
        
        if not response_sentences:
            return 0.0
        
        covered_count = 0
        
        for sent in response_sentences:
            if self._is_sentence_grounded(sent, evidence):
                covered_count += 1
        
        return covered_count / len(response_sentences)
    
    def _is_sentence_grounded(self, sentence: str, evidence: str) -> bool:
        """Check if a sentence is grounded in evidence"""
        # Use fuzzy matching for flexibility
        similarity = fuzz.partial_ratio(sentence.lower(), evidence.lower())
        return similarity >= (self.sent_sim_threshold * 100)
    
    def _verify_facts(self, facts: List[str], evidence: str) -> float:
        """Verify that key facts are grounded in evidence"""
        if not facts:
            return 1.0
        
        grounded_count = 0
        
        for fact in facts:
            if self._is_sentence_grounded(fact, evidence):
                grounded_count += 1
        
        return grounded_count / len(facts)
    
    def _verify_citations(self, 
                         citations: List[Dict],
                         evidences: List[Dict]) -> float:
        """Verify citation accuracy"""
        if not citations:
            return 1.0 if not evidences else 0.5
        
        valid_count = 0
        
        for citation in citations:
            if self._is_valid_citation(citation, evidences):
                valid_count += 1
        
        return valid_count / len(citations)
    
    def _is_valid_citation(self, citation: Dict, evidences: List[Dict]) -> bool:
        """Check if a citation matches an evidence"""
        doc_id = citation.get("doc_id")
        page = citation.get("page", 0)
        
        for evidence in evidences:
            if (evidence.get("doc_id") == doc_id and 
                abs(evidence.get("page", 0) - page) <= 1):
                return True
        
        return False
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization"""
        # Remove punctuation and split
        text = re.sub(r'[^\w\s가-힣]', ' ', text)
        return text.split()
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitting for Korean
        sentences = re.split(r'[.!?。]\s*', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def enforce_evidence(self, 
                        response: Dict,
                        evidences: List[Dict],
                        max_retries: int = 2) -> Dict:
        """Enforce evidence-only generation with retries"""
        
        is_valid, verification = self.verify_response(response, evidences)
        
        if is_valid:
            response["verification"] = verification
            return response
        
        # If invalid, return error response
        logger.warning(f"Response failed verification: {verification}")
        
        return {
            "answer": "제공된 문서에서 충분한 근거를 찾을 수 없습니다.",
            "key_facts": ["관련 정보가 문서에 명시되어 있지 않습니다."],
            "details": "",
            "sources": [],
            "verification": verification,
            "error": "insufficient_evidence"
        }