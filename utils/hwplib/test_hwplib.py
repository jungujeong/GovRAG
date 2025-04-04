#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import logging
import time
from hwp_linux import HwpLinuxExtractor

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='hwplib를 사용하여 HWP 파일 텍스트 추출 테스트')
    parser.add_argument('--file_path', required=True, help='테스트할 HWP 파일 경로')
    parser.add_argument('--jar_path', help='hwplib JAR 파일 경로 (선택 사항)')
    
    args = parser.parse_args()
    
    # 파일 경로 검증
    if not os.path.exists(args.file_path):
        logger.error(f"HWP 파일을 찾을 수 없습니다: {args.file_path}")
        sys.exit(1)
    
    try:
        # HwpLinuxExtractor 인스턴스 생성
        hwp_extractor = HwpLinuxExtractor(args.jar_path) if args.jar_path else HwpLinuxExtractor()
        
        # 텍스트 추출
        start_time = time.time()
        logger.info(f"텍스트 추출 시작: {args.file_path}")
        
        text = hwp_extractor.extract_text(args.file_path)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # 결과 보고
        if text and len(text.strip()) > 0:
            logger.info(f"텍스트 추출 성공 (처리 시간: {elapsed_time:.2f}초)")
            print(f"추출된 텍스트 길이: {len(text)} 자")
            print("\n====== 추출된 텍스트 샘플(처음 500자) ======\n")
            print(text[:500] + "...\n" if len(text) > 500 else text)
            print("=====================================")
        else:
            logger.error("텍스트 추출 실패: 추출된 텍스트가 비어있습니다.")
            
        # JVM 종료
        hwp_extractor.shutdown()
        
    except Exception as e:
        logger.error(f"오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 