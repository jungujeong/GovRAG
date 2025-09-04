#!/bin/bash
# 구청장 지시사항 PDF를 JSONL로 변환하는 스크립트

# 기본 경로 설정
PDF_DIR="data/documents"
OUTPUT_DIR="data/extracted_directives"
DEPT_LIST="data/dept_whitelist.txt"

# 인자로 경로 받기 (옵션)
if [ $# -ge 1 ]; then
    PDF_DIR="$1"
fi
if [ $# -ge 2 ]; then
    OUTPUT_DIR="$2"
fi
if [ $# -ge 3 ]; then
    DEPT_LIST="$3"
fi

echo "======================================"
echo "구청장 지시사항 PDF → JSONL 변환"
echo "======================================"
echo "PDF 디렉터리: $PDF_DIR"
echo "출력 디렉터리: $OUTPUT_DIR"
echo "부서 리스트: $DEPT_LIST"
echo ""

# 실행
python3 processors/directive_extractor.py \
    --pdf_glob "${PDF_DIR}/*구청장*지시사항*.pdf" \
    --out_dir "$OUTPUT_DIR" \
    --dept_list "$DEPT_LIST"

echo ""
echo "완료! 결과 확인:"
echo "ls -la $OUTPUT_DIR/"