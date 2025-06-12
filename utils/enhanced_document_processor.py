import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import chardet
import fitz  # PyMuPDF
import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.schema import Document
from config import DOCUMENTS_PATH, logger

class EnhancedDocumentProcessor:
    """개선된 문서 처리기 - 구조 인식 및 청크 기반 처리"""
    
    def __init__(self, documents_path=DOCUMENTS_PATH):
        self.documents_path = documents_path
        os.makedirs(documents_path, exist_ok=True)
        
        # 청크 분할기 초기화
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ".", "!", "?", ";", ":", " ", ""]
        )
        
        # 한국어 문장 분할을 위한 패턴
        self.korean_sentence_pattern = re.compile(r'[.!?]+[\s]*')
        
        logger.info("개선된 문서 처리기 초기화 완료")
    
    def extract_pdf_with_structure(self, file_path: str) -> List[Dict[str, Any]]:
        """PDF에서 구조 정보를 보존하며 텍스트 추출"""
        try:
            structured_content = []
            
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # 텍스트 추출
                    text = page.extract_text()
                    if text:
                        structured_content.append({
                            'type': 'text',
                            'content': text,
                            'page': page_num,
                            'metadata': {'source_type': 'text'}
                        })
                    
                    # 표 추출
                    tables = page.extract_tables()
                    for table_num, table in enumerate(tables):
                        if table:
                            # 표를 구조화된 형태로 변환
                            table_text = self._format_table(table)
                            structured_content.append({
                                'type': 'table',
                                'content': table_text,
                                'page': page_num,
                                'table_index': table_num,
                                'metadata': {'source_type': 'table'}
                            })
            
            return structured_content
            
        except Exception as e:
            logger.error(f"PDF 구조 추출 실패: {e}")
            # 폴백: 기본 텍스트 추출
            return self._fallback_pdf_extraction(file_path)
    
    def _format_table(self, table: List[List[str]]) -> str:
        """표를 읽기 쉬운 형태로 포맷팅"""
        if not table:
            return ""
        
        # 헤더와 데이터 분리
        headers = table[0] if table else []
        rows = table[1:] if len(table) > 1 else []
        
        formatted_parts = []
        
        # 헤더 추가
        if headers:
            header_text = " | ".join([cell or "" for cell in headers])
            formatted_parts.append(f"[표 헤더] {header_text}")
        
        # 각 행을 구조화된 형태로 변환
        for row_idx, row in enumerate(rows):
            row_pairs = []
            for col_idx, cell in enumerate(row):
                if cell and cell.strip():
                    header = headers[col_idx] if col_idx < len(headers) else f"열{col_idx+1}"
                    row_pairs.append(f"{header}: {cell.strip()}")
            
            if row_pairs:
                formatted_parts.append(f"[행 {row_idx+1}] " + " | ".join(row_pairs))
        
        return "\n".join(formatted_parts)
    
    def _fallback_pdf_extraction(self, file_path: str) -> List[Dict[str, Any]]:
        """기본 PDF 텍스트 추출 (폴백)"""
        try:
            doc = fitz.open(file_path)
            content = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                if text.strip():
                    content.append({
                        'type': 'text',
                        'content': text,
                        'page': page_num + 1,
                        'metadata': {'source_type': 'text_fallback'}
                    })
            
            doc.close()
            return content
            
        except Exception as e:
            logger.error(f"폴백 PDF 추출 실패: {e}")
            return []
    
    def process_hwp_file(self, file_path: str) -> List[Dict[str, Any]]:
        """HWP 파일 처리 (기존 로직 유지)"""
        try:
            # 기존 HWP 처리 로직 사용
            from utils.hwplib.hwp_linux import HwpLinuxExtractor
            
            hwp_extractor = HwpLinuxExtractor()
            text = hwp_extractor.extract_text(file_path)
            
            if text:
                return [{
                    'type': 'text',
                    'content': text,
                    'page': 1,
                    'metadata': {'source_type': 'hwp'}
                }]
            else:
                return []
                
        except Exception as e:
            logger.error(f"HWP 파일 처리 실패: {e}")
            return []
    
    def create_chunks(self, structured_content: List[Dict[str, Any]], 
                     source_metadata: Dict[str, Any]) -> List[Document]:
        """구조화된 컨텐츠를 청크로 분할"""
        chunks = []
        
        for content_item in structured_content:
            content_text = content_item['content']
            if not content_text or not content_text.strip():
                continue
            
            # 텍스트를 청크로 분할
            text_chunks = self.text_splitter.split_text(content_text)
            
            for chunk_idx, chunk_text in enumerate(text_chunks):
                if len(chunk_text.strip()) < 50:  # 너무 짧은 청크 제외
                    continue
                
                # 메타데이터 구성
                chunk_metadata = {
                    **source_metadata,
                    'page': content_item.get('page', 1),
                    'chunk_index': chunk_idx,
                    'content_type': content_item['type'],
                    'total_chunks': len(text_chunks),
                    **content_item.get('metadata', {})
                }
                
                # 표 데이터인 경우 추가 메타데이터
                if content_item['type'] == 'table':
                    chunk_metadata['table_index'] = content_item.get('table_index', 0)
                
                # Document 객체 생성
                doc = Document(
                    page_content=chunk_text,
                    metadata=chunk_metadata
                )
                
                chunks.append(doc)
        
        return chunks
    
    def process_document(self, file_path: str) -> Tuple[List[Document], Dict[str, Any]]:
        """
        문서를 처리하여 청크 리스트와 요약 정보 반환
        
        Returns:
            (chunks, summary_info): 청크 리스트와 요약 정보
        """
        try:
            file_path = str(Path(file_path).absolute())
            file_name = os.path.basename(file_path)
            file_ext = os.path.splitext(file_path)[1].lower()
            
            logger.info(f"문서 처리 시작: {file_name}")
            
            # 기본 메타데이터
            base_metadata = {
                'source': file_name,
                'file_path': file_path,
                'file_type': file_ext
            }
            
            # 파일 타입별 처리
            if file_ext == '.pdf':
                structured_content = self.extract_pdf_with_structure(file_path)
            elif file_ext == '.hwp':
                structured_content = self.process_hwp_file(file_path)
            elif file_ext in ['.txt', '.md']:
                structured_content = self._process_text_file(file_path)
            else:
                raise ValueError(f"지원하지 않는 파일 형식: {file_ext}")
            
            if not structured_content:
                raise ValueError("문서에서 내용을 추출할 수 없습니다")
            
            # 청크 생성
            chunks = self.create_chunks(structured_content, base_metadata)
            
            if not chunks:
                raise ValueError("유효한 청크를 생성할 수 없습니다")
            
            # 요약 정보 생성
            summary_info = {
                'total_chunks': len(chunks),
                'total_pages': max([item.get('page', 1) for item in structured_content]),
                'content_types': list(set([item['type'] for item in structured_content])),
                'file_name': file_name,
                'file_type': file_ext
            }
            
            logger.info(f"문서 처리 완료: {len(chunks)}개 청크 생성")
            return chunks, summary_info
            
        except Exception as e:
            logger.error(f"문서 처리 실패 {file_path}: {e}")
            raise
    
    def _process_text_file(self, file_path: str) -> List[Dict[str, Any]]:
        """텍스트 파일 처리"""
        try:
            # 인코딩 감지
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                detected = chardet.detect(raw_data)
                encoding = detected['encoding'] if detected['encoding'] else 'utf-8'
            
            # 텍스트 읽기
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                text = f.read()
            
            if text.strip():
                return [{
                    'type': 'text',
                    'content': text,
                    'page': 1,
                    'metadata': {'source_type': 'text_file'}
                }]
            else:
                return []
                
        except Exception as e:
            logger.error(f"텍스트 파일 처리 실패: {e}")
            return []
    
    def validate_document(self, file_path: str) -> Tuple[bool, str]:
        """문서 유효성 검사"""
        try:
            if not os.path.exists(file_path):
                return False, "파일이 존재하지 않습니다"
            
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return False, "파일이 비어있습니다"
            
            if file_size > 50 * 1024 * 1024:  # 50MB 제한
                return False, "파일이 너무 큽니다 (50MB 이하만 지원)"
            
            file_ext = os.path.splitext(file_path)[1].lower()
            supported_formats = ['.pdf', '.hwp', '.txt', '.md']
            
            if file_ext not in supported_formats:
                return False, f"지원하지 않는 파일 형식입니다 ({', '.join(supported_formats)} 지원)"
            
            return True, "유효한 문서입니다"
            
        except Exception as e:
            return False, f"유효성 검사 실패: {e}" 