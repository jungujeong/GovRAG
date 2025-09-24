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
            self.summary_dir = Path(config.DOC_DIR).parent / "data" / "summaries"
            self.summary_dir.mkdir(parents=True, exist_ok=True)

        except Exception as e:
            logger.error(f"Failed to initialize DocumentSummarizer: {e}")
            raise

    def _get_summary_file_path(self, doc_id: str) -> Path:
        """Get summary file path for document ID"""
        # Normalize document ID for consistent file naming
        doc_id_normalized = unicodedata.normalize("NFC", doc_id)
        return self.summary_dir / f"{doc_id_normalized}_summary.json"

    async def generate_summary(self, file_path: Path, doc_id: str) -> Dict:
        """
        Generate summary for a document
        Args:
            file_path: Path to the document file
            doc_id: Document identifier
        Returns:
            Dict containing summary data
        """
        try:
            logger.info(f"Generating summary for document: {doc_id}")

            # Extract document content
            content = await self._extract_document_content(file_path)
            if not content or not content.strip():
                logger.warning(f"No content extracted from {file_path}")
                return self._create_empty_summary(doc_id, "내용을 추출할 수 없습니다.")

            # Generate summary using existing Ollama generator
            summary_text = await self._generate_summary_text(content)

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

        except Exception as e:
            logger.error(f"Failed to generate summary for {doc_id}: {e}")
            error_summary = self._create_empty_summary(doc_id, f"요약 생성 실패: {str(e)}")
            await self._save_summary(doc_id, error_summary)
            return error_summary

    async def _extract_document_content(self, file_path: Path) -> str:
        """Extract text content from document"""
        try:
            if file_path.suffix.lower() == '.pdf':
                # Use existing PDF processor
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.pdf_processor.process_pdf, str(file_path)
                )
                if result and 'chunks' in result:
                    # Combine all chunk content
                    return '\n'.join([chunk.get('content', '') for chunk in result['chunks']])
                return ""

            elif file_path.suffix.lower() == '.hwp':
                # Use existing HWP parser
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.hwp_parser.parse_hwp, str(file_path)
                )
                if result and 'content' in result:
                    return result['content']
                return ""

            else:
                logger.warning(f"Unsupported file type: {file_path.suffix}")
                return ""

        except Exception as e:
            logger.error(f"Content extraction failed for {file_path}: {e}")
            return ""

    async def _generate_summary_text(self, content: str) -> str:
        """Generate summary text using Ollama"""
        try:
            # Limit content length for summary (to avoid token limits)
            max_content_length = 4000  # Conservative limit
            if len(content) > max_content_length:
                content = content[:max_content_length] + "..."

            # Create a simple HTTP request to Ollama directly for summarization
            import httpx

            system_message = "당신은 한국어 공문서 요약 전문가입니다. 정확하고 간결한 요약을 작성합니다."
            user_message = f"""다음 한국어 공문서의 내용을 간결하게 요약해주세요.
주요 내용, 핵심 사항, 중요한 날짜나 숫자 등을 포함하여 3-5문장으로 요약해주세요.

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

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{config.OLLAMA_HOST}/api/chat",
                    json=request_data
                )

                if response.status_code == 200:
                    result = response.json()
                    summary = result.get("message", {}).get("content", "").strip()
                    if summary:
                        return summary
                    else:
                        return "요약을 생성할 수 없습니다."
                else:
                    logger.error(f"Ollama request failed with status {response.status_code}")
                    return f"요약 생성 서비스 오류 (HTTP {response.status_code})"

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return f"요약 생성 중 오류가 발생했습니다: {str(e)}"

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