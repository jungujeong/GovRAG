from typing import List, Dict

class PromptTemplates:
    """Evidence-Only generation prompt templates"""
    
    # 단순화된 시스템 프롬프트
    SYSTEM_PROMPT = """한국어로 답변하는 문서 검색 도우미입니다.
제공된 문서 내용을 바탕으로 답변합니다.
부서명이 있다면 포함하여 답변하세요.
문서명이나 파일명은 언급하지 마세요."""
    
    # 단순화된 프롬프트
    USER_PROMPT_TEMPLATE = """다음 문서 내용을 참고하여 질문에 답변하세요.

문서 내용:
{evidences}

질문: {query}

답변 시 부서명이 있다면 포함하되, 문서명이나 파일명은 언급하지 마세요.

답변:"""
    
    # 증거 형식에서 파일명 제거, 내용과 부서명만 포함
    EVIDENCE_FORMAT = """{text}"""
    
    OUTPUT_SCHEMA = {
        "answer": {
            "type": "string",
            "description": "핵심 답변 (1-2문장)"
        },
        "key_facts": {
            "type": "array",
            "items": {"type": "string"},
            "description": "주요 사실 목록 (3-5개)"
        },
        "details": {
            "type": "string",
            "description": "상세 설명 (선택사항)"
        },
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string"},
                    "page": {"type": "integer"},
                    "start": {"type": "integer"},
                    "end": {"type": "integer"}
                }
            },
            "description": "출처 정보"
        }
    }
    
    VERIFICATION_PROMPT = """다음 답변이 제공된 근거와 일치하는지 검증하세요.

답변: {answer}

근거: {evidence}

답변이 근거에 포함된 내용만 사용했는지 평가하고, 
할루시네이션이 있다면 지적하세요."""
    
    @classmethod
    def format_user_prompt(cls, query: str, evidences: List[Dict]) -> str:
        """Format user prompt with evidences"""
        formatted_evidences = []
        
        for idx, evidence in enumerate(evidences, 1):
            text = evidence.get("text", "")
            # Always use the same format - no filename, only content
            formatted_evidence = cls.EVIDENCE_FORMAT.format(text=text)
            formatted_evidences.append(formatted_evidence)
        
        return cls.USER_PROMPT_TEMPLATE.format(
            query=query,
            evidences="\n\n".join(formatted_evidences)
        )
    
    @classmethod
    def format_verification_prompt(cls, answer: str, evidence: str) -> str:
        """Format verification prompt"""
        return cls.VERIFICATION_PROMPT.format(
            answer=answer,
            evidence=evidence
        )
    
    @classmethod
    def get_system_prompt(cls, evidences: List[Dict] = None) -> str:
        """Get system prompt"""
        return cls.SYSTEM_PROMPT
    
    @classmethod
    def get_json_schema(cls) -> Dict:
        """Get JSON schema for structured output"""
        return {
            "type": "object",
            "properties": cls.OUTPUT_SCHEMA,
            "required": ["answer", "key_facts", "sources"]
        }