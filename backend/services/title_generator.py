"""
LLM 기반 세션 제목 생성 서비스
"""
import httpx
import json
import logging
from typing import Optional
from config import config

logger = logging.getLogger(__name__)

class TitleGenerator:
    """LLM을 활용한 동적 제목 생성 서비스"""

    def __init__(self):
        self.base_url = config.OLLAMA_HOST
        self.model = config.OLLAMA_MODEL
        self.timeout = httpx.Timeout(10.0, connect=5.0)

    async def generate_title(self, first_message: str, assistant_response: Optional[str] = None) -> str:
        """
        LLM을 사용하여 대화 내용 기반 제목 생성

        Args:
            first_message: 사용자의 첫 메시지
            assistant_response: 어시스턴트의 첫 응답 (선택)

        Returns:
            생성된 제목
        """
        if not first_message:
            return "새 대화"

        # LLM 프롬프트 구성
        system_prompt = """당신은 대화 제목을 생성하는 전문가입니다.

규칙:
1. 대화의 핵심 주제를 2-5단어로 간결하게 요약
2. 구체적이고 명확한 표현 사용
3. 일반적인 표현 대신 고유명사나 핵심 키워드 포함
4. 한국어로만 작성
5. 조사나 불필요한 단어 최소화

좋은 예시:
- "홍티예술촌 환경개선"
- "예산 편성 절차"
- "관광 활성화 방안"
- "부서별 업무 분장"

나쁜 예시:
- "질문입니다"
- "알려주세요"
- "대화"
- "새로운 주제"
"""

        user_prompt = f"""다음 대화의 제목을 생성하세요.

사용자 질문: {first_message[:200]}

{f'어시스턴트 답변 요약: {assistant_response[:200]}' if assistant_response else ''}

제목 (2-5단어, 20자 이내):"""

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.3,  # 일관성 있는 제목 생성
                        "max_tokens": 50,
                        "stream": False
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    title = result.get("message", {}).get("content", "").strip()

                    # 후처리
                    title = self._clean_title(title)

                    if title and len(title) > 1:
                        return title

        except Exception as e:
            logger.error(f"LLM 제목 생성 실패: {e}")

        # 폴백: 간단한 규칙 기반
        return self._fallback_title(first_message)

    def _clean_title(self, title: str) -> str:
        """제목 정리 및 검증"""
        # 따옴표, 마침표 등 제거
        title = title.strip().strip('"\'').strip('.')

        # 불필요한 접두사 제거
        prefixes = ["제목:", "주제:", "대화 제목:", "제목은"]
        for prefix in prefixes:
            if title.startswith(prefix):
                title = title[len(prefix):].strip()

        # 길이 제한
        if len(title) > 30:
            # 의미 단위로 자르기
            if " " in title:
                words = title.split()
                result = ""
                for word in words:
                    if len(result + " " + word) <= 30:
                        result = (result + " " + word).strip()
                    else:
                        break
                title = result if result else title[:30]
            else:
                title = title[:30]

        return title

    def _fallback_title(self, message: str) -> str:
        """LLM 실패 시 폴백 제목 생성"""
        # 핵심 키워드 추출
        import re

        # 특수 패턴 우선 확인
        patterns = [
            (r"([\가-\힣]+(?:예술촌|문화마을|공단|상권|사업))", r"\1"),
            (r"([\가-\힣]+) (?:대해|관해|관련)", r"\1"),
            (r"([\가-\힣]{2,5})(?:이|가|은|는|을|를) ", r"\1"),
        ]

        for pattern, replacement in patterns:
            match = re.search(pattern, message)
            if match:
                return re.sub(pattern, replacement, message[:30]).strip()

        # 기본: 첫 20자
        title = message[:20].strip()

        # 조사 제거
        for particle in ["이", "가", "을", "를", "은", "는"]:
            if title.endswith(particle):
                title = title[:-len(particle)]
                break

        return title if len(title) > 1 else "새 대화"

    async def update_title_with_context(self, current_title: str, new_context: str) -> str:
        """
        대화가 진행되면서 제목 업데이트 (필요 시)

        Args:
            current_title: 현재 제목
            new_context: 새로운 대화 내용

        Returns:
            업데이트된 제목 (변경 불필요 시 현재 제목)
        """
        # 현재는 첫 대화에서만 제목 생성
        # 추후 필요시 대화 진행에 따른 제목 업데이트 로직 추가 가능
        return current_title