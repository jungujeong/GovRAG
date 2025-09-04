import json
from typing import List, Dict, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class FailureAnalyzer:
    """Analyze evaluation failures and suggest improvements"""
    
    def __init__(self):
        self.failure_types = {
            "low_em": "Low exact match score",
            "low_f1": "Low F1 score", 
            "bad_citation": "Poor citation accuracy",
            "hallucination": "Hallucination detected",
            "no_answer": "No answer generated",
            "error": "System error"
        }
    
    def analyze_failures(self, results: List[Dict]) -> Dict:
        """Analyze failure patterns"""
        
        failures = []
        failure_counts = defaultdict(int)
        
        for result in results:
            failure_reasons = self._identify_failure_reasons(result)
            
            if failure_reasons:
                failures.append({
                    "question_id": result.get("question_id"),
                    "question": result.get("question"),
                    "reasons": failure_reasons,
                    "metrics": {
                        "exact_match": result.get("exact_match", 0),
                        "f1_score": result.get("f1_score", 0),
                        "citation_accuracy": result.get("citation_accuracy", 0)
                    }
                })
                
                for reason in failure_reasons:
                    failure_counts[reason] += 1
        
        # Generate improvement suggestions
        suggestions = self._generate_suggestions(failure_counts, failures)
        
        return {
            "total_failures": len(failures),
            "failure_rate": len(failures) / len(results) if results else 0,
            "failure_types": dict(failure_counts),
            "top_failures": failures[:10],
            "improvement_suggestions": suggestions
        }
    
    def _identify_failure_reasons(self, result: Dict) -> List[str]:
        """Identify reasons for failure"""
        reasons = []
        
        if result.get("error"):
            reasons.append("error")
            return reasons
        
        if not result.get("generated_answer"):
            reasons.append("no_answer")
        
        if result.get("exact_match", 0) < 0.95:
            reasons.append("low_em")
        
        if result.get("f1_score", 0) < 0.99:
            reasons.append("low_f1")
        
        if result.get("citation_accuracy", 0) < 0.995:
            reasons.append("bad_citation")
        
        if result.get("hallucination_detected", False):
            reasons.append("hallucination")
        
        return reasons
    
    def _generate_suggestions(self, 
                             failure_counts: Dict[str, int],
                             failures: List[Dict]) -> List[Dict]:
        """Generate improvement suggestions based on failures"""
        
        suggestions = []
        
        # Analyze most common failure types
        if failure_counts:
            most_common = max(failure_counts, key=failure_counts.get)
            
            if most_common == "low_em":
                suggestions.append({
                    "issue": "Low Exact Match Scores",
                    "root_cause": "Generated answers don't match expected format",
                    "suggestions": [
                        "Improve prompt templates to enforce exact output format",
                        "Add post-processing to normalize answer format",
                        "Fine-tune generation temperature (currently too high)"
                    ]
                })
            
            elif most_common == "low_f1":
                suggestions.append({
                    "issue": "Low F1 Scores",
                    "root_cause": "Answers missing key information",
                    "suggestions": [
                        "Increase number of retrieved evidence chunks",
                        "Improve reranking model weights",
                        "Enhance evidence coverage in prompt"
                    ]
                })
            
            elif most_common == "bad_citation":
                suggestions.append({
                    "issue": "Poor Citation Accuracy",
                    "root_cause": "Citations don't match source documents",
                    "suggestions": [
                        "Improve citation tracking in generation",
                        "Add explicit citation instructions to prompt",
                        "Verify chunk metadata integrity in index"
                    ]
                })
            
            elif most_common == "hallucination":
                suggestions.append({
                    "issue": "Hallucination Detected",
                    "root_cause": "Model generating information not in evidence",
                    "suggestions": [
                        "Strengthen evidence-only enforcement in prompt",
                        "Lower generation temperature to 0.0",
                        "Add stricter post-generation validation",
                        "Consider using a different base model"
                    ]
                })
            
            elif most_common == "no_answer":
                suggestions.append({
                    "issue": "No Answers Generated",
                    "root_cause": "System failing to produce responses",
                    "suggestions": [
                        "Check Ollama service availability",
                        "Increase generation timeout",
                        "Verify retrieval returning valid evidences"
                    ]
                })
            
            elif most_common == "error":
                suggestions.append({
                    "issue": "System Errors",
                    "root_cause": "Technical failures in pipeline",
                    "suggestions": [
                        "Check system logs for error details",
                        "Verify all services are running",
                        "Increase memory allocation",
                        "Add better error handling and retries"
                    ]
                })
        
        # Additional general suggestions
        suggestions.append({
            "issue": "General Performance",
            "root_cause": "Overall system optimization needed",
            "suggestions": [
                f"Current failure rate: {len(failures)}/{len(failures) + len([r for r in failures if not self._identify_failure_reasons(r)])}",
                "Consider batch evaluation for better resource usage",
                "Implement caching for repeated queries",
                "Profile and optimize slowest components"
            ]
        })
        
        return suggestions
    
    def generate_failure_report(self, evaluation_results: Dict) -> Dict:
        """Generate comprehensive failure report"""
        
        details = evaluation_results.get("details", [])
        
        # Analyze failures
        analysis = self.analyze_failures(details)
        
        # Create report
        report = {
            "summary": {
                "total_evaluated": len(details),
                "total_passed": sum(1 for d in details if not self._identify_failure_reasons(d)),
                "total_failed": analysis["total_failures"],
                "failure_rate": analysis["failure_rate"],
                "meets_requirements": evaluation_results.get("passed", False)
            },
            "failure_breakdown": analysis["failure_types"],
            "top_failures": analysis["top_failures"],
            "improvement_plan": analysis["improvement_suggestions"],
            "recommended_actions": self._prioritize_actions(analysis)
        }
        
        return report
    
    def _prioritize_actions(self, analysis: Dict) -> List[str]:
        """Prioritize improvement actions"""
        
        actions = []
        
        # Priority 1: Critical failures
        if analysis["failure_types"].get("error", 0) > 0:
            actions.append("1. Fix system errors immediately")
        
        if analysis["failure_types"].get("hallucination", 0) > 0:
            actions.append("2. Address hallucination issues with stricter prompts")
        
        # Priority 2: Accuracy issues
        if analysis["failure_types"].get("low_f1", 0) > 5:
            actions.append("3. Improve retrieval and reranking")
        
        if analysis["failure_types"].get("bad_citation", 0) > 3:
            actions.append("4. Fix citation tracking")
        
        # Priority 3: Optimization
        if analysis["failure_rate"] > 0.1:
            actions.append("5. Consider switching to a better base model")
        
        return actions if actions else ["System performing well - minor optimizations only"]
    
    def save_report(self, report: Dict, path: str = "reports/failure_report.json"):
        """Save failure report to file"""
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved failure report to {path}")