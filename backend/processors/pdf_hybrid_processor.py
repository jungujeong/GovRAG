import os
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import logging
import tempfile
import json

logger = logging.getLogger(__name__)

class PDFHybridProcessor:
    """Hybrid PDF processor using PyMuPDF with OCR fallback"""
    
    def __init__(self, ocr_threshold: float = 0.6):
        self.ocr_threshold = ocr_threshold
        self.tesseract_config = r'--oem 3 --psm 6 -l kor+eng'
        
    def parse_pdf(self, file_path: str) -> Dict:
        """Parse PDF document with hybrid approach"""
        
        # 파일명에 '구청장 지시사항'이 포함된 경우 특별 처리
        file_name = Path(file_path).name
        if '구청장' in file_name and '지시' in file_name:
            logger.info(f"Detected directive document: {file_name}")
            
            # Use the strict v2 directive extractor (완전 재구현 버전)
            from processors.directive_extractor_strict_v2 import process_pdf
            
            # Process PDF to get structured directives
            records, _ = process_pdf(file_path)
            
            # Convert to document format for RAG system
            pages = {}
            for record in records:
                page_num = record['page']
                
                if page_num not in pages:
                    pages[page_num] = {
                        'page_num': page_num,
                        'text': '',
                        'blocks': []
                    }
                
                # Add directive as text block - 깨끗하게 처리된 텍스트만 사용
                cleaned_text = record['directive']
                
                pages[page_num]['blocks'].append({
                    'text': cleaned_text,
                    'type': 'directive',
                    'departments': record.get('departments', []),
                    'index': record['index']
                })
                
                # Concatenate text
                if pages[page_num]['text']:
                    pages[page_num]['text'] += '\n\n'
                pages[page_num]['text'] += cleaned_text
            
            # Sort pages
            sorted_pages = [pages[k] for k in sorted(pages.keys())]
            
            return {
                "doc_id": Path(file_path).stem,
                "file_path": file_path,
                "pages": sorted_pages,
                "tables": [],  # 테이블 중복 처리 방지
                "metadata": {"doc_type": "gucheong_jisisa"}
            }
        
        # 일반 PDF 처리 (구청장 지시사항이 아닌 경우)
        result = {
            "doc_id": Path(file_path).stem,
            "file_path": file_path,
            "pages": [],
            "tables": [],
            "metadata": {}
        }
        
        try:
            with fitz.open(file_path) as doc:
                # Extract metadata
                metadata = doc.metadata
                result["metadata"] = {
                    "title": metadata.get("title", ""),
                    "author": metadata.get("author", ""),
                    "subject": metadata.get("subject", ""),
                    "pages": doc.page_count,
                    "created": metadata.get("creationDate", "")
                }
                
                # Process each page
                for page_num in range(doc.page_count):
                    page = doc[page_num]
                    
                    # Process page - get raw text first
                    page_data = self._process_page(page, page_num + 1)
                    
                    # Check if OCR is needed
                    if self._needs_ocr(page_data["text"]):
                        logger.info(f"Page {page_num + 1} needs OCR")
                        page_data = self._ocr_page(page, page_num + 1)
                    
                    result["pages"].append(page_data)
                
                logger.info(f"Parsed PDF: {doc.page_count} pages")
                
        except Exception as e:
            logger.error(f"Failed to parse PDF: {e}")
            result["pages"] = [{
                "page_num": 1,
                "text": f"[PDF 파일 파싱 실패: {file_path}]",
                "blocks": []
            }]
        
        return result
    
    def _process_page(self, page, page_num: int) -> Dict:
        """Process a single PDF page"""
        page_data = {
            "page_num": page_num,
            "text": "",
            "blocks": [],
            "links": []
        }
        
        try:
            # Extract text blocks
            blocks = page.get_text("dict")
            
            text_parts = []
            char_offset = 0
            
            for block_idx, block in enumerate(blocks.get("blocks", [])):
                if block.get("type") == 0:  # Text block
                    block_text = self._extract_block_text(block)
                    
                    if block_text.strip():
                        # 기본 텍스트 정리
                        block_text = self._clean_text(block_text)
                        
                        block_data = {
                            "block_id": block_idx,
                            "text": block_text,
                            "bbox": block.get("bbox", []),
                            "start_char": char_offset,
                            "end_char": char_offset + len(block_text)
                        }
                        
                        page_data["blocks"].append(block_data)
                        text_parts.append(block_text)
                        char_offset += len(block_text) + 1
            
            page_data["text"] = "\n".join(text_parts)
            
            # Extract links
            for link in page.get_links():
                page_data["links"].append({
                    "rect": link.get("rect", []),
                    "uri": link.get("uri", ""),
                    "page": link.get("page", -1)
                })
            
        except Exception as e:
            logger.error(f"Error processing page {page_num}: {e}")
        
        return page_data
    
    def _clean_text(self, text: str) -> str:
        """기본 텍스트 정리"""
        # 특수문자 제거
        special_chars = ['󰏅', '󰎨', '│', '┃', '┌', '┐', '└', '┘', 
                        '├', '┤', '┬', '┴', '┼', '─', '━']
        for char in special_chars:
            text = text.replace(char, '')
        
        # 중복 공백 제거
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        
        return text.strip()
    
    def _extract_block_text(self, block: Dict) -> str:
        """Extract text from a block"""
        text_parts = []
        
        for line in block.get("lines", []):
            line_text = ""
            for span in line.get("spans", []):
                span_text = span.get("text", "")
                line_text += span_text
            
            if line_text.strip():
                text_parts.append(line_text)
        
        return "\n".join(text_parts)
    
    def _needs_ocr(self, text: str) -> bool:
        """Check if OCR is needed based on text extraction rate"""
        if not text or len(text.strip()) < 100:
            return True
        
        # Check for Korean characters
        korean_chars = len(re.findall(r'[가-힣]', text))
        total_chars = len(re.findall(r'[가-힣a-zA-Z0-9]', text))
        
        if total_chars == 0:
            return True
        
        # If too few meaningful characters extracted
        extraction_rate = total_chars / max(len(text), 1)
        return extraction_rate < self.ocr_threshold
    
    def _ocr_page(self, page, page_num: int) -> Dict:
        """Perform OCR on a page"""
        page_data = {
            "page_num": page_num,
            "text": "",
            "blocks": [],
            "ocr": True
        }
        
        try:
            # Render page to image
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
            img_data = pix.tobytes("png")
            
            # Convert to PIL Image
            image = Image.open(io.BytesIO(img_data))
            
            # Perform OCR
            ocr_text = pytesseract.image_to_string(
                image,
                config=self.tesseract_config
            )
            
            # Clean OCR text
            ocr_text = self._clean_text(ocr_text)
            
            # Get detailed OCR data
            ocr_data = pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT,
                config=self.tesseract_config
            )
            
            # Process OCR results into blocks
            current_block = []
            current_block_text = []
            char_offset = 0
            
            for i in range(len(ocr_data['text'])):
                if ocr_data['conf'][i] > 0:  # Valid text
                    text = ocr_data['text'][i]
                    
                    if text.strip():
                        current_block_text.append(text)
                        
                        # Check for block boundary (new paragraph)
                        if ocr_data['block_num'][i] != ocr_data['block_num'][i-1] if i > 0 else False:
                            # Save previous block
                            if current_block_text:
                                block_text = " ".join(current_block_text)
                                page_data["blocks"].append({
                                    "block_id": len(page_data["blocks"]),
                                    "text": block_text,
                                    "bbox": [],  # OCR doesn't provide exact bbox
                                    "start_char": char_offset,
                                    "end_char": char_offset + len(block_text)
                                })
                                char_offset += len(block_text) + 1
                                current_block_text = [text]
            
            # Add last block
            if current_block_text:
                block_text = " ".join(current_block_text)
                page_data["blocks"].append({
                    "block_id": len(page_data["blocks"]),
                    "text": block_text,
                    "bbox": [],
                    "start_char": char_offset,
                    "end_char": char_offset + len(block_text)
                })
            
            page_data["text"] = ocr_text
            logger.info(f"OCR completed for page {page_num}: {len(ocr_text)} chars")
            
        except Exception as e:
            logger.error(f"OCR failed for page {page_num}: {e}")
            page_data["text"] = "[OCR 실패]"
        
        return page_data