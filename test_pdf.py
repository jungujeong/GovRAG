import os
import sys
from pathlib import Path
import logging

from utils.document_processor import DocumentProcessor
from config import DOCUMENTS_PATH, logger

# 로그 레벨 설정
logger.setLevel(logging.DEBUG)

# 콘솔 핸들러 추가
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def main():
    # DocumentProcessor 초기화
    doc_processor = DocumentProcessor()
    
    # documents 디렉토리에서 PDF 파일 찾기
    documents_path = Path(DOCUMENTS_PATH)
    pdf_files = [f for f in os.listdir(documents_path) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print("PDF 파일을 찾을 수 없습니다. 먼저 PDF 파일을 업로드하세요.")
        return
    
    print(f"발견된 PDF 파일: {pdf_files}")
    
    # 첫 번째 PDF 파일 처리
    pdf_file = pdf_files[0]
    pdf_path = documents_path / pdf_file
    
    print(f"\n\n===== {pdf_file} 처리 시작 =====")
    
    try:
        # PDF에서 텍스트 추출
        text, metadata = doc_processor.extract_text(str(pdf_path))
        
        # 결과 확인
        print(f"\n추출된 메타데이터: {metadata}")
        print(f"\n추출된 텍스트 길이: {len(text)} 자")
        print(f"\n추출된 텍스트 샘플 (처음 500자):\n{text[:500]}...")
        
    except Exception as e:
        print(f"PDF 처리 중 오류 발생: {e}")

if __name__ == "__main__":
    main() 