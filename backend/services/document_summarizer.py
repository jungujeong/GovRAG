"""
Document Summarizer Service
문서 요약 생성 및 관리 서비스
"""
import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import unicodedata

# Import existing RAG components (safe imports)
try:
    from config import config
    from rag.generator_ollama import OllamaGenerator
    from processors.pdf_hybrid_processor import PDFHybridProcessor
    from processors.hwp_structure_parser import HWPStructureParser
    from processors.normalizer_govkr import NormalizerGovKR
except ImportError as e:
    logging.error(f"Import error in document_summarizer: {e}")
    raise

logger = logging.getLogger(__name__)

class DocumentSummarizer:
    """문서 요약 생성 및 관리 클래스"""

    def __init__(self):
        """Initialize summarizer with existing components"""
        try:
            self.generator = OllamaGenerator()
            self.pdf_processor = PDFHybridProcessor()
            self.hwp_parser = HWPStructureParser()
            self.normalizer = NormalizerGovKR()

            # Summary storage directory
            # config.DOC_DIR is already BASE_DIR / "data" / "documents"
            # So .parent gets us to "data", not "data/data"
            self.summary_dir = Path(config.DOC_DIR).parent / "summaries"
            self.summary_dir.mkdir(parents=True, exist_ok=True)

        except Exception as e:
            logger.error(f"Failed to initialize DocumentSummarizer: {e}")
            raise

    def _get_summary_file_path(self, doc_id: str) -> Path:
        """Get summary file path for document ID"""
        # Normalize document ID for consistent file naming
        doc_id_normalized = unicodedata.normalize("NFC", doc_id)
        return self.summary_dir / f"{doc_id_normalized}_summary.json"

    async def generate_summary(self, file_path: Path, doc_id: str, request=None) -> Dict:
        """
        Generate summary for a document
        Args:
            file_path: Path to the document file
            doc_id: Document identifier
            request: Optional FastAPI Request object to check client connection
        Returns:
            Dict containing summary data
        """
        try:
            logger.info(f"Generating summary for document: {doc_id}")

            # Check if client disconnected
            if request and await request.is_disconnected():
                logger.info(f"Client disconnected, aborting summary generation for: {doc_id}")
                raise ConnectionError("Client disconnected")

            # Extract document content
            content = await self._extract_document_content(file_path)
            if not content or not content.strip():
                logger.warning(f"No content extracted from {file_path}")
                return self._create_empty_summary(doc_id, "내용을 추출할 수 없습니다.")

            # Check again before heavy Ollama operation
            if request and await request.is_disconnected():
                logger.info(f"Client disconnected before Ollama request for: {doc_id}")
                raise ConnectionError("Client disconnected")

            # Generate summary using existing Ollama generator
            summary_text = await self._generate_summary_text(content, request)

            # Detect if summary generation actually failed
            summary_trimmed = summary_text.strip()
            is_error = (
                not summary_trimmed or  # Empty summary
                len(summary_trimmed) < 20 or  # Too short
                "오류" in summary_text or
                "실패" in summary_text or
                "생성할 수 없습니다" in summary_text or
                summary_trimmed.endswith(':')  # Empty error message
            )

            # Don't save error summaries - let frontend retry
            if is_error:
                logger.warning(f"Summary generation produced error/empty result for {doc_id}: {summary_trimmed[:100]}")
                raise ValueError(f"Invalid summary generated: {summary_trimmed[:100]}")

            # Create summary data structure
            summary_data = {
                "doc_id": doc_id,
                "file_name": file_path.name,
                "summary": summary_text,
                "generated_at": datetime.now().isoformat(),
                "content_length": len(content),
                "status": "completed"
            }

            # Save summary to file
            await self._save_summary(doc_id, summary_data)

            logger.info(f"Summary generated successfully for: {doc_id}")
            return summary_data

        except ConnectionError as e:
            # Client disconnected - don't save error, just log and re-raise
            logger.info(f"Client disconnected during summary generation for {doc_id}")
            raise

        except Exception as e:
            # Get error message, fallback to exception type if empty
            error_msg = str(e).strip() if str(e).strip() else type(e).__name__

            # Log detailed error information
            logger.error(
                f"Failed to generate summary for {doc_id}: {error_msg}",
                exc_info=True,
                extra={"doc_id": doc_id, "file_path": str(file_path), "error_type": type(e).__name__}
            )

            # Don't save error summaries - raise exception so frontend can retry
            raise

    async def _extract_document_content(self, file_path: Path) -> str:
        """Extract text content from document"""
        try:
            if file_path.suffix.lower() == '.pdf':
                # Use existing PDF processor
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.pdf_processor.parse_pdf, str(file_path)
                )
                if result and 'pages' in result:
                    # Combine all page text
                    return '\n\n'.join([page.get('text', '') for page in result['pages']])
                return ""

            elif file_path.suffix.lower() == '.hwp':
                # Use existing HWP parser
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.hwp_parser.parse_hwp, str(file_path)
                )
                if result and 'pages' in result:
                    # Combine all page text
                    return '\n\n'.join([page.get('text', '') for page in result['pages']])
                elif result and 'content' in result:
                    # Fallback to content field if available
                    return result['content']
                return ""

            else:
                logger.warning(f"Unsupported file type: {file_path.suffix}")
                return ""

        except Exception as e:
            logger.error(f"Content extraction failed for {file_path}: {e}")
            return ""

    async def _generate_summary_text(self, content: str, request=None) -> str:
        """Generate summary text using Ollama with retry logic"""
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            # Check if client disconnected before each retry
            if request and await request.is_disconnected():
                logger.info(f"Client disconnected during Ollama retry (attempt {attempt + 1}/{max_retries})")
                raise ConnectionError("Client disconnected")

            try:
                # Limit content length for summary (to avoid token limits)
                max_content_length = 4000  # Conservative limit
                if len(content) > max_content_length:
                    content = content[:max_content_length] + "..."

                # Create a simple HTTP request to Ollama directly for summarization
                import httpx
                import re

                system_message = "당신은 한국어 공문서 요약 전문가입니다. 정확하고 간결한 요약을 작성합니다. <think> 태그나 생각 과정을 포함하지 말고 요약 내용만 출력하세요."
                user_message = f"""다음 한국어 공문서의 내용을 간결하게 요약해주세요.
주요 내용, 핵심 사항, 중요한 날짜나 숫자 등을 포함하여 3-5문장으로 요약해주세요.
<think> 태그나 사고 과정 없이 요약 내용만 작성하세요.

문서 내용:
{content}

요약:"""

                request_data = {
                    "model": config.OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": 0.1,  # Low temperature for consistent summaries
                    "stream": False
                }

                logger.info(f"Attempt {attempt + 1}/{max_retries}: Requesting summary from Ollama")

                # Longer timeout for slower computers (3 minutes)
                async with httpx.AsyncClient(timeout=180.0) as client:
                    response = await client.post(
                        f"{config.OLLAMA_HOST}/api/chat",
                        json=request_data
                    )

                if response.status_code == 200:
                    result = response.json()
                    summary = result.get("message", {}).get("content", "").strip()

                    logger.info(f"Raw Ollama response: {summary[:200]}...")  # Log first 200 chars

                    if summary:
                        # Remove <think> tags and their content
                        original_length = len(summary)
                        summary = re.sub(r'<think>.*?</think>', '', summary, flags=re.DOTALL)
                        logger.info(f"After removing <think> tags: {len(summary)} chars (was {original_length})")

                        # Remove any remaining XML-like tags
                        summary = re.sub(r'<[^>]+>', '', summary)
                        # Clean up extra whitespace
                        summary = re.sub(r'\s+', ' ', summary).strip()

                        logger.info(f"Final summary: {summary[:200]}...")  # Log first 200 chars

                        if summary:
                            logger.info(f"Successfully generated summary on attempt {attempt + 1}")
                            return summary
                        else:
                            last_error = "요약이 정상적으로 생성되지 않았습니다. 다시 시도해주세요."
                            logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: Summary became empty after cleaning")
                            if attempt < max_retries - 1:
                                continue
                    else:
                        last_error = "요약을 생성할 수 없습니다."
                        logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: Ollama returned empty summary")
                        if attempt < max_retries - 1:
                            continue
                else:
                    last_error = f"요약 생성 서비스 오류 (HTTP {response.status_code})"
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: Ollama request failed with status {response.status_code}")
                    if attempt < max_retries - 1:
                        continue

            except httpx.TimeoutException:
                last_error = "요약 생성 시간 초과: Ollama 서비스 응답이 없습니다."
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: Ollama request timed out")
                if attempt < max_retries - 1:
                    continue
            except httpx.ConnectError:
                last_error = "요약 생성 연결 실패: Ollama 서비스에 연결할 수 없습니다."
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: Cannot connect to Ollama")
                if attempt < max_retries - 1:
                    continue
            except Exception as e:
                # Get error message, fallback to exception type name if empty
                error_msg = str(e).strip() if str(e).strip() else type(e).__name__
                last_error = f"요약 생성 중 오류가 발생했습니다: {error_msg}"
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {error_msg}", exc_info=True)
                if attempt < max_retries - 1:
                    continue

        # All retries exhausted - raise exception instead of returning error message
        error_message = last_error or "요약 생성 중 알 수 없는 오류가 발생했습니다."
        logger.error(f"Summary generation failed after {max_retries} attempts. Last error: {last_error}")
        raise Exception(error_message)

    def _create_empty_summary(self, doc_id: str, message: str) -> Dict:
        """Create empty/error summary structure"""
        return {
            "doc_id": doc_id,
            "file_name": "",
            "summary": message,
            "generated_at": datetime.now().isoformat(),
            "content_length": 0,
            "status": "error"
        }

    async def _save_summary(self, doc_id: str, summary_data: Dict):
        """Save summary data to JSON file"""
        try:
            summary_file = self._get_summary_file_path(doc_id)

            # Write summary data
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to save summary for {doc_id}: {e}")

    async def get_summary(self, doc_id: str) -> Optional[Dict]:
        """
        Get existing summary for document
        Args:
            doc_id: Document identifier
        Returns:
            Summary data dict or None if not found
        """
        try:
            summary_file = self._get_summary_file_path(doc_id)

            if not summary_file.exists():
                logger.info(f"No summary file found for: {doc_id}")
                return None

            with open(summary_file, 'r', encoding='utf-8') as f:
                summary_data = json.load(f)

            logger.info(f"Summary loaded for: {doc_id}")
            return summary_data

        except Exception as e:
            logger.error(f"Failed to load summary for {doc_id}: {e}")
            return None

    async def delete_summary(self, doc_id: str) -> bool:
        """
        Delete summary for document
        Args:
            doc_id: Document identifier
        Returns:
            True if deleted successfully
        """
        try:
            summary_file = self._get_summary_file_path(doc_id)

            if summary_file.exists():
                summary_file.unlink()
                logger.info(f"Summary deleted for: {doc_id}")
                return True
            else:
                logger.info(f"No summary file to delete for: {doc_id}")
                return True  # Consider it successful if file doesn't exist

        except Exception as e:
            logger.error(f"Failed to delete summary for {doc_id}: {e}")
            return False

    async def list_summaries(self) -> List[Dict]:
        """
        List all available summaries
        Returns:
            List of summary metadata
        """
        try:
            summaries = []

            for summary_file in self.summary_dir.glob("*_summary.json"):
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summary_data = json.load(f)

                    # Add file info
                    summary_data['file_path'] = str(summary_file)
                    summaries.append(summary_data)

                except Exception as e:
                    logger.warning(f"Failed to read summary file {summary_file}: {e}")
                    continue

            logger.info(f"Found {len(summaries)} summaries")
            return summaries

        except Exception as e:
            logger.error(f"Failed to list summaries: {e}")
            return []