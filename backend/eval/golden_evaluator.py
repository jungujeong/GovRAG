import json
from pathlib import Path
from typing import List, Dict, Optional
import asyncio
import logging
from datetime import datetime

from eval.metrics import Metrics
from routers.query import process_query
from schemas import QueryRequest

logger = logging.getLogger(__name__)

class GoldenEvaluator:
    """Evaluate system against golden QA dataset"""
    
    def __init__(self):
        self.golden_path = Path("data/golden/qa_100.json")
        self.metrics = Metrics()
        self.results = []
    
    def load_golden_data(self) -> Dict:
        """Load golden QA dataset"""
        if not self.golden_path.exists():
            logger.error(f"Golden dataset not found: {self.golden_path}")
            return {"questions": []}
        
        with open(self.golden_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    async def evaluate_question(self, question: Dict) -> Dict:
        """Evaluate a single question"""
        try:
            # Create query request
            request = QueryRequest(
                query=question["question"],
                limit=10
            )
            
            # Get system response
            response = await process_query(request)
            
            # Convert response to evaluation format
            prediction = {
                "answer": response.answer,
                "key_facts": response.key_facts,
                "sources": [s.dict() for s in response.sources] if response.sources else []
            }
            
            # Evaluate
            eval_result = self.metrics.evaluate_answer(prediction, question)
            
            # Add metadata
            eval_result["question_id"] = question["id"]
            eval_result["question"] = question["question"]
            eval_result["expected_answer"] = question["answer"]
            eval_result["generated_answer"] = response.answer
            
            return eval_result
            
        except Exception as e:
            logger.error(f"Failed to evaluate question {question.get('id', 'unknown')}: {e}")
            
            return {
                "question_id": question.get("id", "unknown"),
                "question": question.get("question", ""),
                "expected_answer": question.get("answer", ""),
                "generated_answer": "",
                "exact_match": 0.0,
                "f1_score": 0.0,
                "citation_accuracy": 0.0,
                "hallucination_detected": True,
                "error": str(e)
            }
    
    async def evaluate_all(self, sample_size: Optional[int] = None) -> Dict:
        """Evaluate all golden questions"""
        
        # Load data
        golden_data = self.load_golden_data()
        questions = golden_data.get("questions", [])
        
        if sample_size and sample_size < len(questions):
            questions = questions[:sample_size]
        
        logger.info(f"Evaluating {len(questions)} questions...")
        
        # Evaluate questions
        self.results = []
        
        for i, question in enumerate(questions):
            logger.info(f"Evaluating question {i+1}/{len(questions)}: {question['id']}")
            
            result = await self.evaluate_question(question)
            self.results.append(result)
            
            # Log progress
            if (i + 1) % 10 == 0:
                current_metrics = self.metrics.aggregate_metrics(self.results)
                logger.info(f"Progress: EM={current_metrics['average_exact_match']:.3f}, "
                          f"F1={current_metrics['average_f1']:.3f}")
        
        # Aggregate metrics
        summary = self.metrics.aggregate_metrics(self.results)
        
        # Add timestamp
        summary["timestamp"] = datetime.now().isoformat()
        summary["details"] = self.results
        
        # Save results
        self._save_results(summary)
        
        # Generate report
        self._generate_report(summary)
        
        return summary
    
    def _save_results(self, results: Dict):
        """Save evaluation results"""
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        # Save JSON results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_path = reports_dir / f"evaluation_{timestamp}.json"
        
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved evaluation results to {result_path}")
    
    def _generate_report(self, summary: Dict):
        """Generate HTML evaluation report"""
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        html_path = reports_dir / "accuracy_dashboard.html"
        
        # Generate HTML
        html_content = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>RAG System Evaluation Dashboard</title>
    <style>
        body {{ font-family: 'Malgun Gothic', sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f0f0f0; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .metric {{ display: inline-block; margin: 10px 20px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; }}
        .metric-label {{ color: #666; }}
        .pass {{ color: green; }}
        .fail {{ color: red; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 10px; border: 1px solid #ddd; text-align: left; }}
        th {{ background: #f0f0f0; }}
        .good {{ background: #d4edda; }}
        .bad {{ background: #f8d7da; }}
    </style>
</head>
<body>
    <h1>📊 RAG System Evaluation Dashboard</h1>
    
    <div class="summary">
        <h2>Overall Performance {'✅ PASSED' if summary.get('passed') else '❌ FAILED'}</h2>
        
        <div class="metric">
            <div class="metric-value {('pass' if summary['average_exact_match'] >= 0.95 else 'fail')}">
                {summary['average_exact_match']:.1%}
            </div>
            <div class="metric-label">Exact Match</div>
        </div>
        
        <div class="metric">
            <div class="metric-value {('pass' if summary['average_f1'] >= 0.99 else 'fail')}">
                {summary['average_f1']:.1%}
            </div>
            <div class="metric-label">F1 Score</div>
        </div>
        
        <div class="metric">
            <div class="metric-value {('pass' if summary['average_citation_accuracy'] >= 0.995 else 'fail')}">
                {summary['average_citation_accuracy']:.1%}
            </div>
            <div class="metric-label">Citation Accuracy</div>
        </div>
        
        <div class="metric">
            <div class="metric-value {('pass' if summary['hallucination_rate'] == 0 else 'fail')}">
                {summary['hallucination_rate']:.1%}
            </div>
            <div class="metric-label">Hallucination Rate</div>
        </div>
    </div>
    
    <h2>Detailed Results</h2>
    <p>Evaluated {summary['total_questions']} questions at {summary.get('timestamp', 'unknown')}</p>
    
    <table>
        <thead>
            <tr>
                <th>Question ID</th>
                <th>Question</th>
                <th>EM</th>
                <th>F1</th>
                <th>Citation</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
"""
        
        # Add rows for each question
        for detail in summary.get("details", [])[:20]:  # Show first 20
            row_class = "good" if detail["f1_score"] >= 0.9 else "bad"
            status = "✓" if detail["f1_score"] >= 0.9 else "✗"
            
            html_content += f"""
            <tr class="{row_class}">
                <td>{detail['question_id']}</td>
                <td>{detail['question'][:100]}...</td>
                <td>{detail['exact_match']:.2f}</td>
                <td>{detail['f1_score']:.2f}</td>
                <td>{detail.get('citation_accuracy', 0):.2f}</td>
                <td>{status}</td>
            </tr>
"""
        
        html_content += """
        </tbody>
    </table>
    
    <div style="margin-top: 40px; color: #666; font-size: 12px;">
        Generated by RAG Evaluation System
    </div>
</body>
</html>
"""
        
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        logger.info(f"Generated HTML report: {html_path}")

if __name__ == "__main__":
    # Run evaluation
    import sys
    sys.path.append(str(Path(__file__).parent.parent.parent))
    
    async def main():
        evaluator = GoldenEvaluator()
        results = await evaluator.evaluate_all(sample_size=10)
        
        print("\n=== Evaluation Results ===")
        print(f"Exact Match: {results['average_exact_match']:.3f}")
        print(f"F1 Score: {results['average_f1']:.3f}")
        print(f"Citation Accuracy: {results['average_citation_accuracy']:.3f}")
        print(f"Hallucination Rate: {results['hallucination_rate']:.3f}")
        print(f"PASSED: {results['passed']}")
    
    asyncio.run(main())