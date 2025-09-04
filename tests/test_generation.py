import pytest
import asyncio
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from backend.rag.generator_ollama import OllamaGenerator
from backend.rag.evidence_enforcer import EvidenceEnforcer
from backend.rag.prompt_templates import PromptTemplates

@pytest.fixture
def generator():
    """Create generator instance"""
    return OllamaGenerator()

@pytest.fixture
def enforcer():
    """Create enforcer instance"""
    return EvidenceEnforcer()

@pytest.fixture
def sample_evidences():
    """Create sample evidences"""
    return [
        {
            "chunk_id": "chunk-1",
            "doc_id": "budget_2024.hwp",
            "page": 3,
            "text": "2024년도 예산 편성 지침의 주요 변경사항은 디지털 전환 예산 10% 증액입니다.",
            "start_char": 150,
            "end_char": 280
        },
        {
            "chunk_id": "chunk-2",
            "doc_id": "budget_2024.hwp",
            "page": 5,
            "text": "탄소중립 관련 예산이 신설되어 500억원이 배정되었습니다.",
            "start_char": 500,
            "end_char": 600
        }
    ]

def test_prompt_formatting():
    """Test prompt template formatting"""
    query = "2024년 예산 변경사항은?"
    evidences = [
        {
            "doc_id": "doc1",
            "page": 1,
            "text": "예산이 증액되었습니다."
        }
    ]
    
    formatted = PromptTemplates.format_user_prompt(query, evidences)
    
    assert query in formatted
    assert "doc1" in formatted
    assert "예산이 증액되었습니다" in formatted

@pytest.mark.asyncio
async def test_generator_health_check(generator):
    """Test Ollama health check"""
    # This may fail if Ollama is not running
    try:
        is_healthy = await generator.check_health()
        assert isinstance(is_healthy, bool)
    except:
        pytest.skip("Ollama not available")

def test_response_parsing(generator):
    """Test response parsing"""
    sample_response = """
핵심 답변: 2024년 예산이 증액되었습니다.

주요 사실:
- 디지털 전환 예산 10% 증액
- 탄소중립 예산 신설
- 지방교부세 상향

상세 설명: 정부는 2024년도 예산 편성에서...

출처:
(budget_2024.hwp, p.3, 150-280)
"""
    
    parsed = generator._parse_response(sample_response)
    
    assert "2024년 예산이 증액되었습니다" in parsed["answer"]
    assert len(parsed["key_facts"]) >= 2
    assert "디지털 전환" in " ".join(parsed["key_facts"])
    assert len(parsed["sources"]) > 0

def test_evidence_verification(enforcer, sample_evidences):
    """Test evidence verification"""
    # Good response (grounded in evidence)
    good_response = {
        "answer": "디지털 전환 예산이 10% 증액되고 탄소중립 예산이 신설되었습니다.",
        "key_facts": [
            "디지털 전환 예산 10% 증액",
            "탄소중립 예산 500억원 배정"
        ],
        "sources": [
            {"doc_id": "budget_2024.hwp", "page": 3, "start": 150, "end": 280}
        ]
    }
    
    is_valid, verification = enforcer.verify_response(good_response, sample_evidences)
    
    assert verification["jaccard_score"] > 0.3
    assert verification["fact_grounding"] > 0.5
    assert not verification["hallucination_detected"]

def test_hallucination_detection(enforcer, sample_evidences):
    """Test hallucination detection"""
    # Bad response (contains hallucination)
    bad_response = {
        "answer": "예산이 50% 삭감되고 모든 사업이 중단됩니다.",  # Not in evidence
        "key_facts": [
            "예산 50% 삭감",  # Hallucinated
            "사업 중단"  # Hallucinated
        ],
        "sources": []
    }
    
    is_valid, verification = enforcer.verify_response(bad_response, sample_evidences)
    
    assert verification["jaccard_score"] < 0.3
    assert verification["fact_grounding"] < 0.5
    assert verification["hallucination_detected"]
    assert not is_valid

def test_citation_verification(enforcer):
    """Test citation accuracy verification"""
    evidences = [
        {"doc_id": "doc1", "page": 1, "start_char": 0, "end_char": 100},
        {"doc_id": "doc2", "page": 5, "start_char": 500, "end_char": 600}
    ]
    
    citations = [
        {"doc_id": "doc1", "page": 1, "start": 0, "end": 100},  # Correct
        {"doc_id": "doc2", "page": 5, "start": 500, "end": 600}  # Correct
    ]
    
    accuracy = enforcer._verify_citations(citations, evidences)
    assert accuracy == 1.0
    
    # Test with wrong citations
    wrong_citations = [
        {"doc_id": "doc3", "page": 10, "start": 1000, "end": 1100}
    ]
    
    accuracy = enforcer._verify_citations(wrong_citations, evidences)
    assert accuracy == 0.0

def test_jaccard_similarity(enforcer):
    """Test Jaccard similarity calculation"""
    text1 = "디지털 전환 예산이 증액되었습니다"
    text2 = "디지털 전환 예산이 10% 증액되었습니다"
    
    similarity = enforcer._jaccard_similarity(text1, text2)
    
    assert 0.5 < similarity < 1.0  # Should be similar but not identical

def test_sentence_coverage(enforcer):
    """Test sentence coverage calculation"""
    response = "예산이 증액되었습니다. 탄소중립이 추진됩니다."
    evidence = "2024년 예산이 증액되었습니다. 정부는 탄소중립을 추진합니다."
    
    coverage = enforcer._sentence_coverage(response, evidence)
    
    assert coverage > 0.5  # Most sentences should be covered

if __name__ == "__main__":
    pytest.main([__file__, "-v"])