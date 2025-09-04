import os
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import logging
# Use improved directive extractor v2
import tempfile
import json

logger = logging.getLogger(__name__)

class PDFHybridProcessor:
    """Hybrid PDF processor using PyMuPDF with OCR fallback"""
    
    def __init__(self, ocr_threshold: float = 0.6):
        self.ocr_threshold = ocr_threshold
        self.tesseract_config = r'--oem 3 --psm 6 -l kor+eng'
        # Use improved directive extractor v2
        from processors.directive_extractor_v2 import process_pdf_to_jsonl, read_dept_list
        self.process_pdf_to_jsonl = process_pdf_to_jsonl
        self.dept_whitelist = read_dept_list("data/dept_whitelist.txt")
        
    def parse_pdf(self, file_path: str) -> Dict:
        """Parse PDF document with hybrid approach"""
        
        # 파일명에 '구청장 지시사항'이 포함된 경우 특별 처리
        file_name = Path(file_path).name
        if '구청장' in file_name and '지시' in file_name:
            logger.info(f"Detected directive document: {file_name}")
            # Use directive_extractor_v2 to process
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as tmp:
                self.process_pdf_to_jsonl(file_path, tmp.name, self.dept_whitelist)
                tmp_path = tmp.name
            
            # Read JSONL results and convert to document format
            pages = []
            with open(tmp_path, 'r', encoding='utf-8') as f:
                for line in f:
                    record = json.loads(line)
                    page_num = record['page']
                    
                    # Find or create page
                    page = next((p for p in pages if p['page_num'] == page_num), None)
                    if not page:
                        page = {
                            'page_num': page_num,
                            'text': '',
                            'blocks': []
                        }
                        pages.append(page)
                    
                    # Add directive as text block
                    page['blocks'].append({
                        'text': record['directive'],
                        'type': 'directive',
                        'departments': record.get('departments', []),
                        'index': record['index']
                    })
                    
                    # Concatenate text
                    if page['text']:
                        page['text'] += '\n\n'
                    page['text'] += record['directive']
            
            # Clean up temp file
            os.unlink(tmp_path)
            
            return {
                "doc_id": Path(file_path).stem,
                "file_path": file_path,
                "pages": sorted(pages, key=lambda x: x['page_num']),
                "tables": [],
                "metadata": {"doc_type": "gucheong_jisisa"}
            }
        
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
                    
                    # Extract tables first
                    tables = self._extract_tables(page, page_num + 1)
                    if tables:
                        result["tables"].extend(tables)
                    
                    # Process page with table awareness
                    page_data = self._process_page(page, page_num + 1)
                    
                    # If tables found, use table text instead of raw text
                    if tables:
                        # Replace poorly extracted text with formatted table text
                        table_texts = [t["text"] for t in tables if t.get("text")]
                        if table_texts:
                            page_data["text"] = "\n\n".join(table_texts)
                            logger.info(f"Page {page_num + 1}: Using formatted table text")
                    
                    # Check if OCR is needed (only if no tables found)
                    elif self._needs_ocr(page_data["text"]):
                        logger.info(f"Page {page_num + 1} needs OCR")
                        page_data = self._ocr_page(page, page_num + 1)
                    
                    result["pages"].append(page_data)
                
                logger.info(f"Parsed PDF: {doc.page_count} pages, {len(result['tables'])} tables")
                
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
    
    def _extract_tables(self, page, page_num: int) -> List[Dict]:
        """Extract tables from PDF page using PyMuPDF's table finder"""
        tables = []
        
        try:
            # Use PyMuPDF's built-in table detection
            table_finders = page.find_tables()
            
            if table_finders:
                for table_idx, table_finder in enumerate(table_finders):
                    try:
                        # Extract table data
                        table_data = table_finder.extract()
                        
                        if table_data and len(table_data) > 0:
                            # Process table data
                            processed_table = {
                                "table_id": f"table-p{page_num}-{table_idx}",
                                "page_num": page_num,
                                "rows": table_data,
                                "text": self._format_table_text(table_data),
                                "bbox": []
                            }
                            tables.append(processed_table)
                            logger.info(f"Extracted table on page {page_num}: {len(table_data)} rows")
                    except Exception as e:
                        logger.warning(f"Failed to extract table {table_idx} on page {page_num}: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
        
        return tables
    
    def _is_table_block(self, block: Dict) -> bool:
        """Detect if a block is likely a table"""
        if block.get("type") != 0:  # Not text
            return False
        
        lines = block.get("lines", [])
        if len(lines) < 2:
            return False
        
        # Check for consistent column alignment
        x_positions = []
        for line in lines:
            for span in line.get("spans", []):
                x_positions.append(span.get("bbox", [0])[0])
        
        if len(set(x_positions)) > 3:  # Multiple distinct x positions
            return True
        
        return False
    
    def _format_table_text(self, table_data: List[List]) -> str:
        """Format table data into readable text, especially for 구청장 지시사항 format"""
        if not table_data:
            return ""
        
        formatted_lines = []
        
        # Check if this is a 구청장 지시사항 table (has specific columns)
        if len(table_data) > 0 and len(table_data[0]) >= 5:
            # Process data rows (skip header)
            for row_idx, row in enumerate(table_data[1:], 1):
                if len(row) >= 3:
                    # Extract key columns
                    category = str(row[1]).strip() if len(row) > 1 else ""  # 처리 구분
                    content = str(row[2]).strip() if len(row) > 2 else ""   # 지시 사항
                    deadline = str(row[3]).strip() if len(row) > 3 else ""  # 처리 기한
                    dept = str(row[4]).strip() if len(row) > 4 else ""      # 주관부서
                    
                    # Clean and reconstruct the content
                    if content and content != '지 시 사 항':  # Skip header
                        # Remove excessive newlines and spaces
                        content = ' '.join(content.split())
                        
                        # Format as a complete instruction
                        if category and '훈시' in category:
                            formatted_lines.append(f"구청장 훈시사항: {content}")
                        elif category and '보고' in category:
                            formatted_lines.append(f"구청장 보고사항: {content}")
                        else:
                            formatted_lines.append(f"구청장 지시사항: {content}")
                        
                        if dept and dept not in ['주관부서', '관련부서', '-']:
                            formatted_lines.append(f"담당부서: {dept}")
                        if deadline and deadline not in ['처리 기한', '-']:
                            formatted_lines.append(f"처리기한: {deadline}")
                        
                        formatted_lines.append("")  # Add empty line between items
        else:
            # Generic table formatting
            for row in table_data:
                if row and any(str(cell).strip() for cell in row):
                    formatted_lines.append(" | ".join(str(cell).strip() for cell in row))
        
        return "\n".join(formatted_lines).strip()
    
    def _extract_table_rows(self, block: Dict) -> List[List[str]]:
        """Extract rows from a table block"""
        rows = []
        
        for line in block.get("lines", []):
            row = []
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if text:
                    row.append(text)
            
            if row:
                rows.append(row)
        
        return rows