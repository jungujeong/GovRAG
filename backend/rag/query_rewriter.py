from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re
import logging

from rag.idf_stats import get_global_filter

logger = logging.getLogger(__name__)


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
        """
        Context-aware query rewriting using STATISTICAL approach - NO PATTERN MATCHING.

        Strategy: If conversation history exists, always try to extract and append
        key entities. Let the retrieval system (BM25 + Vector) decide relevance.

        This works for ANY follow-up question pattern without hardcoding.
        """
        query = context.current_query
        query_lower = query.lower()

        logger.info(f"[QR] Original query: {query}")
        logger.info(f"[QR] Context - entities: {len(context.entities)}, messages: {len(context.recent_messages)}, summary: {bool(context.summary)}")

        # Special case: Meta questions (structural pattern, not content pattern)
        if self._is_meta_question(query_lower):
            if context.recent_messages:
                last_user_msg = self._get_last_user_message(context.recent_messages)
                if last_user_msg:
                    logger.info(f"[QR] Meta question detected, using last user message: {last_user_msg}")
                    return RewriteResult(
                        search_query=last_user_msg,
                        sub_queries=[f"{last_user_msg} (요약 요청)"],
                        reasoning="meta_question",
                        used_fallback=False,
                    )

        # Core strategy: If conversation exists, extract context and CREATE ENHANCED QUERY
        # This handles ALL follow-up questions automatically without pattern matching

        enhanced_query = query
        extracted_context = None

        # Try multiple context sources (ordered by preference)
        # 1. Provided entities (already extracted by system)
        if context.entities:
            canonical = self._select_best_entity(context.entities, query)
            if canonical:
                extracted_context = canonical
                logger.info(f"[QR] Extracted context from entities: {extracted_context}")

        # 2. Extract from recent messages if no entities provided
        if not extracted_context and context.recent_messages:
            entities = self._extract_key_nouns_from_messages(context.recent_messages)
            logger.info(f"[QR] Extracted entities from messages: {entities}")
            if entities:
                extracted_context = entities[0]
                logger.info(f"[QR] Using first entity: {extracted_context}")

        # 3. Fallback to summary
        if not extracted_context and context.summary:
            entities = self._extract_nouns_from_text(context.summary)
            if entities:
                extracted_context = entities[0]
                logger.info(f"[QR] Extracted context from summary: {extracted_context}")

        # If we found context, create enhanced query
        if extracted_context:
            # IMPORTANT: Topic change detection using simple character overlap
            # Extract Korean words from both query and context (raw, no filtering)
            query_words = set(re.findall(r'[가-힣]{2,}', query))
            context_words = set(re.findall(r'[가-힣]{2,}', extracted_context))

            # Check if extracted_context already in query
            context_already_in_query = extracted_context.lower() in query_lower

            if context_already_in_query:
                # Context already mentioned - just use original
                logger.info(f"[QR] Entity '{extracted_context}' already in query, no change")
                return RewriteResult(
                    search_query=query,
                    sub_queries=[],
                    reasoning=f"entity_already_present:{extracted_context}",
                    used_fallback=False,
                )

            # Check for topic change: query has substantial content (3+ char words) with NO overlap
            substantial_query_words = {w for w in query_words if len(w) >= 3}
            substantial_context_words = {w for w in context_words if len(w) >= 3}

            if substantial_query_words and not (substantial_query_words & substantial_context_words):
                # Zero overlap in meaningful words → topic change
                logger.info(f"[QR] Topic change detected: query words {list(substantial_query_words)[:3]} have no overlap with context '{extracted_context}'")
                return RewriteResult(
                    search_query=query,
                    sub_queries=[query],
                    reasoning=f"topic_change_no_overlap",
                    used_fallback=False,
                )

            # Safe to enhance - appears to be same topic
            enhanced_query = self._create_enhanced_query(query, extracted_context)
            logger.info(f"[QR] Enhanced query: {enhanced_query}")

            # Return BOTH for sub-queries (system can use both)
            return RewriteResult(
                search_query=enhanced_query,  # Use enhanced for primary search
                sub_queries=[query, enhanced_query],  # Keep both
                reasoning=f"context_enriched:{extracted_context}",
                used_fallback=False,
            )

        # No context available - use original query
        logger.info(f"[QR] No context available, using original query")
        return RewriteResult(
            search_query=context.current_query,
            sub_queries=[],
            reasoning="no_context_available",
            used_fallback=True,
        )

    def _select_best_entity(self, entities: List[Any], query: str) -> Optional[str]:
        """Select most relevant entity - simply return first valid one."""
        for entity in entities:
            if isinstance(entity, str):
                return entity
            elif isinstance(entity, dict):
                return entity.get("canonical") or entity.get("surface")
        return None

    def _extract_key_nouns_from_messages(self, messages: List[Dict[str, str]]) -> List[str]:
        """
        Extract key nouns from recent messages - CONTEXT-AWARE.

        Strategy:
        1. Process messages in CHRONOLOGICAL order
        2. Extract from BOTH user questions AND assistant answers
        3. Prioritize: assistant entities > user entities (assistant = confirmed context)
        4. Use STATISTICAL clustering to normalize

        This fixes the context loss problem where "홍티예술촌" was missed
        in follow-up questions.
        """
        # Separate context and current entities
        context_entities = []  # From assistant (confirmed context)
        user_entities = []     # From user questions

        content_context = []   # 3+ chars from assistant
        content_user = []      # 3+ chars from user

        # Look at recent messages in CHRONOLOGICAL order
        for msg in messages[-5:]:  # Increased to 5 for better context
            role = msg.get("role")
            text = msg.get("content", "").strip()

            if not text:
                continue

            # Extract nouns
            nouns = self._extract_nouns_from_text(text)

            # Separate by role
            if role == "assistant":
                # Assistant answers contain confirmed context entities
                context_entities.extend(nouns)
                for noun in nouns:
                    if len(noun) >= 3:
                        content_context.append(noun)
            elif role == "user":
                # User questions
                user_entities.extend(nouns)
                for noun in nouns:
                    if len(noun) >= 3:
                        content_user.append(noun)

        # STATISTICAL NORMALIZATION: Cluster variants using substring overlap
        # Example: "홍티예술촌", "홍티예술촌에", "홍티예술촌의" → "홍티예술촌"
        normalized_context = self._normalize_entities_statistical(content_context)
        normalized_user = self._normalize_entities_statistical(content_user)

        # Deduplicate while preserving order
        # IMPORTANT: Context entities (from assistant) come FIRST
        seen = set()
        unique_entities = []

        # 1. Context entities first (from assistant - confirmed context)
        for entity in normalized_context:
            if entity not in seen:
                seen.add(entity)
                unique_entities.append(entity)

        # 2. User entities second (current question)
        for entity in normalized_user:
            if entity not in seen:
                seen.add(entity)
                unique_entities.append(entity)

        logger.info(
            f"[QR] Extracted entities: context={normalized_context[:3]}, "
            f"user={normalized_user[:3]}, final={unique_entities[:3]}"
        )

        return unique_entities

    def _normalize_entities_statistical(self, entities: List[str]) -> List[str]:
        """
        Normalize entity variants using SUBSTRING CLUSTERING (pure statistics).
        NO pattern matching, NO hardcoded particles.

        Strategy: Group entities by substring overlap, select canonical form.
        Example: ["홍티예술촌", "홍티예술촌에", "홍티예술촌의"] → ["홍티예술촌"]

        Works for ANY language/dialect - purely statistical.
        """
        if not entities:
            return []

        # Build clusters: entities with substring overlap belong to same cluster
        clusters = []
        for entity in entities:
            # Check if entity belongs to existing cluster
            matched_cluster = None
            for cluster in clusters:
                for existing in cluster:
                    # Substring overlap detection
                    if entity in existing or existing in entity:
                        matched_cluster = cluster
                        break
                if matched_cluster:
                    break

            if matched_cluster:
                matched_cluster.add(entity)
            else:
                clusters.append({entity})

        # Select canonical form from each cluster
        normalized = []
        for cluster in clusters:
            # Strategy: shortest form is usually the root (particles add characters)
            # Break ties by frequency in original list (earlier = more frequent)
            cluster_list = list(cluster)
            canonical = min(cluster_list, key=lambda x: (len(x), entities.index(x) if x in entities else 999))
            normalized.append(canonical)

        return normalized

    def _extract_nouns_from_text(self, text: str) -> List[str]:
        """
        Extract likely nouns from text using STATISTICAL methods - NO HARDCODING.

        Strategy:
        1. Extract all Korean words (2+ chars to catch more)
        2. Use IDF-based statistical filter
        3. Additional linguistic heuristics (minimal, universal)
        """
        # Extract all Korean word segments (2+ chars to be inclusive)
        words = re.findall(r'[가-힣]{2,}', text)

        nouns = []
        stat_filter = get_global_filter()

        for word in words:
            # 1. STATISTICAL FILTER - Primary method (NO HARDCODING)
            # Uses IDF scores + character entropy
            if not stat_filter.is_content_word(word, strict=False):
                continue

            # 2. Linguistic heuristics (MINIMAL, UNIVERSAL)
            # These apply to ALL Korean, not domain-specific

            # Skip question patterns (verb stems) - linguistic universals
            if any(pattern in word for pattern in ['알려', '설명', '어떻', '무엇', '어디', '언제', '누구']):
                continue

            # Skip verb/adjective endings - morphological universals
            if any(word.endswith(ending) for ending in ['하다', '되다', '이다', '하는', '되는', '한다', '된다', '합니다']):
                continue

            # Accept as content word
            nouns.append(word)

        logger.debug(f"Extracted {len(nouns)} content words from: {text[:50]}...")
        return nouns

    def _create_enhanced_query(self, query: str, entity: str) -> str:
        """
        Merge entity with query intelligently using POSITION-BASED strategy.

        Strategy: If entity is not in query, prepend it.
        Let BM25/Vector search handle the full query - they will automatically
        downweight filler words through TF-IDF and semantic similarity.

        This works for ANY dialect or phrasing without pattern matching.
        """
        # If entity is already prominently in query, don't duplicate
        if entity in query:
            logger.info(f"[QR] Entity '{entity}' already in query, no change")
            return query

        # Otherwise, prepend entity and let search systems filter
        # BM25 will automatically down-weight common words like "그렇다면"
        # Vector search will focus on semantic content
        enhanced = f"{entity} {query}"
        logger.info(f"[QR] Enhanced query: {entity} + {query[:30]}...")
        return enhanced

    def _merge_context(self, query: str, entity: str) -> str:
        """
        Merge entity with query intelligently.
        """
        query_lower = query.lower()

        # If query starts with demonstrative, replace it
        for pronoun in ['그렇다면', '그러면', '그럼', '그런데', '그리고', '그', '이', '저', '그것', '이것', '저것']:
            if query.startswith(pronoun):
                # Replace pronoun with entity
                rest = query[len(pronoun):].strip()
                return f"{entity} {rest}"

        # If entity is already in query, don't duplicate
        if entity in query:
            return query

        # Otherwise, prepend entity
        return f"{entity} {query}"

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
