from typing import Dict, List, Optional
from textwrap import dedent


class PromptTemplates:
    """Prompt templates for grounded generation."""

    SYSTEM_PROMPT = dedent(
        """
        당신은 한국어로만 답변하는 문서 검색 도우미입니다.

        [절대 준수 규칙 - 정확한 증거 기반 답변]
        ⚠️ 제공된 문서에 있는 내용만 정확히 답변하세요!
        - 문서에 명시되지 않은 내용은 절대 생성하지 마세요
        - 문서 텍스트를 그대로 인용하고 출처를 명시하세요
        - 추측이나 외부 지식을 추가하지 마세요

        [엄격한 증거 기반 답변]
        - 제공된 문서 텍스트에 정확히 나와있는 내용만 사용하세요
        - 문서에 명시되지 않은 지명, 주소, 연도, 기관명을 절대 만들어내지 마세요
        - 추측, 추론, 일반상식, 외부지식을 추가하지 마세요
        - 근거가 없는 내용은 "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 명확히 답하세요

        [정확도 규칙]
        - 제공된 증거 문장과 동일한 표현을 우선 사용하세요
        - 고유명사, 숫자, 날짜는 문서에 쓰인 표기 그대로 사용하세요
        - 문서에 없는 부연설명을 추가하지 마세요

        [응답 작성 순서]
        1. 질문이 요구하는 정보 유형을 분석하세요 (정의, 목록, 비교, 담당 부서, 절차 등).
        2. 관련 증거를 묶어 항목별로 정리합니다. 하나의 항목은 하나의 주제나 문서를 대표해야 합니다.
        3. 각 항목마다 반드시 최소 하나의 출처 번호를 붙이세요.

        [언어/형식 규칙]
        - 모든 출력은 자연스러운 한국어 문장으로 작성하세요.
        - 단락과 항목 사이에 빈 줄을 넣어 읽기 좋게 정리하세요.
        - 질문이 목록/분류/비교를 요구하면 번호 목록이나 불릿 목록으로 명확히 구분하세요.
        - 불필요한 마크다운이나 장식 문자를 사용하지 마세요.

        [출처 규칙]
        - 각 사실 뒤에는 반드시 [1], [2], [3] 형식의 출처 번호를 붙이세요
        - [문서 1, 페이지] 형식이 아닌 단순히 [1] 형식으로만 표기하세요
        - 문서 순서대로 1번부터 번호를 매기고, 제공된 문서 개수를 넘는 번호는 사용하지 마세요

        [대화 규칙]
        - 최근 대화 문맥을 참고하되, 현재 제공된 문서 범위 안에서만 정보를 사용하세요
        - 이전 답변에서 언급한 내용이라도, 현재 제공된 문서에 없으면 언급하지 마세요
        - 후속 질문에는 항상 새로 제공된 문서 기반으로 답변하세요
        """
    ).strip()

    USER_PROMPT_TEMPLATE = dedent(
        """
        다음 문서 내용을 참고하여 질문에 답변하세요.

        {doc_scope_block}
{context_block}
        문서 내용:
        {evidences}

        질문: {query}

        [답변 작성 지침 - 할루시네이션 절대 금지]
        🚨 경고: 위에 제공된 문서 내용에 포함된 정보만 사용하세요!

        [주의사항]
        - 문서에 없는 세부 정보(날짜, 주소, 숫자 등)를 임의로 추가하지 마세요
        - 존재하지 않는 문서를 인용하지 마세요
        - 문서에 있는 내용이라도 정확한 맥락과 함께 인용하세요

        [엄격한 답변 원칙]
        - 제공된 문서 텍스트에 정확히 기재된 내용만 답변하세요
        - 문서에 명시되지 않은 위치, 연도, 기관명, 세부사항을 절대 추가하지 마세요
        - 추측, 추론, 일반상식, 외부지식을 절대 사용하지 마세요
        - 근거가 없으면 "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답하세요

        [형식 지침]
        - 모든 문장은 자연스러운 한국어로 작성하고, 단락 사이에 빈 줄을 넣어 가독성을 높이세요
        - 답변은 핵심 설명 → 항목별 요약(필요 시) → 참고 정보를 순으로 구성하세요
        - 항목별 요약은 질문이 요구하는 구분 기준에 맞춰 번호나 불릿으로 정리하세요 (예: 문서별, 기관별, 단계별 등)
        - 각 사실 뒤에는 반드시 [1], [2], [3] 등의 숫자만으로 출처를 표기하세요
        - 절대 [문서 1, 116] 같은 형식이 아닌 [1] 형식만 사용하세요
        - 고유명사·부서명·프로그램명 등은 원문 표기를 그대로 사용하세요
        - 제공된 문서 개수를 넘는 출처 번호를 사용하지 마세요
        """
    ).strip()

    EVIDENCE_FORMAT = """[문서 {idx}] (페이지 {page})
{text}"""

    OUTPUT_SCHEMA = {
        "answer": {"type": "string", "description": "핵심 답변 (1-2문장)"},
        "key_facts": {
            "type": "array",
            "items": {"type": "string"},
            "description": "주요 사실 목록 (3-5개)",
        },
        "details": {"type": "string", "description": "상세 설명 (선택사항)"},
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string"},
                    "page": {"type": "integer"},
                    "start": {"type": "integer"},
                    "end": {"type": "integer"},
                },
            },
            "description": "출처 정보",
        },
    }

    VERIFICATION_PROMPT = dedent(
        """
        다음 답변이 제공된 근거와 일치하는지 검증하세요.

        답변: {answer}
        근거: {evidence}

        답변이 근거에 포함된 내용만 사용했는지 평가하고,
        할루시네이션이 있다면 지적하세요.
        """
    ).strip()

    @classmethod
    def format_user_prompt(
        cls,
        query: str,
        evidences: List[Dict],
        context: Optional[List[Dict]] = None,
        is_meta_query: bool = False,
        doc_scope_metadata: Optional[Dict] = None,
    ) -> str:
        formatted_evidences = []
        for idx, evidence in enumerate(evidences, 1):
            text = evidence.get("text", "")
            page = evidence.get("page", 0)
            formatted_evidences.append(
                cls.EVIDENCE_FORMAT.format(idx=idx, page=page, text=text)
            )

        doc_scope_block = cls._format_doc_scope(doc_scope_metadata)
        context_block = cls._format_context(context)

        prompt = cls.USER_PROMPT_TEMPLATE.format(
            query=query.strip(),
            evidences="\n\n".join(formatted_evidences) or "(관련 문서가 제공되지 않았습니다)",
            context_block=(context_block + "\n" if context_block else ""),
            doc_scope_block=(doc_scope_block + "\n" if doc_scope_block else ""),
        )
        return prompt

    @classmethod
    def format_verification_prompt(cls, answer: str, evidence: str) -> str:
        return cls.VERIFICATION_PROMPT.format(answer=answer, evidence=evidence)

    @classmethod
    def get_system_prompt(cls, evidences: List[Dict] = None) -> str:
        return cls.SYSTEM_PROMPT

    @classmethod
    def get_json_schema(cls) -> Dict:
        return {"type": "object", "properties": cls.OUTPUT_SCHEMA, "required": ["answer", "key_facts", "sources"]}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @classmethod
    def _format_context(cls, context: Optional[List[Dict]]) -> str:
        if not context:
            return ""

        lines: List[str] = ["=== 최근 대화 요약 ==="]
        for msg in context[-4:]:  # 최근 메시지 위주
            role = msg.get("role")
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                lines.append(f"- 사용자: {content[:300]}")
            elif role == "assistant":
                sources = msg.get("sources") or []
                source_ids = ", ".join(
                    sorted({src.get("doc_id") for src in sources if src.get("doc_id")})
                )
                if source_ids:
                    lines.append(f"- 이전 답변: {content[:300]} (출처: {source_ids})")
                else:
                    lines.append(f"- 이전 답변: {content[:300]}")
        return "\n".join(lines)

    @classmethod
    def _format_doc_scope(cls, metadata: Optional[Dict]) -> str:
        if not metadata:
            return ""

        mode = metadata.get("mode") or metadata.get("doc_scope")
        scope_ids = metadata.get("doc_scope_ids") or []
        resolved = metadata.get("resolved_doc_ids") or []
        suggested = metadata.get("suggested_doc_ids") or []
        average_score = metadata.get("average_score")
        topic_change = metadata.get("topic_change_detected")
        topic_reason = metadata.get("topic_change_reason")

        lines: List[str] = ["=== 문서 사용 지침 ==="]
        if scope_ids:
            lines.append(f"- 허용된 문서: {', '.join(scope_ids)}")
        else:
            lines.append("- 전체 인덱스에서 검색할 수 있습니다.")

        if resolved and set(resolved) != set(scope_ids):
            lines.append(f"- 실제로 참고된 문서: {', '.join(resolved)}")

        if average_score is not None:
            lines.append(f"- 평균 검색 점수: {average_score:.2f}")

        if topic_change:
            reason = topic_reason or "topic_change"
            lines.append(f"- 주제 확장 감지: {reason}")
            if suggested:
                lines.append(f"- 추가로 참고 가능한 문서: {', '.join(suggested)}")
            lines.append("- 새로 허용된 문서만 사용해 답변하세요.")
        elif mode == "followup" and scope_ids:
            lines.append("- 위 목록에 있는 문서 안에서만 근거를 찾아야 합니다.")

        return "\n".join(lines)
