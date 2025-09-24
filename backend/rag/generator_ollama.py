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
        """Parse LLM response into structured format"""
        
        # Remove think tags if present
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        
        # Clean up any non-Korean language remnants
        content = self._clean_non_korean(content)
        
        # Initialize result
        result = {
            "answer": "",
            "key_facts": [],
            "details": "",
            "sources": [],
            "raw_response": content
        }
        
        # Try to parse structured sections
        lines = content.strip().split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            # Detect sections
            if "핵심 답변" in line or "답변:" in line:
                current_section = "answer"
                continue
            elif "주요 사실" in line or "사실:" in line:
                current_section = "key_facts"
                continue
            elif "상세 설명" in line or "설명:" in line:
                current_section = "details"
                continue
            elif "출처" in line or "참조:" in line:
                current_section = "sources"
                continue
            
            # Add content to sections
            if current_section == "answer" and line:
                cleaned_line = self._clean_non_korean(line)
                result["answer"] += cleaned_line + " "
            elif current_section == "key_facts" and line:
                cleaned_line = self._clean_non_korean(line)
                if cleaned_line.startswith(("-", "•", "*", "·")):
                    result["key_facts"].append(cleaned_line[1:].strip())
                elif cleaned_line:
                    result["key_facts"].append(cleaned_line)
            elif current_section == "details" and line:
                cleaned_line = self._clean_non_korean(line)
                result["details"] += cleaned_line + " "
            elif current_section == "sources" and line:
                # Parse source format
                source = self._parse_source(line)
                if source:
                    result["sources"].append(source)
        
        # Clean up
        result["answer"] = result["answer"].strip()
        result["details"] = result["details"].strip()
        
        # If no structured parsing worked, use whole content as answer
        if not result["answer"] and not result["key_facts"]:
            result["answer"] = self._clean_non_korean(content.strip())
        
        return result
    
    def _clean_non_korean(self, text: str) -> str:
        """Remove non-Korean content while preserving line breaks and spacing semantics."""
        if not text:
            return text

        out_chars = []
        for ch in text:
            # Preserve newlines and tabs to avoid merging tokens across lines
            if ch in ('\n', '\t'):
                out_chars.append(ch)
                continue
            code = ord(ch)
            if (
                0xAC00 <= code <= 0xD7AF or  # Hangul Syllables
                0x1100 <= code <= 0x11FF or  # Hangul Jamo
                0x3130 <= code <= 0x318F or  # Hangul Compatibility Jamo
                0xA960 <= code <= 0xA97F or  # Hangul Jamo Extended-A
                0xD7B0 <= code <= 0xD7FF     # Hangul Jamo Extended-B
            ):
                out_chars.append(ch)
            elif 0x0020 <= code <= 0x007E:  # Basic ASCII printable
                out_chars.append(ch)
            elif ch in '·、。「」『』〈〉《》【】〔〕':
                out_chars.append(ch)
            else:
                out_chars.append(' ')

        # Collapse spaces per line but preserve line boundaries
        cleaned_lines = []
        for line in ''.join(out_chars).splitlines(True):  # keepends=True
            # Replace runs of spaces/tabs with a single space
            replaced = re.sub(r'[ \t]+', ' ', line)
            cleaned_lines.append(replaced)

        result = ''.join(cleaned_lines)
        return result.strip('\n')
    
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
