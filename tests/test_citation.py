import pytest
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from backend.rag.citation_tracker import CitationTracker
from backend.rag.answer_formatter import AnswerFormatter

@pytest.fixture
def tracker():
    """Create citation tracker instance"""
    return CitationTracker()

@pytest.fixture
def formatter():
    """Create answer formatter instance"""
    return AnswerFormatter()

@pytest.fixture
def sample_response():
    """Create sample response"""
    return {
        "answer": "예산이 10% 증액되었습니다.",
        "key_facts": [
            "디지털 전환 예산 증액",
            "탄소중립 예산 신설"
        ],
        "details": "2024년도 예산 편성 지침에 따르면...",
        "sources": [
            {
                "doc_id": "budget_2024.hwp",
                "page": 3,
                "start": 150,
                "end": 280
            }
        ]
    }

@pytest.fixture
def sample_evidences():
    """Create sample evidences"""
    return [
        {
            "chunk_id": "chunk-1",
            "doc_id": "budget_2024.hwp",
            "page": 3,
            "text": "예산이 10% 증액되었습니다.",
            "start_char": 150,
            "end_char": 280
        }
    ]

def test_citation_tracking(tracker, sample_response, sample_evidences):
    """Test citation tracking"""
    result = tracker.track_citations(sample_response, sample_evidences)
    
    assert "sources" in result
    assert len(result["sources"]) > 0
    assert "citations_json" in result
    
    # Check if citations are properly formatted
    source = result["sources"][0]
    assert "doc_id" in source
    assert "page" in source
    assert source["doc_id"] == "budget_2024.hwp"

def test_inline_citations(tracker):
    """Test inline citation addition"""
    text = "예산이 증액되었습니다. 탄소중립이 추진됩니다."
    evidences = [
        {
            "chunk_id": "chunk-1",
            "doc_id": "doc1",
            "text": "예산이 증액되었습니다.",
            "page": 1
        },
        {
            "chunk_id": "chunk-2",
            "doc_id": "doc2",
            "text": "탄소중립이 추진됩니다.",
            "page": 2
        }
    ]
    
    result = tracker._add_inline_citations(text, evidences)
    
    # Should have citation markers
    assert "[" in result and "]" in result

def test_citation_map_building(tracker, sample_evidences):
    """Test citation map building"""
    citation_map = tracker._build_citation_map(sample_evidences)
    
    assert len(citation_map) == len(sample_evidences)
    
    key = f"{sample_evidences[0]['doc_id']}_{sample_evidences[0]['page']}"
    assert key in citation_map
    assert citation_map[key]["index"] == 1

def test_answer_formatting_text(formatter, sample_response):
    """Test text format output"""
    formatted = formatter._format_as_text(sample_response)
    
    assert "핵심 답변" in formatted
    assert "예산이 10% 증액되었습니다" in formatted
    assert "디지털 전환" in formatted
    assert "budget_2024.hwp" in formatted

def test_answer_formatting_html(formatter, sample_response):
    """Test HTML format output"""
    formatted = formatter._format_as_html(sample_response)
    
    assert "<div" in formatted
    assert "class=" in formatted
    assert sample_response["answer"] in formatted
    
    # Check for proper HTML escaping
    response_with_html = sample_response.copy()
    response_with_html["answer"] = "Test <script>alert('xss')</script>"
    
    formatted = formatter._format_as_html(response_with_html)
    assert "<script>" not in formatted
    assert "&lt;script&gt;" in formatted

def test_answer_formatting_markdown(formatter, sample_response):
    """Test Markdown format output"""
    formatted = formatter._format_as_markdown(sample_response)
    
    assert "###" in formatted  # Headers
    assert "- " in formatted  # List items
    assert "`budget_2024.hwp`" in formatted  # Code formatting

def test_answer_formatting_json(formatter, sample_response):
    """Test JSON format output"""
    import json
    
    formatted = formatter._format_as_json(sample_response)
    
    # Should be valid JSON
    parsed = json.loads(formatted)
    assert parsed["answer"] == sample_response["answer"]
    assert len(parsed["key_facts"]) == len(sample_response["key_facts"])

def test_error_response_formatting(formatter):
    """Test error response formatting"""
    error_response = formatter.format_error_response(
        "Test error",
        "Test query"
    )
    
    assert error_response["error"] == True
    assert "Test error" in error_response["error_message"]
    assert "Test query" in error_response["original_query"]
    assert len(error_response["key_facts"]) > 0

def test_citation_display_formatting(tracker):
    """Test citation display formatting"""
    citations = [
        {
            "doc_id": "doc1.pdf",
            "page": 5,
            "start_char": 100,
            "end_char": 200
        },
        {
            "doc_id": "doc2.hwp",
            "page": 10,
            "start_char": 500,
            "end_char": 600
        }
    ]
    
    formatted = tracker.format_citation_display(citations)
    
    assert "참고 문헌:" in formatted
    assert "[1]" in formatted
    assert "[2]" in formatted
    assert "doc1.pdf" in formatted
    assert "5페이지" in formatted

def test_fuzzy_matching(tracker):
    """Test fuzzy text matching"""
    text1 = "예산이 증액되었습니다"
    text2 = "예산이 증액 되었습니다"  # Extra space
    
    assert tracker._fuzzy_match(text1, text2, threshold=0.9)
    
    text3 = "완전히 다른 텍스트입니다"
    assert not tracker._fuzzy_match(text1, text3, threshold=0.8)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])