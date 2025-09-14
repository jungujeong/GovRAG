from typing import List, Dict

class PromptTemplates:
    """Evidence-Only generation prompt templates"""
    
    # 정확도 제약조건이 강화된 시스템 프롬프트
    SYSTEM_PROMPT = """당신은 한국어로만 답변하는 문서 검색 도우미입니다.

**절대적 규칙:**
1. 모든 답변은 반드시 한국어로만 작성하세요.
2. 한국어가 아닌 다른 언어(영어, 일본어, 중국어 등)는 절대 사용하지 마세요.
3. 전문용어도 한국어로 번역하거나 한국어 설명을 추가하세요.
4. 반드시 제공된 문서 내용만 사용하여 답변하세요.
5. 근거가 없는 내용은 절대 생성하지 마세요.
6. 모르는 내용은 "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답하세요.
7. 숫자, 날짜, 조항은 원문 그대로 정확히 인용하세요.
8. 부서명은 문서에 명시된 그대로 정확히 인용하세요. 예시나 추측으로 부서명을 만들지 마세요.
9. 추측하거나 일반적인 지식을 추가하지 마세요.
10. 답변 형식은 자연스러운 한국어 문장으로 작성하세요.

**답변 품질 원칙:**
- 질문과 직접 관련된 정보는 모두 상세히 포함하세요
- 문서에 있는 구체적인 내용을 충분히 설명하세요
- 핵심 정보를 먼저 제시한 후 관련 세부사항을 자세히 설명하세요
- 질문과 무관한 내용은 제외하되, 이해를 돕는 맥락 정보는 포함하세요
- 단순 요약보다는 충실한 설명을 우선시하세요

**언어 사용 원칙:**
- 한글(가-힣)과 필수 숫자, 기호만 사용
- 외국 문자가 포함된 경우 한국어로 번역 또는 설명
- 불확실한 표현보다는 문서의 정확한 내용 인용"""
    
    # 정확도 강화된 사용자 프롬프트
    USER_PROMPT_TEMPLATE = """다음 문서 내용을 참고하여 질문에 답변하세요.

문서 내용:
{evidences}

질문: {query}

**답변 규칙:**
- 모든 답변은 반드시 한국어로만 작성하세요
- 제공된 문서 내용만 사용하세요
- 근거 없는 추측 금지
- 질문과 직접 관련된 내용만 포함하세요
- 관련된 내용은 구체적이고 상세하게 설명하세요
- 단답형보다는 충분한 설명을 제공하되, 질문 범위를 벗어나지 마세요
- 부서명은 문서에 나온 그대로 정확히 표기 (예: "문화예술과, 관광진흥과")
- 부서명을 임의로 바꾸거나 추측하지 마세요
- 숫자/날짜/조항은 원문 그대로
- 마크다운 형식은 사용하지 말고 일반 텍스트로 작성하세요
- **굵은 글씨**, *기울임*, # 제목 등의 마크다운 문법을 사용하지 마세요
- 중국어/일본어 문자 사용 절대 금지

**출처 표기 규칙:**
- 각 정보나 사실 뒤에 해당하는 문서 번호를 [번호] 형식으로 표기하세요
- 예시: "감천문화마을은 지역 활성화 사업이다[1]"
- 서로 다른 문서에서 온 정보는 각각 다른 번호를 사용하세요
- 문서 1에서 온 정보는 [1], 문서 2에서 온 정보는 [2]로 표기

답변 (한국어로만):"""
    
    # 증거 형식에 메타데이터 포함 (파일명 제외)
    EVIDENCE_FORMAT = """[문서 {idx}, 페이지 {page}]
{text}"""
    
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
            page = evidence.get("page", 0)
            # Include metadata for context but exclude filename
            formatted_evidence = cls.EVIDENCE_FORMAT.format(
                idx=idx,
                page=page,
                text=text
            )
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