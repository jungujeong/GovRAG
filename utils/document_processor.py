import os
import subprocess
import tempfile
import chardet
from pathlib import Path
import logging
import time
import sys
import platform
from config import DOCUMENTS_PATH, logger
import fitz  # PyMuPDF

# HWP Linux/Mac OS 지원을 위한 hwplib 임포트
try:
    from utils.hwplib.hwp_linux import HwpLinuxExtractor
    HWPLIB_AVAILABLE = True
except ImportError:
    HWPLIB_AVAILABLE = False
    logger.warning("hwplib를 불러올 수 없습니다. HWP 파일 처리가 제한될 수 있습니다.")

class DocumentProcessor:
    def __init__(self, documents_path=DOCUMENTS_PATH):
        self.documents_path = documents_path
        os.makedirs(documents_path, exist_ok=True)
        
        # hwplib 초기화
        self.hwp_extractor = None
        if HWPLIB_AVAILABLE:
            try:
                self.hwp_extractor = HwpLinuxExtractor()
                logger.info("hwplib 초기화 완료 - HWP 파일 처리 가능")
            except Exception as e:
                logger.error(f"hwplib 초기화 실패: {e}")
                self.hwp_extractor = None
    
    def process_hwp_file(self, file_path):
        """hwplib를 사용하여 HWP 파일 처리"""
        try:
            # 경로가 Path 객체인 경우 문자열로 변환
            if isinstance(file_path, Path):
                file_path = str(file_path)
                
            # 절대 경로로 변환
            file_path = os.path.abspath(file_path)
            logger.info(f"hwplib로 HWP 처리 중, 절대 경로: {file_path}")
            
            if not self.hwp_extractor:
                logger.error("hwplib가 초기화되지 않았습니다.")
                return "HWP 처리 모듈이 초기화되지 않았습니다."
                
            text = self.hwp_extractor.extract_text(file_path)
            
            if text and len(text.strip()) > 0:
                return text
            else:
                logger.error("추출된 텍스트가 없습니다.")
                return "텍스트 추출 실패"
                
        except Exception as e:
            logger.error(f"HWP 파일 처리 중 오류: {e}")
            return f"HWP 파일 처리 오류: {str(e)}"
    
    def _read_text_file(self, file_path):
        """일반 텍스트 파일 읽기"""
        try:
            # 파일 인코딩 감지
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                detected = chardet.detect(raw_data)
                encoding = detected['encoding'] if detected['encoding'] else 'utf-8'
            
            # 텍스트 파일 읽기
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                text = f.read()
                
            return text
        except Exception as e:
            logger.error(f"텍스트 파일 읽기 실패: {e}")
            return ""
    
    def process_pdf(self, file_path):
        """PDF 파일에서 텍스트 추출"""
        try:
            # 경로가 Path 객체인 경우 문자열로 변환
            if isinstance(file_path, Path):
                file_path = str(file_path)
                
            # 절대 경로로 변환
            file_path = os.path.abspath(file_path)
            
            # PDF 파일 열기
            doc = fitz.open(file_path)
            
            # 모든 페이지의 텍스트 추출
            text = ""
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text += page.get_text()
            
            # 문서 닫기
            doc.close()
            
            return text
        except Exception as e:
            logger.error(f"PDF 파일 처리 중 오류: {e}")
            return ""
    
    def extract_text(self, file_path):
        """
        파일에서 텍스트 추출 (확장자에 따라 적절한 방법 선택)
        
        Returns:
            (text, metadata): 텍스트와 메타데이터 쌍
        """
        if not os.path.exists(file_path):
            logger.error(f"파일이 존재하지 않습니다: {file_path}")
            return "", {"error": "파일이 존재하지 않습니다"}
            
        file_ext = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path)
        metadata = {"source": file_name}
        
        # HWP 파일 처리
        if file_ext == '.hwp':
            # hwplib 사용
            if self.hwp_extractor:
                logger.info("hwplib를 사용하여 HWP 파일 처리")
                text = self.process_hwp_file(file_path)
                if isinstance(text, str) and len(text.strip()) > 0:
                    return text, metadata
                else:
                    return "", {"error": "텍스트 추출 실패", "source": file_name}
            else:
                logger.error("HWP 파일 처리 모듈이 초기화되지 않았습니다.")
                return "", {"error": "HWP 파일 처리 모듈이 초기화되지 않았습니다", "source": file_name}
        
        # PDF 파일 처리
        elif file_ext == '.pdf':
            text = self.process_pdf(file_path)
            return text, metadata
        
        # 텍스트 파일 처리
        elif file_ext in ['.txt', '.csv', '.md', '.json', '.xml', '.html']:
            text = self._read_text_file(file_path)
            return text, metadata
            
        # 지원하지 않는 파일 형식
        else:
            logger.warning(f"지원하지 않는 파일 형식: {file_ext}")
            return "", {"error": f"지원하지 않는 파일 형식: {file_ext}", "source": file_name}
    
    def validate_file(self, file_path):
        """
        파일 유효성 검사
        
        Returns:
            (is_valid, message): 유효성 여부와 메시지
        """
        if not os.path.exists(file_path):
            return False, "파일이 존재하지 않습니다."
            
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext not in ['.hwp', '.pdf']:
            return False, f"지원하지 않는 파일 형식: {file_ext}. HWP 또는 PDF 파일만 지원됩니다."
        
        # HWP 파일인 경우 hwplib 가용성 확인
        if file_ext == '.hwp' and not self.hwp_extractor:
            return False, "HWP 파일 처리 모듈이 초기화되지 않았습니다. Java 설치 및 hwplib 설정을 확인하세요."
        
        return True, "파일 유효성 검사 통과"
    
    def summarize_document(self, text, max_length=300):
        """
        문서 텍스트 요약 (간단한 추출 요약 방식)
        
        Args:
            text: 요약할 텍스트
            max_length: 최대 요약 길이
        
        Returns:
            요약된 텍스트
        """
        if not text:
            return "요약할 텍스트가 없습니다."
            
        try:
            # 문장 분리
            sentences = text.split('.')
            sentences = [s.strip() + '.' for s in sentences if s.strip()]
            
            # 너무 짧은 문장 필터링
            sentences = [s for s in sentences if len(s) > 10]
            
            # 문서가 이미 짧은 경우
            if len(sentences) <= 3:
                return text
                
            # 첫 문장과 마지막 문장은 중요한 정보를 담고 있을 가능성이 높음
            summary = sentences[0] + ' '
            
            # 중간 문장 중에서 일부 선택 (길이 기준)
            middle_sentences = sentences[1:-1]
            
            # 문서 길이에 따라 요약 문장 수 조정
            num_sentences = min(3, len(middle_sentences))
            
            # 길이 기준으로 정렬하여 중요한 문장 선택 (길이가 긴 문장이 더 많은 정보 포함)
            middle_sentences.sort(key=len, reverse=True)
            
            for i in range(num_sentences):
                if i < len(middle_sentences):
                    summary += middle_sentences[i] + ' '
            
            # 마지막 문장 추가
            if len(sentences) > 1:
                summary += sentences[-1]
                
            # 최대 길이 제한
            if len(summary) > max_length:
                summary = summary[:max_length] + '...'
                
            return summary
            
        except Exception as e:
            logger.error(f"요약 생성 중 오류: {e}")
            return "요약 생성 중 오류가 발생했습니다."
    
    def process_document(self, file_path):
        """
        문서 처리 및 요약 통합 기능
        
        Args:
            file_path: 처리할 파일 경로
            
        Returns:
            (text, summary): 원본 텍스트와 요약 텍스트
        """
        # 파일 유효성 검사
        is_valid, message = self.validate_file(file_path)
        if not is_valid:
            return "", message
            
        # 텍스트 추출
        text, metadata = self.extract_text(file_path)
        if not text or len(text.strip()) == 0:
            return "", "텍스트 추출에 실패했습니다."
            
        # 요약 생성
        summary = self.summarize_document(text)
        
        return text, summary
        
    def list_documents(self):
        """문서 디렉토리의 모든 문서 목록 반환"""
        try:
            return [f for f in os.listdir(self.documents_path) if f.lower().endswith(('.hwp', '.pdf'))]
        except Exception as e:
            logger.error(f"문서 목록 조회 오류: {e}")
            return []
            
    def delete_document(self, filename, vector_store=None):
        """문서 디렉토리 및 벡터 저장소에서 문서 삭제"""
        try:
            file_path = Path(self.documents_path) / filename
            deleted = False
            
            # 파일 시스템에서 삭제
            if file_path.exists():
                os.remove(file_path)
                logger.info(f"파일 {filename}이(가) 파일 시스템에서 삭제됨")
                deleted = True
                
                # 벡터 DB에서도 삭제 (벡터 스토어가 제공된 경우)
                if vector_store:
                    try:
                        success = vector_store.delete_document(filename)
                        if success:
                            logger.info(f"문서 {filename}이(가) 벡터 저장소에서 삭제됨")
                        else:
                            logger.warning(f"문서 {filename}을(를) 벡터 저장소에서 삭제하지 못함")
                    except Exception as e:
                        logger.error(f"벡터 저장소에서 문서 삭제 오류: {e}")
            
            return deleted
        except Exception as e:
            logger.error(f"문서 삭제 오류: {e}")
            return False
            
    def get_document_path(self, filename):
        """문서의 전체 경로 반환"""
        return str(Path(self.documents_path) / filename)
        
    def file_exists(self, filename):
        """
        문서 디렉토리에 특정 파일이 존재하는지 확인
        
        Args:
            filename: 확인할 파일 이름
            
        Returns:
            bool: 파일 존재 여부
        """
        try:
            file_path = Path(self.documents_path) / filename
            return file_path.exists()
        except Exception as e:
            logger.error(f"파일 존재 여부 확인 중 오류: {e}")
            return False 