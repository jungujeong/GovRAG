#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
구청장 지시사항 PDF → RAG 적재용 JSONL 변환 (v2)
- 헤더/풋터 완전 제거
- 중복 제거
- 문맥 복원 (안전한 범위)
- 부서명 토막 복원
"""

import os
import re
import glob
import json
import argparse
import fitz  # PyMuPDF
from itertools import zip_longest
from typing import List, Dict, Set, Tuple

# ============================ 유틸 ============================

def read_dept_list(path: str) -> List[str]:
    """부서 화이트리스트 파일 읽기"""
    if not os.path.exists(path):
        print(f"Warning: 부서 리스트 파일이 없습니다: {path}")
        # 기본 부서 리스트
        return [
            "경제일자리과", "전부서", "전 부서", "토지정보과", "건축과", "문화예술과",
            "관광진흥과", "총무과", "안전총괄과", "교통행정과", "주차관리과",
            "자원순환과", "평생교육과", "민원여권과", "산림녹지과", "시설관리사업소",
            "전략사업과", "기획조정실", "감사실", "행정지원국", "복지환경국",
            "안전도시국", "미래성장국", "보건소", "의회사무국", "재무과", "세무과",
            "홍보담당관", "일자리경제과", "문화체육과", "교육정책과", "복지정책과",
            "어르신장애인과", "가족정책과", "청소행정과", "환경위생과", "공원녹지과",
            "건설과", "도시재생과", "스마트도시과", "전 동", "초량동", "수정동",
            "좌천동", "범일동", "부전동"
        ]
    
    out, seen = [], set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out

def normalize_key(text: str) -> str:
    """중복 검사용 키 생성 (첫 50자, 공백/구두점 정규화)"""
    # ○ 이후 50자만 추출
    if '○' in text:
        text = text[text.index('○'):]
    text = text[:50]
    # 공백 정규화
    text = re.sub(r'\s+', ' ', text)
    # 구두점 중복 제거
    text = re.sub(r'[,]+', ',', text)
    text = re.sub(r'[.]+', '.', text)
    return text.strip()

def is_header_line(line: str) -> bool:
    """표 헤더/캡션 라인 여부 판단"""
    # 헤더 키워드들
    header_keywords = [
        r'일\s*련', r'처\s*리', r'지\s*시\s*사\s*항', 
        r'기\s*한', r'주\s*관\s*부\s*서', r'관\s*련\s*부\s*서',
        r'훈\s*시', r'󰏅', r'번\s*호', r'구\s*분'
    ]
    
    # 여러 키워드가 한 줄에 있으면 헤더
    pattern = r'(?:' + '|'.join(header_keywords) + r')'
    matches = re.findall(pattern, line)
    if len(matches) >= 2:  # 2개 이상 키워드가 있으면 헤더
        return True
    
    # 단독 헤더 패턴
    if re.match(r'^\s*(?:훈시|보고|계속)\s*(?:󰏅|$)', line):
        return True
    
    return False

def clean_text_context(text: str, dept_whitelist: List[str] = None) -> str:
    """
    문맥 복원: 줄바꿈 병합, 구두점 정리, 숫자-단위 처리
    """
    # 1. 헤더 라인 제거
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        if not is_header_line(line):
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    
    # 1-1. 토막난 부서명 패턴을 찾아 제거
    # 패턴: 한글 단일 글자가 공백으로 분리된 형태 (2개 이상)
    if dept_whitelist:
        # 토막난 패턴 찾기 및 복원
        pattern = r'(?:[가-힣]\s+){2,}[가-힣](?:\s+[가-힣]\s+[가-힣])*'
        
        def check_dept_pattern(match):
            # 토막난 텍스트를 복원
            fragmented = match.group(0)
            restored = re.sub(r'\s+', '', fragmented)
            
            # 부서명 화이트리스트에 있거나 "과", "부", "실", "동"으로 끝나면 제거
            for dept in dept_whitelist:
                if dept.replace(' ', '') == restored or restored in dept:
                    return ''  # 부서명이므로 제거
            
            # 일반적인 부서 패턴
            if restored.endswith(('과', '부', '실', '동', '센터', '관')):
                return ''  # 부서명이므로 제거
            
            return match.group(0)  # 부서명이 아니면 유지
        
        text = re.sub(pattern, check_dept_pattern, text)
    
    # 2. 문장부호 뒤 개행만 유지, 나머지는 공백으로
    lines = text.split('\n')
    merged_lines = []
    buffer = ""
    
    for line in lines:
        line = line.strip()
        if not line:
            if buffer:
                merged_lines.append(buffer)
                buffer = ""
            continue
        
        if buffer:
            # 이전 줄이 문장부호로 끝났는지 확인
            if re.search(r'[.?!다]\s*$', buffer):
                merged_lines.append(buffer)
                buffer = line
            else:
                # 공백으로 연결
                buffer = buffer + " " + line
        else:
            buffer = line
    
    if buffer:
        merged_lines.append(buffer)
    
    text = '\n'.join(merged_lines)
    
    # 3. 중복/연속 구두점 정리
    text = re.sub(r',+', ',', text)
    text = re.sub(r'\.+', '.', text)
    text = re.sub(r'·\s*,', '·', text)
    text = re.sub(r',\s*·', '·', text)
    
    # 4. 빈 괄호 제거
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'\[\s*\]', '', text)
    
    # 5. 날짜/단위 안전한 결합
    text = re.sub(r'(\d+)\s+월\s+경', r'\1월경', text)
    text = re.sub(r'(\d+)\s+월', r'\1월', text)
    text = re.sub(r'(\d+)\s+일', r'\1일', text)
    text = re.sub(r'(\d+)\s+명', r'\1명', text)
    text = re.sub(r'(\d+)\s+%', r'\1%', text)
    text = re.sub(r'제\s+(\d+)\s+회', r'제\1회', text)
    text = re.sub(r'(\d+)\s+차', r'\1차', text)
    text = re.sub(r'(\d+)\s+년', r'\1년', text)
    
    # 6. 한글-숫자 안전 분리 (제외: 제N회 패턴)
    # 한글 뒤 숫자
    text = re.sub(r'(?<!제)([가-힣])(\d+)', r'\1 \2', text)
    # 숫자 뒤 한글 (단위 제외)
    text = re.sub(r'(\d+)(?![월일년회명%차])([가-힣])', r'\1 \2', text)
    
    # 7. 연속 공백 정리
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def restore_dept_names(text: str, dept_whitelist: List[str]) -> str:
    """부서명 토막 복원"""
    # 토막난 부서명 패턴 찾기 (예: "전 부 서", "건 설 과")
    # 한글 단일 글자가 공백으로 분리된 패턴
    pattern = r'(?:[가-힣]\s+){2,}[가-힣]'
    
    def restore_candidate(match):
        candidate = match.group(0)
        # 공백 제거
        restored = re.sub(r'\s+', '', candidate)
        # 화이트리스트에 있으면 복원
        if restored in dept_whitelist:
            return restored
        # 부분 일치 확인 (예: "전부서" -> "전 부서")
        for dept in dept_whitelist:
            if dept.replace(' ', '') == restored:
                return dept
        return candidate  # 원본 유지
    
    text = re.sub(pattern, restore_candidate, text)
    return text

# ===================== 열 경계 탐지 =====================

def get_words(page):
    """페이지에서 단어 위치 정보 추출"""
    return [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words", sort=True)]

def find_header_columns(page, y_top=0, y_bottom=250) -> List[float]:
    """첫 페이지에서 표 헤더를 찾고 열 경계 추출"""
    words = get_words(page)
    if not words:
        return None
    
    # 상단 영역에서 헤더 찾기
    header_words = [w for w in words if y_top <= w[1] <= y_bottom]
    if not header_words:
        # 기본 5열 분할
        w = page.rect.width
        return [-1e9] + [w * i / 5.0 for i in range(1, 5)] + [1e9]
    
    # 헤더 키워드 포함 라인 찾기
    header_keywords = ['일련', '처리', '지시', '기한', '주관', '관련']
    
    # y 좌표로 라인 그룹핑
    lines = {}
    for x0, y0, x1, y1, text in header_words:
        y_key = round(y0 / 5) * 5  # 5pt 단위로 그룹핑
        if y_key not in lines:
            lines[y_key] = []
        lines[y_key].append((x0, x1, text))
    
    # 헤더 키워드가 가장 많은 라인 찾기
    best_line = None
    best_score = 0
    
    for y_key, words_in_line in lines.items():
        line_text = ' '.join(w[2] for w in words_in_line)
        score = sum(1 for kw in header_keywords if kw in line_text)
        if score > best_score:
            best_score = score
            best_line = words_in_line
    
    if not best_line or best_score < 2:
        # 기본 5열 분할
        w = page.rect.width
        return [-1e9] + [w * i / 5.0 for i in range(1, 5)] + [1e9]
    
    # x 좌표 기준으로 열 경계 계산
    x_positions = []
    for x0, x1, _ in best_line:
        x_positions.append(x0)
        x_positions.append(x1)
    x_positions.sort()
    
    # 간격이 큰 곳을 열 경계로
    gaps = []
    for i in range(1, len(x_positions)):
        gap = x_positions[i] - x_positions[i-1]
        if gap > 20:  # 20pt 이상 간격
            gaps.append((gap, (x_positions[i-1] + x_positions[i]) / 2))
    
    gaps.sort(reverse=True)
    
    # 상위 간격들을 열 경계로
    edges = [-1e9]
    for _, edge in gaps[:4]:  # 최대 4개 경계
        edges.append(edge)
    edges.append(1e9)
    edges.sort()
    
    if len(edges) < 5:  # 최소 5개 (4개 열)
        w = page.rect.width
        return [-1e9] + [w * i / 5.0 for i in range(1, 5)] + [1e9]
    
    return edges

def extract_departments_from_last_col(page, col_edges, dept_whitelist) -> List[List[str]]:
    """마지막 열에서 부서명 추출"""
    if not col_edges:
        return []
    
    words = get_words(page)
    if not words:
        return []
    
    # 마지막 열 영역의 단어들만 추출
    last_col_start = col_edges[-2]
    last_col_end = col_edges[-1]
    
    # y 좌표로 행 그룹핑
    rows = {}
    for x0, y0, x1, y1, text in words:
        x_center = (x0 + x1) / 2
        if last_col_start <= x_center < last_col_end:
            y_key = round(y0 / 10) * 10  # 10pt 단위로 그룹핑
            if y_key not in rows:
                rows[y_key] = []
            rows[y_key].append(text)
    
    # 각 행에서 부서명 찾기
    found_depts = []
    for y_key in sorted(rows.keys()):
        row_text = ' '.join(rows[y_key])
        # 토막난 부서명 복원
        row_text = restore_dept_names(row_text, dept_whitelist)
        
        # 부서명 추출
        depts = []
        for dept in dept_whitelist:
            if dept in row_text and dept not in depts:
                depts.append(dept)
        
        if depts:
            found_depts.append(depts)
    
    return found_depts

# ====================== 지시사항 추출 ======================

def extract_directives_from_page(page_text: str, seen_directives: Set[str], dept_whitelist: List[str]) -> List[str]:
    """
    페이지에서 지시사항 추출 (중복 제거 포함)
    """
    # 헤더 라인 제거
    lines = page_text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        if not is_header_line(line.strip()):
            cleaned_lines.append(line)
    
    text = '\n'.join(cleaned_lines)
    
    # ○로 시작하는 블록 분리
    blocks = re.split(r'(?=^\s*○)', text, flags=re.M)
    
    directives = []
    for block in blocks:
        block = block.strip()
        if not block or not block.startswith('○'):
            continue
        
        # 문맥 복원
        cleaned = clean_text_context(block, dept_whitelist)
        
        # 중복 체크
        key = normalize_key(cleaned)
        if key in seen_directives:
            continue
        seen_directives.add(key)
        
        # 최소 길이 체크 (너무 짧은 것은 헤더 잔여물일 가능성)
        if len(cleaned) > 20:
            directives.append(cleaned)
    
    return directives

# ====================== 메인 파이프라인 ======================

def process_pdf_to_jsonl(pdf_path: str, out_jsonl: str, dept_whitelist: List[str]):
    """PDF 파일을 처리하여 JSONL 형식으로 출력"""
    doc = fitz.open(pdf_path)
    if len(doc) == 0:
        return
    
    # 첫 페이지에서 열 경계 고정
    col_edges = find_header_columns(doc[0])
    
    # 중복 제거를 위한 세트
    seen_directives = set()
    
    records = []
    
    for pidx, page in enumerate(doc, start=1):
        # 1) 지시사항 추출
        text = page.get_text("text")
        directives = extract_directives_from_page(text, seen_directives, dept_whitelist)
        
        # 2) 부서 추출
        page_depts = extract_departments_from_last_col(page, col_edges, dept_whitelist)
        
        # 3) 순서 매칭
        for idx, (directive, depts) in enumerate(zip_longest(directives, page_depts, fillvalue=[]), start=1):
            if not directive:
                continue  # 지시사항이 없으면 스킵
            
            rec = {
                "source_file": os.path.basename(pdf_path),
                "page": pidx,
                "index": idx,
                "directive": directive,
                "departments": depts if isinstance(depts, list) else [],
                "lang": "ko",
                "doc_type": "gucheong_jisisa"
            }
            records.append(rec)
    
    # JSONL로 저장
    with open(out_jsonl, "w", encoding="utf-8") as out:
        for rec in records:
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    
    return len(records)

def run(pdf_glob: str, out_dir: str, dept_list_path: str):
    """메인 실행 함수"""
    os.makedirs(out_dir, exist_ok=True)
    whitelist = read_dept_list(dept_list_path)
    
    pdf_files = glob.glob(pdf_glob)
    print(f"Found {len(pdf_files)} PDF files")
    
    total_records = 0
    for path in pdf_files:
        if not path.lower().endswith(".pdf"):
            continue
        
        print(f"Processing: {path}")
        base = os.path.splitext(os.path.basename(path))[0]
        out_jsonl = os.path.join(out_dir, base + ".jsonl")
        
        try:
            count = process_pdf_to_jsonl(path, out_jsonl, whitelist)
            print(f"  → Saved {count} records to: {out_jsonl}")
            total_records += count
        except Exception as e:
            print(f"  → Error: {e}")
    
    print(f"\nTotal: {total_records} records extracted")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="구청장 지시사항 PDF를 JSONL로 변환 (v2)")
    ap.add_argument("--pdf_glob", required=True,
                   help="PDF 파일 glob 패턴")
    ap.add_argument("--out_dir", required=True,
                   help="출력 디렉터리")
    ap.add_argument("--dept_list", required=False, default="",
                   help="부서 화이트리스트 파일 (옵션)")
    args = ap.parse_args()
    
    run(args.pdf_glob, args.out_dir, args.dept_list)