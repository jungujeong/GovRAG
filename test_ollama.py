#!/usr/bin/env python3
"""Test Ollama generation directly"""

import asyncio
import httpx
import json

async def test_ollama():
    """Test Ollama with a simple prompt"""
    
    request_data = {
        "model": "qwen3:4b",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant that answers in Korean."
            },
            {
                "role": "user", 
                "content": """다음 문서를 바탕으로 '지역경제 활성화'에 대해 답변하세요:

문서: 구청장 지시사항 - 지역경제 및 상권 활성화 노력: 현재 경제가 불황으로 수당대금 지급 등을 조속히 처리

답변 형식:
1. 핵심 답변: (1-2문장)
2. 주요 사실: (2-3개)"""
            }
        ],
        "temperature": 0.0,
        "stream": False
    }
    
    print("Sending request to Ollama...")
    print(f"Model: {request_data['model']}")
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        try:
            response = await client.post(
                "http://localhost:11434/api/chat",
                json=request_data
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("message", {}).get("content", "")
                print("\nOllama Response:")
                print("-" * 50)
                print(content)
                print("-" * 50)
                
                # Check response time
                if "total_duration" in result:
                    duration_s = result["total_duration"] / 1_000_000_000
                    print(f"\nGeneration time: {duration_s:.1f} seconds")
            else:
                print(f"Error: Status {response.status_code}")
                print(response.text)
                
        except httpx.TimeoutException:
            print("ERROR: Request timed out after 120 seconds")
            print("The model might be too slow or not loaded")
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_ollama())