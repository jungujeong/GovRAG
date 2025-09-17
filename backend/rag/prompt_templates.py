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

**고유명사 정확성 규칙 (절대 위반 금지):**
- 모든 고유명사(장소, 기관, 시설 등)는 문서에 표기된 그대로 사용하세요
- 고유명사를 변형하거나 유사한 다른 이름으로 바꾸지 마세요
- 괄호를 사용한 부연설명도 문서에 있는 경우에만 사용하세요
- 예: 문서에 "홍티예술촌"이면 그대로 "홍티예술촌"만 사용 (다른 이름 추가 금지)

**대화 컨텍스트 처리 원칙:**
- 이전 대화 내용을 참고하여 질문의 의도를 파악하세요
- 후속 질문인 경우 이전 답변의 내용과 출처를 활용하세요
- 사용자가 이전 답변에서 특정 부분을 더 자세히 원할 수 있으므로 주의 깊게 파악하세요
- 이전에 언급한 내용을 반복하지 말고 새로운 관점이나 추가 정보를 제공하세요

**출처 일관성 원칙 (매우 중요):**
- **대화가 시작된 후, 첫 번째 답변에서 사용한 문서만을 계속 사용하세요**
- 후속 질문에서는 첫 번째 답변의 문서 범위를 절대 벗어나지 마세요
- 새로운 문서 번호나 출처를 추가하면 안 됩니다
- **제공된 문서 내용에만 기반하여 답변하세요**
- **문서에 없는 내용은 추측하거나 생성하지 마세요**

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

{context_info}

질문: {query}

**답변 규칙:**
- 모든 답변은 반드시 한국어로만 작성하세요
- 제공된 문서 내용만 사용하세요
- 근거 없는 추측 금지
- 질문과 직접 관련된 내용만 포함하세요
- 관련된 내용은 구체적이고 상세하게 설명하세요
- 단답형보다는 충분한 설명을 제공하되, 질문 범위를 벗어나지 마세요
- 모든 고유명사와 정보는 문서에 나온 그대로 정확히 표기
- 문서에 없는 내용을 임의로 추가하지 마세요
- 숫자/날짜/조항은 원문 그대로
- 마크다운 형식은 사용하지 말고 일반 텍스트로 작성하세요
- **굵은 글씨**, *기울임*, # 제목 등의 마크다운 문법을 사용하지 마세요
- 중국어/일본어 문자 사용 절대 금지

**고유명사 검증 (필수):**
- 답변 전 모든 고유명사가 문서에 있는 그대로인지 확인하세요
- 유사하지만 다른 이름으로 바꾸지 마세요 (예: 홍티예술촌 → 홍티아트바이오 X)
- 문서에 없는 괄호 설명을 추가하지 마세요

**질문 유형별 처리:**
1. 요약/정리 요청: 이전 대화의 핵심 내용을 간결하게 정리하세요
2. 구체적 정보 요청 (부서명, 각 항목별 등): 이전 답변에서 언급된 내용을 기반으로 상세히 설명하세요
3. 후속 질문: 이전 답변과 연결하여 추가 정보를 제공하세요
4. 새로운 질문: 제공된 문서를 기반으로 새롭게 답변하세요
5. **중요**: 위에 제공된 문서 내용에 없는 정보는 절대 언급하지 마세요

**출처 표기 규칙:**
- 각 정보나 사실 뒤에 해당하는 문서 번호를 [번호] 형식으로 표기하세요
- 예시: "감천문화마을은 지역 활성화 사업이다[1]"
- 제공된 문서 순서대로 [1], [2], [3] 등으로 표기
- **절대 금지: 제공되지 않은 문서 번호(예: [4], [5] 등)를 사용하지 마세요**
- **절대 금지: 제공되지 않은 문서명(예: 제066호)을 언급하지 마세요**
- **중요: 후속 질문에서는 이전에 사용한 출처만 사용하세요**

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
    def format_user_prompt(cls, query: str, evidences: List[Dict], context: List[Dict] = None, is_meta_query: bool = False) -> str:
        """Format user prompt with evidences and context"""
        formatted_evidences = []
        evidence_doc_ids = set()  # 현재 제공된 evidence의 문서 ID 추적

        for idx, evidence in enumerate(evidences, 1):
            text = evidence.get("text", "")
            page = evidence.get("page", 0)
            doc_id = evidence.get("doc_id", "")
            if doc_id:
                evidence_doc_ids.add(doc_id)
            # Include metadata for context but exclude filename
            formatted_evidence = cls.EVIDENCE_FORMAT.format(
                idx=idx,
                page=page,
                text=text
            )
            formatted_evidences.append(formatted_evidence)

        # 대화 컨텍스트 정보 추가 - 항상 포함 (메타 질문 여부와 관계없이)
        context_info = ""
        if context:
            context_lines = []
            previous_doc_ids = set()
            first_answer_doc_ids = set()
            first_answer_found = False

            # 첫 번째 답변의 출처를 먼저 찾기
            for msg in context:
                if msg.get("role") == "assistant" and not first_answer_found:
                    sources = msg.get('sources', [])
                    if sources:
                        for s in sources:
                            doc_id = s.get('doc_id', '')
                            if doc_id:
                                first_answer_doc_ids.add(doc_id)
                        first_answer_found = True
                        break

            # 최근 대화 내용 포함
            for msg in context[-4:]:  # 최근 4개 메시지 (질문-답변 2쌍)
                if msg.get("role") == "user":
                    context_lines.append(f"이전 질문: {msg.get('content', '')}")
                elif msg.get("role") == "assistant":
                    content = msg.get('content', '')
                    # 출처 정보도 포함
                    sources = msg.get('sources', [])
                    if sources:
                        source_info = ", ".join([f"[{s.get('doc_id', '')}]" for s in sources[:3]])
                        context_lines.append(f"이전 답변: {content[:500]}... 출처: {source_info}")
                    else:
                        context_lines.append(f"이전 답변: {content[:500]}...")

            # 첫 답변의 출처 사용
            if first_answer_doc_ids:
                previous_doc_ids = first_answer_doc_ids
            if context_lines:
                doc_restriction = ""
                if previous_doc_ids or first_answer_doc_ids:
                    # 더 강력한 출처 제한 메시지 - 범용적 접근
                    doc_restriction = f"\n\n⚠️ **후속 답변 규칙** ⚠️\n"
                    doc_restriction += f"이것은 대화의 후속 답변입니다.\n"
                    doc_restriction += f"• 첫 답변의 문서 범위 유지: {sorted(list(first_answer_doc_ids or previous_doc_ids))}\n"
                    doc_restriction += f"• 현재 제공된 문서 내용만 사용\n"
                    doc_restriction += f"• 제공된 문서에 없는 새로운 정보 생성 금지\n"
                    doc_restriction += f"• 모든 답변에 출처 [번호] 표기 필수\n"
                    doc_restriction += f"• 출처 번호는 제공된 문서 순서를 따름\n"
                context_info = "\n=== 대화 컨텍스트 ===\n" + "\n".join(context_lines) + doc_restriction + "\n===============\n"

        return cls.USER_PROMPT_TEMPLATE.format(
            query=query,
            evidences="\n\n".join(formatted_evidences),
            context_info=context_info
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