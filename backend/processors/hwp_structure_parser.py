import os
import re
import json
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import jpype
import jpype.imports
from jpype import JClass
import logging

logger = logging.getLogger(__name__)

class HWPStructureParser:
    """HWP document structure parser using hwplib via JPype"""
    
    def __init__(self):
        self.jvm_started = False
        self.hwp_file = None
        
    def _start_jvm(self):
        """Start JVM with hwplib"""
        if not jpype.isJVMStarted():
            # Find hwplib jar
            jar_path = self._find_hwplib_jar()
            if not jar_path:
                raise RuntimeError("hwplib.jar not found. Please install hwplib.")
            
            jpype.startJVM(classpath=[jar_path])
            self.jvm_started = True
            logger.info("JVM started with hwplib")
    
    def _find_hwplib_jar(self) -> Optional[str]:
        """Find hwplib jar file"""
        possible_paths = [
            "./lib/hwplib.jar",
            "/usr/local/lib/hwplib.jar",
            os.path.expanduser("~/lib/hwplib.jar")
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None
    
    def parse_hwp(self, file_path: str) -> Dict:
        """Parse HWP document structure"""
        if not self.jvm_started:
            self._start_jvm()
        
        result = {
            "doc_id": Path(file_path).stem,
            "file_path": file_path,
            "sections": [],
            "tables": [],
            "footnotes": [],
            "metadata": {}
        }
        
        try:
            # Load HWP file using hwplib
            HWPFile = JClass("kr.dogfoot.hwplib.object.HWPFile")
            HWPReader = JClass("kr.dogfoot.hwplib.reader.HWPReader")
            
            self.hwp_file = HWPReader.fromFile(file_path)
            
            # Extract document info
            doc_info = self.hwp_file.getDocInfo()
            if doc_info:
                result["metadata"] = {
                    "title": str(doc_info.getDocumentProperties().getTitle() or ""),
                    "author": str(doc_info.getDocumentProperties().getAuthor() or ""),
                    "created": str(doc_info.getDocumentProperties().getCreateDate() or ""),
                    "pages": self._count_pages()
                }
            
            # Parse sections
            section_idx = 0
            for section in self.hwp_file.getBodyText().getSectionList():
                section_data = self._parse_section(section, section_idx)
                result["sections"].append(section_data)
                section_idx += 1
                
                # Extract tables and footnotes from section
                result["tables"].extend(section_data.get("tables", []))
                result["footnotes"].extend(section_data.get("footnotes", []))
            
            logger.info(f"Parsed HWP: {len(result['sections'])} sections, "
                       f"{len(result['tables'])} tables, {len(result['footnotes'])} footnotes")
            
        except Exception as e:
            logger.error(f"Failed to parse HWP: {e}")
            # Fallback to basic text extraction
            result = self._fallback_parse(file_path)
        
        return result
    
    def _parse_section(self, section, section_idx: int) -> Dict:
        """Parse a single section"""
        section_data = {
            "section_id": section_idx,
            "paragraphs": [],
            "tables": [],
            "footnotes": []
        }
        
        para_idx = 0
        char_offset = 0
        
        for para in section.getParagraphList():
            para_text = self._extract_paragraph_text(para)
            
            if para_text.strip():
                # Check if it's a numbered item (조/항/호)
                structure_type = self._detect_structure_type(para_text)
                
                para_data = {
                    "para_id": para_idx,
                    "text": para_text,
                    "structure_type": structure_type,
                    "start_char": char_offset,
                    "end_char": char_offset + len(para_text),
                    "page": self._estimate_page(char_offset)
                }
                
                section_data["paragraphs"].append(para_data)
                char_offset += len(para_text) + 1  # +1 for newline
                para_idx += 1
            
            # Extract tables from paragraph
            tables = self._extract_tables_from_para(para, section_idx, para_idx)
            if tables:
                section_data["tables"].extend(tables)
            
            # Extract footnotes
            footnotes = self._extract_footnotes_from_para(para, section_idx, para_idx)
            if footnotes:
                section_data["footnotes"].extend(footnotes)
        
        return section_data
    
    def _extract_paragraph_text(self, paragraph) -> str:
        """Extract text from paragraph"""
        try:
            text_parts = []
            for run in paragraph.getRunList():
                for char_run in run.getCharRunList():
                    text = str(char_run.getCharList())
                    text_parts.append(text)
            return "".join(text_parts)
        except:
            return ""
    
    def _detect_structure_type(self, text: str) -> Optional[str]:
        """Detect document structure type (조/항/호)"""
        patterns = {
            "article": r"^제\s*\d+\s*조",  # 제1조, 제 2 조
            "paragraph": r"^[①②③④⑤⑥⑦⑧⑨⑩]",  # ① ② ③
            "item": r"^\d+\.",  # 1. 2. 3.
            "subitem": r"^[가나다라마바사아자차카타파하]\.",  # 가. 나. 다.
        }
        
        for struct_type, pattern in patterns.items():
            if re.match(pattern, text.strip()):
                return struct_type
        return None
    
    def _extract_tables_from_para(self, paragraph, section_idx: int, para_idx: int) -> List[Dict]:
        """Extract tables from paragraph"""
        tables = []
        try:
            control_list = paragraph.getControlList()
            if control_list:
                for control in control_list:
                    if control.getType() == 20:  # Table type in hwplib
                        table = control.getTable()
                        table_data = {
                            "table_id": f"table-{section_idx}-{para_idx}-{len(tables)}",
                            "section_id": section_idx,
                            "para_id": para_idx,
                            "rows": [],
                            "caption": ""
                        }
                        
                        # Extract table rows
                        for row in table.getRowList():
                            row_data = []
                            for cell in row.getCellList():
                                cell_text = self._extract_cell_text(cell)
                                row_data.append(cell_text)
                            table_data["rows"].append(row_data)
                        
                        tables.append(table_data)
        except:
            pass
        
        return tables
    
    def _extract_cell_text(self, cell) -> str:
        """Extract text from table cell"""
        try:
            text_parts = []
            for para in cell.getParagraphList():
                text_parts.append(self._extract_paragraph_text(para))
            return " ".join(text_parts)
        except:
            return ""
    
    def _extract_footnotes_from_para(self, paragraph, section_idx: int, para_idx: int) -> List[Dict]:
        """Extract footnotes from paragraph"""
        footnotes = []
        try:
            control_list = paragraph.getControlList()
            if control_list:
                for control in control_list:
                    if control.getType() == 17:  # Footnote type in hwplib
                        footnote = control.getFootnote()
                        footnote_data = {
                            "footnote_id": f"footnote-{section_idx}-{para_idx}-{len(footnotes)}",
                            "section_id": section_idx,
                            "para_id": para_idx,
                            "number": len(footnotes) + 1,
                            "text": self._extract_footnote_text(footnote)
                        }
                        footnotes.append(footnote_data)
        except:
            pass
        
        return footnotes
    
    def _extract_footnote_text(self, footnote) -> str:
        """Extract text from footnote"""
        try:
            text_parts = []
            for para in footnote.getParagraphList():
                text_parts.append(self._extract_paragraph_text(para))
            return " ".join(text_parts)
        except:
            return ""
    
    def _count_pages(self) -> int:
        """Estimate page count"""
        try:
            # HWP doesn't directly expose page count, estimate from content
            total_chars = 0
            for section in self.hwp_file.getBodyText().getSectionList():
                for para in section.getParagraphList():
                    total_chars += len(self._extract_paragraph_text(para))
            
            # Rough estimate: ~2000 chars per page
            return max(1, total_chars // 2000)
        except:
            return 1
    
    def _estimate_page(self, char_offset: int) -> int:
        """Estimate page number from character offset"""
        # Rough estimate: ~2000 chars per page
        return (char_offset // 2000) + 1
    
    def _fallback_parse(self, file_path: str) -> Dict:
        """Fallback parsing when hwplib fails"""
        logger.warning("Using fallback HWP parser")
        
        result = {
            "doc_id": Path(file_path).stem,
            "file_path": file_path,
            "sections": [{
                "section_id": 0,
                "paragraphs": [{
                    "para_id": 0,
                    "text": f"[HWP 파일 파싱 실패: {file_path}]",
                    "structure_type": None,
                    "start_char": 0,
                    "end_char": 100,
                    "page": 1
                }],
                "tables": [],
                "footnotes": []
            }],
            "tables": [],
            "footnotes": [],
            "metadata": {}
        }
        
        return result
    
    def close(self):
        """Close parser and shutdown JVM if needed"""
        if self.jvm_started and jpype.isJVMStarted():
            jpype.shutdownJVM()
            self.jvm_started = False