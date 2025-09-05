import re
from typing import List, Dict, Tuple
import numpy as np
from collections import Counter
import logging

logger = logging.getLogger(__name__)

class Metrics:
    """Evaluation metrics for RAG system"""
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for evaluation"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove punctuation
        text = re.sub(r'[^\w\s가-힣]', '', text)
        
        # Lowercase
        text = text.lower().strip()
        
        return text
    
    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tokenize text into words"""
        # Simple whitespace tokenization
        return text.split()
    
    @classmethod
    def exact_match(cls, prediction: str, reference: str) -> float:
        """Calculate exact match score"""
        pred_norm = cls.normalize_text(prediction)
        ref_norm = cls.normalize_text(reference)
        
        return 1.0 if pred_norm == ref_norm else 0.0
    
    @classmethod
    def f1_score(cls, prediction: str, reference: str) -> float:
        """Calculate F1 score"""
        pred_tokens = cls.tokenize(cls.normalize_text(prediction))
        ref_tokens = cls.tokenize(cls.normalize_text(reference))
        
        if not pred_tokens and not ref_tokens:
            return 1.0
        
        if not pred_tokens or not ref_tokens:
            return 0.0
        
        common = Counter(pred_tokens) & Counter(ref_tokens)
        num_same = sum(common.values())
        
        if num_same == 0:
            return 0.0
        
        precision = num_same / len(pred_tokens)
        recall = num_same / len(ref_tokens)
        
        f1 = 2 * precision * recall / (precision + recall)
        
        return f1
    
    @staticmethod
    def citation_iou(pred_citations: List[Dict], ref_citations: List[Dict]) -> float:
        """Calculate IoU for citation spans"""
        if not pred_citations and not ref_citations:
            return 1.0
        
        if not pred_citations or not ref_citations:
            return 0.0
        
        ious = []
        
        for pred in pred_citations:
            best_iou = 0.0
            
            for ref in ref_citations:
                # Check if same document
                if pred.get("doc_id") != ref.get("doc_id"):
                    continue
                
                # Calculate span IoU
                pred_start = pred.get("start", 0)
                pred_end = pred.get("end", 0)
                ref_start = ref.get("start", 0)
                ref_end = ref.get("end", 0)
                
                # Calculate intersection
                inter_start = max(pred_start, ref_start)
                inter_end = min(pred_end, ref_end)
                
                if inter_end > inter_start:
                    intersection = inter_end - inter_start
                    union = max(pred_end, ref_end) - min(pred_start, ref_start)
                    
                    if union > 0:
                        iou = intersection / union
                        best_iou = max(best_iou, iou)
            
            ious.append(best_iou)
        
        return sum(ious) / len(ious) if ious else 0.0
    
    @staticmethod
    def sentence_similarity(sent1: str, sent2: str) -> float:
        """Calculate sentence similarity using character n-grams"""
        if not sent1 or not sent2:
            return 0.0
        
        # Create character trigrams
        def get_trigrams(text: str) -> set:
            text = text.lower()
            return set([text[i:i+3] for i in range(len(text) - 2)])
        
        trigrams1 = get_trigrams(sent1)
        trigrams2 = get_trigrams(sent2)
        
        if not trigrams1 or not trigrams2:
            return 0.0
        
        intersection = len(trigrams1 & trigrams2)
        union = len(trigrams1 | trigrams2)
        
        return intersection / union if union > 0 else 0.0
    
    @classmethod
    def evaluate_answer(cls, 
                       prediction: Dict,
                       reference: Dict) -> Dict:
        """Evaluate a single answer"""
        
        results = {}
        
        # Extract answer texts
        pred_answer = prediction.get("answer", "")
        ref_answer = reference.get("answer", "")
        
        # Calculate EM and F1
        results["exact_match"] = cls.exact_match(pred_answer, ref_answer)
        results["f1_score"] = cls.f1_score(pred_answer, ref_answer)
        
        # Evaluate key facts if available
        pred_facts = prediction.get("key_facts", [])
        ref_facts = reference.get("key_facts", [])
        
        if ref_facts:
            fact_f1_scores = []
            for ref_fact in ref_facts:
                best_f1 = 0.0
                for pred_fact in pred_facts:
                    f1 = cls.f1_score(pred_fact, ref_fact)
                    best_f1 = max(best_f1, f1)
                fact_f1_scores.append(best_f1)
            
            results["facts_f1"] = sum(fact_f1_scores) / len(fact_f1_scores)
        else:
            results["facts_f1"] = 0.0
        
        # Evaluate citations
        pred_citations = prediction.get("sources", [])
        ref_citations = reference.get("evidence_spans", [])
        
        results["citation_accuracy"] = cls.citation_iou(pred_citations, ref_citations)
        
        # Detect hallucination
        results["hallucination_detected"] = (
            prediction.get("verification", {}).get("hallucination_detected", False)
        )
        
        return results
    
    @classmethod
    def aggregate_metrics(cls, results: List[Dict]) -> Dict:
        """Aggregate metrics across multiple evaluations"""
        
        if not results:
            return {
                "average_exact_match": 0.0,
                "average_f1": 0.0,
                "average_facts_f1": 0.0,
                "average_citation_accuracy": 0.0,
                "hallucination_rate": 0.0,
                "total_questions": 0
            }
        
        metrics = {
            "average_exact_match": sum(r["exact_match"] for r in results) / len(results),
            "average_f1": sum(r["f1_score"] for r in results) / len(results),
            "average_facts_f1": sum(r.get("facts_f1", 0) for r in results) / len(results),
            "average_citation_accuracy": sum(r.get("citation_accuracy", 0) for r in results) / len(results),
            "hallucination_rate": sum(1 for r in results if r.get("hallucination_detected", False)) / len(results),
            "total_questions": len(results)
        }
        
        # Check pass/fail
        metrics["passed"] = (
            metrics["average_exact_match"] >= 0.95 and
            metrics["average_f1"] >= 0.99 and
            metrics["average_citation_accuracy"] >= 0.995 and
            metrics["hallucination_rate"] == 0.0
        )
        
        return metrics