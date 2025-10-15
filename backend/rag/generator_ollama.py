import httpx
import json
import re
from typing import Dict, List, Optional, AsyncIterator
import asyncio
import logging

from config import config
from rag.prompt_templates import PromptTemplates

logger = logging.getLogger(__name__)

class OllamaGenerator:
    """Ollama-based text generator with streaming support"""
    
    def __init__(self):
        self.base_url = config.OLLAMA_HOST
        self.model = config.OLLAMA_MODEL
        self.temperature = config.GEN_TEMPERATURE
        self.top_p = config.GEN_TOP_P
        self.max_tokens = config.GEN_MAX_TOKENS
        self.timeout = httpx.Timeout(120.0, connect=10.0)  # Increase timeout for slower models
    
    async def generate(self, 
                       query: str,
                       evidences: List[Dict],
                       stream: bool = False) -> Dict:
        """Generate response using Ollama"""
        
        # Format prompt
        system_prompt = PromptTemplates.get_system_prompt(evidences)
        user_prompt = PromptTemplates.format_user_prompt(query, evidences)
        
        # Prepare request
        request_data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "stream": stream
        }
        
        try:
            if stream:
                return await self._generate_stream(request_data)
            else:
                return await self._generate_complete(request_data)
                
        except Exception as e:
            logger.error(f"Generation failed: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "error": str(e),
                "answer": "죄송합니다. 응답 생성 중 오류가 발생했습니다.",
                "key_facts": [],
                "sources": []
            }
    
    async def _generate_complete(self, request_data: Dict) -> Dict:
        """Generate complete response"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=request_data
                )
                
                if response.status_code != 200:
                    raise Exception(f"Ollama returned {response.status_code}")
                
                result = response.json()
                
                # Parse response
                content = result.get("message", {}).get("content", "")
                
                # Try to parse structured response
                parsed = self._parse_response(content)
                
                return parsed
                
            except httpx.ConnectError:
                logger.error("Cannot connect to Ollama. Is it running?")
                raise Exception("Ollama 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
    
    async def _generate_stream(self, request_data: Dict) -> AsyncIterator[str]:
        """Generate streaming response"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=request_data
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data:
                                content = data["message"].get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
    
    def _parse_response(self, content: str) -> Dict:
        """Parse LLM response into structured format

        Strategy: Preserve LLM output as much as possible, only extract citations.
        Do NOT force-parse into rigid sections - let LLM's natural formatting shine.
        """

        # Remove think tags if present
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

        logger.info("="*80)
        logger.info("RAW LLM RESPONSE (after think-tag removal):")
        logger.info(content[:1000])
        logger.info("="*80)

        # Initialize result - use raw content as answer by default
        result = {
            "answer": content,  # Use raw content directly
            "key_facts": [],
            "details": "",
            "sources": [],
            "raw_response": content
        }

        # Extract citation numbers for source tracking
        # Pattern: [1], [2], etc.
        citation_pattern = re.compile(r'\[(\d+)\]')
        citations = citation_pattern.findall(content)
        if citations:
            logger.info(f"Extracted citations from response: {citations}")

        # Log final parsed result
        logger.info("PARSED RESPONSE STRUCTURE:")
        logger.info(f"  answer: {result['answer'][:200]}...")
        logger.info(f"  key_facts: {len(result['key_facts'])} items")
        logger.info(f"  details: {len(result['details'])} chars")
        logger.info(f"  citations: {citations}")

        return result
    
    def _clean_non_korean(self, text: str) -> str:
        """DEPRECATED: Minimal cleaning only - preserve all content.

        This function previously destroyed LLM output by removing non-Korean chars.
        Now it only does basic whitespace normalization.
        """
        if not text:
            return text

        # Only normalize excessive whitespace (statistical approach)
        # Collapse multiple spaces/tabs to single space per line
        lines = text.split('\n')
        cleaned_lines = [re.sub(r'[ \t]+', ' ', line) for line in lines]

        return '\n'.join(cleaned_lines).strip()
    
    def _parse_source(self, line: str) -> Optional[Dict]:
        """Parse source citation line"""
        
        # Pattern: (doc_id, p.X, start-end)
        pattern = r'\(([^,]+),\s*p\.(\d+),\s*(\d+)-(\d+)\)'
        match = re.search(pattern, line)
        
        if match:
            return {
                "doc_id": match.group(1),
                "page": int(match.group(2)),
                "start": int(match.group(3)),
                "end": int(match.group(4))
            }
        
        # Alternative pattern: 문서ID: X, 페이지: Y
        pattern2 = r'문서ID:\s*([^,]+),\s*페이지:\s*(\d+)'
        match2 = re.search(pattern2, line)
        
        if match2:
            return {
                "doc_id": match2.group(1),
                "page": int(match2.group(2)),
                "start": 0,
                "end": 0
            }
        
        return None
    
    async def generate_with_context(
        self,
        query: str,
        evidences: List[Dict],
        context: Optional[List[Dict]] = None,
        doc_scope: Optional[Dict] = None,
        stream: bool = False,
    ) -> Dict:
        """Generate response with conversation context"""

        # 항상 컨텍스트를 포함하여 LLM이 질문 유형을 판단하도록 함
        query_lower = query.lower()

        # Format prompt with context - 항상 컨텍스트 포함
        system_prompt = PromptTemplates.get_system_prompt(evidences)
        user_prompt = PromptTemplates.format_user_prompt(
            query,
            evidences,
            context,
            is_meta_query=False,
            doc_scope_metadata=doc_scope,
        )

        # Build message list - 시스템 프롬프트와 사용자 프롬프트만 사용
        # 컨텍스트는 user_prompt에 이미 포함되어 있음
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Prepare request
        request_data = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "stream": stream
        }

        try:
            if stream:
                return await self._generate_stream(request_data)
            else:
                return await self._generate_complete(request_data)
        except Exception as e:
            logger.error(f"Generation with context failed: {e}")
            raise

    async def stream_with_context(
        self,
        query: str,
        evidences: List[Dict],
        context: Optional[List[Dict]] = None,
        doc_scope: Optional[Dict] = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> AsyncIterator[str]:
        """Stream response with conversation context"""

        # 항상 컨텍스트를 포함하여 LLM이 질문 유형을 판단하도록 함
        query_lower = query.lower()

        # Format prompt with context - 항상 컨텍스트 포함
        system_prompt = PromptTemplates.get_system_prompt(evidences)
        user_prompt = PromptTemplates.format_user_prompt(
            query,
            evidences,
            context,
            is_meta_query=False,
            doc_scope_metadata=doc_scope,
        )

        # DEBUG: Log the exact prompts being sent
        logger.info("="*80)
        logger.info("DEBUG: EXACT PROMPT BEING SENT TO OLLAMA")
        logger.info("="*80)
        logger.info(f"System Prompt:\n{system_prompt[:500]}...")
        logger.info("-"*40)
        logger.info(f"User Prompt:\n{user_prompt[:1000]}...")
        logger.info("="*80)

        # Build message list - 시스템 프롬프트와 사용자 프롬프트만 사용
        # 컨텍스트는 user_prompt에 이미 포함되어 있음
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Prepare request
        request_data = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "stream": True
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    'POST',
                    f"{self.base_url}/api/chat",
                    json=request_data
                ) as response:
                    response.raise_for_status()

                    # DEBUG: Collect raw response for logging
                    raw_response_parts = []

                    async for line in response.aiter_lines():
                        # Check cancellation
                        if cancel_event and cancel_event.is_set():
                            break

                        if line:
                            try:
                                data = json.loads(line)
                                if data.get("message", {}).get("content"):
                                    content = data["message"]["content"]
                                    raw_response_parts.append(content)
                                    yield content
                            except json.JSONDecodeError:
                                continue

                    # DEBUG: Log the complete raw response
                    if raw_response_parts:
                        full_raw_response = ''.join(raw_response_parts)
                        logger.info("="*80)
                        logger.info("DEBUG: RAW MODEL RESPONSE FROM OLLAMA")
                        logger.info("="*80)
                        logger.info(f"{full_raw_response[:2000]}...")
                        logger.info("="*80)

        except Exception as e:
            logger.error(f"Stream generation with context failed: {e}")
            raise

    async def check_health(self) -> bool:
        """Check if Ollama is available"""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except:
            return False
