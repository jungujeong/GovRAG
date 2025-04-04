#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import jpype
import jpype.imports
from jpype.types import *

def extract_text_from_hwp(hwp_jar_path, file_path):
    """
    HWP 파일에서 텍스트를 추출
    
    Args:
        hwp_jar_path: hwplib JAR 파일 경로
        file_path: HWP 파일 경로
        
    Returns:
        추출된 텍스트
    """
    try:
        # JVM 시작
        if not jpype.isJVMStarted():
            jpype.startJVM(
                jpype.getDefaultJVMPath(), 
                "-Djava.class.path=" + hwp_jar_path,
                convertStrings=True
            )
        
        # Java 클래스 import
        from kr.dogfoot.hwplib.reader import HWPReader
        from kr.dogfoot.hwplib.tool.textextractor import TextExtractor
        from kr.dogfoot.hwplib.tool.textextractor import TextExtractOption
        
        # HWP 파일 로드
        hwpFile = HWPReader.fromFile(file_path)
        
        # 기본 TextExtractOption 사용
        option = TextExtractOption()
        
        # 텍스트 추출
        text = TextExtractor.extract(hwpFile, option)
        
        # JVM 종료
        if jpype.isJVMStarted():
            jpype.shutdownJVM()
            
        return text
        
    except Exception as e:
        print(f"오류 발생: {e}", file=sys.stderr)
        if jpype.isJVMStarted():
            jpype.shutdownJVM()
        return ""

def main():
    # 명령줄 인자 파싱
    parser = argparse.ArgumentParser(description='HWP 파일에서 텍스트 추출')
    parser.add_argument('--hwp_jar_path', required=True, help='hwplib JAR 파일 경로')
    parser.add_argument('--file_path', required=True, help='HWP 파일 경로')
    
    args = parser.parse_args()
    
    # 파일 경로 검증
    if not os.path.exists(args.hwp_jar_path):
        print(f"JAR 파일을 찾을 수 없습니다: {args.hwp_jar_path}", file=sys.stderr)
        sys.exit(1)
        
    if not os.path.exists(args.file_path):
        print(f"HWP 파일을 찾을 수 없습니다: {args.file_path}", file=sys.stderr)
        sys.exit(1)
    
    # 텍스트 추출 및 출력
    text = extract_text_from_hwp(args.hwp_jar_path, args.file_path)
    print(text)

if __name__ == "__main__":
    main() 