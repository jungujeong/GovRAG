from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re


@dataclass
class RewriteContext:
    """Input payload for query rewriting."""

    current_query: str
    recent_messages: List[Dict[str, str]] = field(default_factory=list)
    summary: str = ""
    entities: List[Any] = field(default_factory=list)
    previous_sources: List[Dict] = field(default_factory=list)  # 이전 답변의 출처


@dataclass
class RewriteResult:
    """Structured result for rewritten queries."""

    search_query: str
    sub_queries: List[str]
    reasoning: str
    used_fallback: bool


class QueryRewriter:
    """Enhanced query rewriter for pronoun resolution and context understanding."""

    pronoun_tokens = ("그", "이", "저", "그것", "이것", "저것", "그거", "이거", "저거")
    meta_keywords = ("요약", "정리", "간단히", "짧게", "다시", "설명")

    def __init__(self) -> None:
        pass

    def rewrite(self, context: RewriteContext) -> RewriteResult:
        query_lower = context.current_query.lower()

        # 메타 질문 처리 (요약, 정리 등)
        if self._is_meta_question(query_lower):
            # 이전 대화 컨텍스트가 있으면 이를 활용
            if context.recent_messages:
                last_user_msg = self._get_last_user_message(context.recent_messages)
                if last_user_msg:
                    # "요약해줘" -> 이전 질문 + "요약"
                    rewritten = f"{last_user_msg} (요약 요청)"
                    return RewriteResult(
                        search_query=last_user_msg,  # 원래 질문으로 검색
                        sub_queries=[rewritten],
                        reasoning="meta_question_with_previous_context",
                        used_fallback=False,
                    )
            # 컨텍스트가 없으면 원본 쿼리 사용
            return RewriteResult(
                search_query=context.current_query,
                sub_queries=[],
                reasoning="meta_question_without_context",
                used_fallback=True,
            )

        # 대명사 해결
        if not context.entities or not context.summary:
            return RewriteResult(
                search_query=context.current_query,
                sub_queries=[],
                reasoning="insufficient_context",
                used_fallback=True,
            )

        canonical = self._select_entity(context.entities, context.current_query)
        if not canonical:
            return RewriteResult(
                search_query=context.current_query,
                sub_queries=[],
                reasoning="no_entity_match",
                used_fallback=True,
            )

        rewritten = self._replace_pronoun(context.current_query, canonical)
        reasoning = (
            f"resolved_pronoun_using:{canonical}"
            if rewritten != context.current_query
            else "entity_context_appended"
        )
        sub_queries = [rewritten]

        return RewriteResult(
            search_query=rewritten,
            sub_queries=sub_queries,
            reasoning=reasoning,
            used_fallback=False,
        )

    def _select_entity(
        self, entities: List[Any], query: str
    ) -> Optional[str]:
        lowered_query = query
        best = None
        for entity in entities:
            if isinstance(entity, str):
                candidate = entity
            else:
                candidate = (
                    entity.get("canonical")
                    or entity.get("surface")
                    if isinstance(entity, dict)
                    else None
                )
            if not candidate:
                continue
            if best is None:
                best = candidate
            if any(keyword in lowered_query for keyword in ("예산", "budget")) and "예산" in candidate:
                return candidate
        return best

    def _replace_pronoun(self, query: str, canonical: str) -> str:
        # Replace leading pronoun tokens with canonical entity.
        stripped = query.strip()
        for token in self.pronoun_tokens:
            pattern = rf"^{re.escape(token)}\s+"
            if re.match(pattern, stripped):
                return re.sub(pattern, f"{canonical} ", stripped, count=1)
        return f"{canonical} {stripped}" if canonical not in stripped else stripped

    def _is_meta_question(self, query_lower: str) -> bool:
        """메타 질문인지 확인 (요약, 정리 등)"""
        for keyword in self.meta_keywords:
            if keyword in query_lower:
                return True
        return False

    def _get_last_user_message(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """최근 사용자 메시지 찾기"""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "").strip()
                # 메타 질문이 아닌 실제 질문 반환
                if content and not self._is_meta_question(content.lower()):
                    return content
        return None
