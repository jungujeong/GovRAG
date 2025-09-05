import httpx
import json
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
        import re
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        
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
                result["answer"] += line + " "
            elif current_section == "key_facts" and line:
                if line.startswith(("-", "•", "*", "·")):
                    result["key_facts"].append(line[1:].strip())
                elif line:
                    result["key_facts"].append(line)
            elif current_section == "details" and line:
                result["details"] += line + " "
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
            result["answer"] = content.strip()
        
        return result
    
    def _parse_source(self, line: str) -> Optional[Dict]:
        """Parse source citation line"""
        import re
        
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
    
    async def check_health(self) -> bool:
        """Check if Ollama is available"""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except:
            return False