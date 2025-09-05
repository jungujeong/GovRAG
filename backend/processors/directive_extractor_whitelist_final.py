#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
구청장 지시/훈시/보고 PDF → 화이트리스트 기반 부서 추출 시스템 (최종 완성판)

핵심 개선사항:
- KNOWN_DEPARTMENTS 화이트리스트로 정확한 부서만 추출
- 제목 끝 부서명 자동 제거 및 별도 수집
- 부서열에서 n-gram 조합으로 분리된 부서명 재조립 ("시설관"+"리사업소"→"시설관리사업소")
- 안전한 좌표 경계: 본문(last_col_start-12pt), 부서열(last_col_start+6pt)
- 헤더 키워드 강력 필터링 및 단위 테스트 포함

안전 경계값 설정 이유:
- MAIN_BOUNDARY_OFFSET = -12pt : 부서열과 본문 완전 분리, 여백 충분히 확보
- DEPT_BOUNDARY_OFFSET = +6pt  : 부서열 시작점을 명확히 하여 잡음 단어 최소화
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Any, Set
from itertools import combinations

import fitz  # PyMuPDF

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("directive_whitelist")

# ----------------------- 설정 상수 -----------------------

# 안전 경계값 (상단 주석 참조)
MAIN_BOUNDARY_OFFSET = -12  # 본문 영역: last_col_start + 이 값 이하만 사용
DEPT_BOUNDARY_OFFSET = +6   # 부서열 영역: last_col_start + 이 값 이상만 사용

# 화이트리스트 부서 목록 (사용자 제공)
KNOWN_DEPARTMENTS = {
    # 핵심 부서/국/실
    "총무과","기획예산과","기획조정실","감사실","홍보담당관",
    "행정지원과","행정지원국","안전도시국","미래성장국","복지환경국",

    # 경제/산업/일자리
    "경제일자리과","일자리경제과","산업경제과","투자유치과",

    # 도시·건설·교통
    "도시계획과","도시재생과","도시정비과","도시관리과",
    "건설과","건설관리과","건축과","도로과","하천과",
    "교통행정과","주차관리과","스마트도시과","정보통신과",

    # 안전·재난
    "안전총괄과","재난안전과","민방위과",

    # 환경·청소·공원·자원순환
    "환경위생과","위생환경과","청소행정과","자원순환과",
    "공원녹지과","산림녹지과","환경정책과",

    # 문화·관광·체육·교육
    "문화예술과","문화체육과","관광진흥과","체육지원과",
    "평생교육과","교육정책과","평생학습과","문화관광과",

    # 복지·보건
    "복지정책과","사회복지과","어르신장애인과","노인복지과",
    "가족정책과","여성가족과","아동보육과","청년정책과",
    "건강증진과","보건소",

    # 세무·재무·회계·민원
    "세무과","재무과","회계과","민원여권과","민원봉사과",

    # 전략/특수 조직
    "전략사업과","도시재생지원센터","시설관리사업소","의회사무국",

    # 관·센터·단(실제 많이 쓰이는 명칭)
    "청소년상담복지센터","장애인복지관","노인복지관","여성인력개발센터",

    # 전부서/전동(집합 지시용)
    "전부서","전동","전 동","전 부 서",
}

# 헤더/잡음 키워드 (강화)
HEADER_KEYWORDS = re.compile(
    r'(구청장\s*(지시|훈시|보고)\s*사항|일\s*련|처\s*리|지\s*시|기\s*한|주\s*관|관\s*련|담\s*당|부서(?!\s*$)|처리기한|처리주관|부서기한관|주관부서|관련부서|일련|번호|구분|사항|계속|훈\s*시|보\s*고)',
    re.I
)

NOISE_KEYWORDS = re.compile(
    r'(처리|기한|주관|관련|담당|번호|구분|계속)',
    re.I
)

# 날짜 패턴들
DATE_RX = re.compile(r'(?P<y>2,?0\d{2})\.\s*(?P<m>\d{1,2})\.\s*(?P<d>\d{1,2})\.?')
YEAR_ONLY_RX = re.compile(r'2,?0\d{2}\.')
MONTH_DAY_RX = re.compile(r'\b\d{1,2}\.\s*\d{1,2}\.')
ALL_DATE_PATTERNS = [DATE_RX, YEAR_ONLY_RX, MONTH_DAY_RX]

# ----------------------- 보조 함수 -----------------------

def detect_page_category(raw_text: str) -> str:
    """페이지 카테고리 탐지"""
    head = "\n".join(raw_text.splitlines()[:20])
    if re.search(r'훈\s*시', head): return "훈시"
    if re.search(r'보\s*고', head): return "보고"
    return "지시"

def find_first_circle_y(page) -> float:
    """첫 번째 '○' 위치 탐지"""
    rects = page.search_for("○", quads=False)
    if rects:
        return min(r.y0 for r in rects)
    ys = []
    for w in page.get_text("words", sort=True):
        if len(w) >= 5 and "○" in (w[4] or ""):
            ys.append(w[1])
    return min(ys) if ys else -1.0

def detect_column_edges(page) -> Tuple[List[float], float]:
    """열 경계 감지 및 마지막 열 시작점 반환"""
    words = page.get_text("words", sort=True)
    if not words:
        w = page.rect.width
        edges = [w*i/5 for i in range(6)]
        return edges, edges[-2]

    h = page.rect.height
    header_words = [w for w in words if w[1] < h*0.2]
    if not header_words:
        header_words = words[:60]

    centers = sorted(((w[0]+w[2])/2) for w in header_words)
    gaps = []
    for i in range(1, len(centers)):
        gap = centers[i] - centers[i-1]
        if gap > 30:
            gaps.append((gap, (centers[i-1]+centers[i])/2))

    if gaps:
        gaps.sort(reverse=True)
        boundaries = [x for _, x in gaps[:5]]
        edges = [0.0] + sorted(boundaries) + [page.rect.width]
    else:
        w = page.rect.width
        edges = [w*i/5 for i in range(6)]

    last_col_start = edges[-2] if len(edges) >= 2 else page.rect.width*0.8
    return edges, last_col_start

# ----------------------- 제목에서 부서 추출 -----------------------

def normalize_spacing_for_departments(text: str) -> str:
    """부서 관련 띄어쓰기 정규화"""
    text = re.sub(r'전\s*부\s*서', '전부서', text)
    text = re.sub(r'전\s*동', '전동', text)
    return text

def strip_trailing_departments_from_title(title: str, known_depts: Set[str]) -> Tuple[str, List[str]]:
    """
    제목 끝에서 화이트리스트 기반 부서명 추출 및 제거
    반환: (정제된_제목, 추출된_부서_리스트)
    """
    # 1) 띄어쓰기 정규화
    normalized = normalize_spacing_for_departments(title)
    
    extracted_depts = []
    cleaned_title = normalized
    
    # 2) 오른쪽 끝에서 부서명 반복 제거
    max_iterations = 10
    for _ in range(max_iterations):
        found_dept = None
        longest_match = 0
        
        # 화이트리스트의 모든 부서명을 체크 (긴 것부터)
        for dept in sorted(known_depts, key=len, reverse=True):
            # 제목 끝에 이 부서가 있는지 확인 (앞뒤 공백 포함 가능)
            pattern = rf'\s*{re.escape(dept)}\s*$'
            if re.search(pattern, cleaned_title, re.I):
                if len(dept) > longest_match:
                    found_dept = dept
                    longest_match = len(dept)
        
        if not found_dept:
            break
            
        # 가장 긴 매칭 부서를 제거
        pattern = rf'\s*{re.escape(found_dept)}\s*$'
        cleaned_title = re.sub(pattern, '', cleaned_title, flags=re.I).strip()
        extracted_depts.append(found_dept)
    
    # 추출 순서 뒤집기 (오른쪽부터 추출했으므로)
    extracted_depts.reverse()
    
    return cleaned_title, extracted_depts

# ----------------------- 본문 라인 재구성 -----------------------

def rebuild_main_content_lines(page, cut_y: float, last_col_start: float) -> List[Tuple[float, str]]:
    """
    본문 영역만 라인 재구성 (부서열 완전 배제)
    안전 경계: last_col_start + MAIN_BOUNDARY_OFFSET 이하만 사용
    """
    words = page.get_text("words", sort=True)
    if not words:
        return []
    
    main_boundary = last_col_start + MAIN_BOUNDARY_OFFSET
    
    # 본문 영역 words만 수집
    buf = []
    for w in words:
        if len(w) < 5: 
            continue
        x0, y0, x1, y1, t = w[:5]
        
        # 헤더 컷
        if cut_y > 0 and y0 < cut_y - 1.5:
            continue
            
        # 본문 영역만 (부서열 완전 배제)
        if x1 > main_boundary:
            continue
            
        t = (t or "").strip()
        if not t: 
            continue
        buf.append((x0, y0, x1, y1, t))

    if not buf: 
        return []

    # y 기준 정렬 후 라인 클러스터링
    buf.sort(key=lambda z: (round(z[1], 1), z[0]))
    lines_words, cur = [], [buf[0]]
    
    for w in buf[1:]:
        if abs(w[1] - cur[-1][1]) <= 3.5:
            cur.append(w)
        else:
            lines_words.append(cur)
            cur = [w]
    lines_words.append(cur)

    # 각 라인을 x 정렬하여 텍스트 생성
    lines = []
    for line in lines_words:
        line.sort(key=lambda z: z[0])
        y0 = min(z[1] for z in line)
        text = " ".join(z[4] for z in line)
        lines.append((y0, text))

    # 헤더성 라인 및 구분선 제거
    filtered = []
    for y, s in lines:
        st = s.strip()
        if not st: 
            continue
        if HEADER_KEYWORDS.search(st) and not st.lstrip().startswith("○"):
            continue
        if re.match(r'^[│┃┌┐└┘├┤┬┴┼─━\s]+$', st):  # 표 구분선
            continue
        if re.match(r'^\s*-?\s*\d{1,3}\s*-?\s*$', st):  # 페이지 번호
            continue
        filtered.append((y, st))

    # 라인 중복 제거
    seen, uniq = set(), []
    for y, st in filtered:
        key = (re.sub(r'\s+', ' ', st), round(y, 1))
        if key in seen: 
            continue
        seen.add(key)
        uniq.append((y, st))

    # 첫 번째 '○' 라인 이전 추가 제거
    bullet_ys = [y for y, s in uniq if s.lstrip().startswith("○")]
    if bullet_ys:
        cut2 = min(bullet_ys) - 1.5
        uniq = [(y, s) for y, s in uniq if y >= cut2]

    return uniq

# ----------------------- Y축 기반 블록-부서 매칭 시스템 -----------------------

def build_blocks_with_y_ranges(page, last_col_start: float) -> List[Dict]:
    """
    반환: [{'text': block_text, 'y_top': float, 'y_bottom': float}]
    - 본문열(x1 <= last_col_start - margin)만 사용해 블록 y범위 계산
    - 블록 경계는 '○' 토큰을 기준으로 words를 그룹화
    """
    words = page.get_text("words", sort=True)  # (x0,y0,x1,y1,txt, ...)
    if not words: 
        return []

    main_max_x = last_col_start + MAIN_BOUNDARY_OFFSET
    
    # 본문영역 단어만 추려서 ○ 기준으로 그룹핑
    main_words = []
    for w in words:
        if len(w) < 5:
            continue
        x0, y0, x1, y1, txt = w[:5]
        if x1 <= main_max_x and txt and txt.strip():
            main_words.append((x0, y0, x1, y1, txt.strip()))
    
    if not main_words:
        return []

    # '○' 토큰의 시작 인덱스 수집
    bullet_indices = []
    for i, w in enumerate(main_words):
        if "○" in w[4]:
            bullet_indices.append(i)
    
    if not bullet_indices:
        return []

    # 블록별 그룹 생성
    blocks = []
    for j, start in enumerate(bullet_indices):
        end = bullet_indices[j+1] if j+1 < len(bullet_indices) else len(main_words)
        
        chunk = main_words[start:end]
        if not chunk:
            continue
            
        # 텍스트 구성 (y축 정렬 후 x축 정렬)
        chunk_by_lines = {}
        for w in chunk:
            y_key = round(w[1], 1)  # y 좌표를 키로 사용
            if y_key not in chunk_by_lines:
                chunk_by_lines[y_key] = []
            chunk_by_lines[y_key].append(w)
        
        # 라인별로 x 정렬하여 텍스트 생성
        sorted_lines = []
        for y_key in sorted(chunk_by_lines.keys()):
            line_words = sorted(chunk_by_lines[y_key], key=lambda w: w[0])
            line_text = " ".join(w[4] for w in line_words)
            sorted_lines.append(line_text)
        
        chunk_text = "\n".join(sorted_lines)
        
        # 세로 범위 계산
        y_top = min(w[1] for w in chunk)
        y_bottom = max(w[3] for w in chunk)

        blocks.append({
            "text": chunk_text,
            "y_top": y_top,
            "y_bottom": y_bottom,
        })
    
    return blocks

def extract_dept_rows(page, last_col_start: float, known_departments: Set[str]) -> List[Dict]:
    """
    반환: [{'y_center': float, 'raw': '원시행텍스트', 'depts': ['시설관리사업소','관광진흥과', ...]}]
    - last_col_start + margin 보다 x중심이 큰 단어만 수집하여 y기반 행으로 묶음
    - 토큰을 1/2/3-gram으로 결합 → KNOWN_DEPARTMENTS 교차
    - 헤더/잡음 라인은 버림
    """
    words = page.get_text("words", sort=True)
    if not words:
        return []

    dept_min_x = last_col_start + DEPT_BOUNDARY_OFFSET
    
    # 마지막 열 후보 단어 수집
    dept_candidates = []
    for w in words:
        if len(w) < 5: 
            continue
        x0, y0, x1, y1, txt = w[:5]
        if not txt or not txt.strip():
            continue
        x_center = (x0 + x1) / 2.0
        if x_center >= dept_min_x:
            dept_candidates.append((x0, y0, x1, y1, txt.strip()))

    if not dept_candidates:
        return []

    # y로 정렬 후 같은 줄 클러스터링 (±8pt)
    dept_candidates.sort(key=lambda z: z[1])
    rows, current_row = [], [dept_candidates[0]]
    
    for candidate in dept_candidates[1:]:
        if abs(candidate[1] - current_row[-1][1]) <= 8.0:
            current_row.append(candidate)
        else:
            rows.append(current_row)
            current_row = [candidate]
    rows.append(current_row)

    # 행 단위로 텍스트 만들고 부서 후보 생성
    result = []
    for row in rows:
        row.sort(key=lambda z: z[0])  # x 정렬
        y_center = sum((z[1] + z[3]) / 2.0 for z in row) / len(row)

        raw_text = " ".join(z[4] for z in row)
        
        # 헤더/잡음 차단
        if NOISE_KEYWORDS.search(raw_text):
            result.append({"y_center": y_center, "raw": raw_text, "depts": []})
            continue

        # 콤마/구분자 정리 + 전부서/전동 정규화
        cleaned = re.sub(r'[,\u00B7·/]+', ' ', raw_text)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = normalize_spacing_for_departments(cleaned).strip()

        # 토큰 나눔 후 1~3그램 후보 생성 → 화이트리스트 교차
        tokens = cleaned.split()
        candidate_names = set()

        # 1-gram 매칭
        for token in tokens:
            if token in known_departments:
                candidate_names.add(token)

        # 2-gram, 3-gram (공백 제거 결합)
        for n in (2, 3):
            for i in range(len(tokens) - n + 1):
                name = "".join(tokens[i:i+n])
                if name in known_departments:
                    candidate_names.add(name)

        # 원문 순서대로 정렬
        final_depts = []
        for dept in candidate_names:
            if dept not in final_depts:
                final_depts.append(dept)
        
        result.append({
            "y_center": y_center,
            "raw": raw_text,
            "depts": final_depts
        })

    return result

def find_departments_from_tokens(tokens: List[str], known_depts: Set[str]) -> List[str]:
    """
    토큰 리스트에서 n-gram 조합을 통해 화이트리스트 부서 찾기
    예: ["시설관", "리사업소"] → "시설관리사업소"
    """
    found = []
    used_indices = set()
    
    # 길이 순으로 정렬된 부서명들 (긴 것부터 매칭)
    sorted_depts = sorted(known_depts, key=len, reverse=True)
    
    for dept in sorted_depts:
        # 1-gram 직접 매칭
        for i, token in enumerate(tokens):
            if i in used_indices:
                continue
            if token.lower() == dept.lower():
                found.append(dept)
                used_indices.add(i)
                break
        else:
            # n-gram 조합 매칭 (2~4-gram)
            for n in range(2, min(5, len(tokens) + 1)):
                for combo_indices in combinations(range(len(tokens)), n):
                    if any(i in used_indices for i in combo_indices):
                        continue
                    
                    combined = "".join(tokens[i] for i in combo_indices)
                    if combined.lower() == dept.lower():
                        found.append(dept)
                        used_indices.update(combo_indices)
                        break
                if dept in found:
                    break
    
    return found

# ----------------------- 텍스트 처리 -----------------------

def minimal_text_cleanup(text: str) -> str:
    """최소한의 텍스트 정제 (의미 변경 방지)"""
    # 기본 단위 결합
    text = re.sub(r'(\d+)\s*월', r'\1월', text)
    text = re.sub(r'(\d+)\s*일', r'\1일', text)
    text = re.sub(r'(\d+)\s*%', r'\1%', text)
    text = re.sub(r'제\s*(\d+)\s*회', r'제\1회', text)
    
    # 부서 띄어쓰기 정규화
    text = normalize_spacing_for_departments(text)
    
    # 중복 구두점 축소
    text = re.sub(r',,+', ',', text)
    text = re.sub(r'\.\.+', '.', text)
    text = re.sub(r'\s{2,}', ' ', text)
    
    return text.strip()

def extract_deadline_from_text(text: str) -> str:
    """날짜 패턴에서 처리기한 추출"""
    m = DATE_RX.search(text)
    if not m: 
        return ""
    
    y, mth, d = m.group('y'), m.group('m'), m.group('d')
    y = y.replace(',', '')
    return f"{int(y)}. {int(mth)}. {int(d)}."

def remove_all_dates_from_text(text: str) -> str:
    """모든 날짜 패턴 제거"""
    cleaned = text
    for pattern in ALL_DATE_PATTERNS:
        cleaned = pattern.sub(' ', cleaned)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    cleaned = re.sub(r'\.{2,}', '.', cleaned)
    return cleaned.strip()

# ----------------------- 블록 처리 -----------------------

def merge_lines_to_text(lines: List[Tuple[float, str]]) -> str:
    """라인들을 자연스러운 텍스트로 병합"""
    if not lines:
        return ""
    
    merged_lines = []
    current_line = ""
    
    for _, text in lines:
        text = text.strip()
        if not text:
            continue
            
        if current_line:
            # 문장 끝이면 개행, 아니면 공백으로 연결
            if re.search(r'[.?!다]\s*$', current_line):
                merged_lines.append(current_line)
                current_line = text
            else:
                current_line += " " + text
        else:
            current_line = text
    
    if current_line:
        merged_lines.append(current_line)
    
    text = "\n".join(merged_lines)
    return minimal_text_cleanup(text)

def split_blocks_by_bullet(text: str) -> List[str]:
    """'○' 기준으로 블록 분리"""
    if not text:
        return []
        
    parts = re.split(r'(?=^\s*○)', text, flags=re.M)
    blocks = []
    
    for part in parts:
        part = part.strip()
        if not part.startswith("○"):
            continue
        if len(part) < 8:
            continue
        blocks.append(part)
    
    return blocks

def process_block_content(block_text: str) -> Tuple[str, str, List[str]]:
    """
    블록에서 제목/본문 분리 및 제목 꼬리 부서 추출
    반환: (제목, 본문, 제목에서_추출된_부서들)
    """
    lines = block_text.splitlines()
    if not lines:
        return "", "", []
    
    # 제목 처리: 첫 줄에서 '○' 제거 후 부서 추출
    title_raw = lines[0].lstrip().lstrip('○').strip()
    clean_title, title_depts = strip_trailing_departments_from_title(title_raw, KNOWN_DEPARTMENTS)
    
    # 본문 처리: 나머지 줄들
    body_lines = [ln.strip() for ln in lines[1:] if ln.strip()]
    body = " ".join(body_lines).strip()
    
    if body:
        # 문장 단위 개행 정리
        body = re.sub(r'\s*([.?!])\s*', r'\1\n', body)
        body = re.sub(r'\n{3,}', '\n\n', body).strip()
        if not body.startswith('-'):
            body = '- ' + body
    
    return clean_title, body, title_depts

# ----------------------- 부서 매칭 로직 -----------------------

def measure_block_y_ranges(page, main_lines: List[Tuple[float, str]], blocks: List[str]) -> List[Tuple[float, float]]:
    """각 블록의 y 범위 추정"""
    bullet_lines = [(y, s) for (y, s) in main_lines if s.lstrip().startswith("○")]
    starts = [y for y, _ in bullet_lines]
    
    ranges = []
    for i, y_start in enumerate(starts):
        if i < len(starts) - 1:
            y_end = starts[i + 1] - 0.1
        else:
            y_end = page.rect.height - 5
        ranges.append((y_start, y_end))
    
    # 블록 수와 맞춤
    while len(ranges) < len(blocks):
        if ranges:
            ranges.append((ranges[-1][0], ranges[-1][1]))
        else:
            ranges.append((0.0, page.rect.height))
    
    return ranges[:len(blocks)]

def assign_departments_by_y(blocks: List[Dict], dept_rows: List[Dict], known_departments: Set[str]) -> List[List[str]]:
    """
    각 블록에 대해:
      1) y-overlap 있는 행들의 부서를 모두 수집
      2) 없으면 y_center가 가장 가까운 행 1개 선택
      3) 중복 제거 + KNOWN_DEPARTMENTS 교차(마지막 방어)
    반환: blocks와 같은 인덱스 순서의 [부서리스트]
    """
    results = []
    for block in blocks:
        y_top, y_bottom = block["y_top"], block["y_bottom"]
        matched_depts = []
        
        # 1) Y-overlap 체크 (겹치는 부서행들의 부서 수집)
        overlap_found = False
        for row in dept_rows:
            y_center = row["y_center"]
            # 블록 Y 범위와 부서행 Y가 겹치는지 확인 (±5pt 허용)
            if y_top - 5 <= y_center <= y_bottom + 5:
                matched_depts.extend(row["depts"])
                overlap_found = True
        
        # 2) Fallback: 가장 가까운 부서행 선택 (overlap이 없을 때)
        if not matched_depts and dept_rows:
            nearest_row = min(dept_rows, key=lambda r: min(
                abs(r["y_center"] - y_top), 
                abs(r["y_center"] - y_bottom)
            ))
            matched_depts.extend(nearest_row["depts"])
        
        # 3) 정리: 중복 제거 + 화이트리스트 필터링
        unique_depts = []
        seen = set()
        for dept in matched_depts:
            if dept in known_departments and dept not in seen:
                seen.add(dept)
                unique_depts.append(dept)
        
        results.append(unique_depts)
    
    return results

def merge_department_lists(column_depts: List[str], title_depts: List[str]) -> List[str]:
    """
    부서열 부서 + 제목 부서 통합 및 화이트리스트 최종 필터링
    """
    all_depts = column_depts + title_depts
    
    # 화이트리스트 필터링
    filtered_depts = [d for d in all_depts if d in KNOWN_DEPARTMENTS]
    
    # 중복 제거 (순서 유지)
    seen = set()
    final_depts = []
    for dept in filtered_depts:
        if dept not in seen:
            seen.add(dept)
            final_depts.append(dept)
    
    return final_depts

# ----------------------- 단위 테스트 로깅 -----------------------

def validate_and_log_block(block_idx: int, title: str, depts: List[str], deadline: str):
    """블록 단위 검증 및 로깅"""
    warnings = []
    
    # 1) 제목에 부서 접미사 남음 체크
    org_suffixes = ["과", "소", "국", "실", "관", "센터", "사업소", "팀", "단"]
    for suffix in org_suffixes:
        if title.strip().endswith(suffix):
            warnings.append(f"제목 끝에 '{suffix}' 접미사 남음")
            break
    
    # 2) 화이트리스트 밖 부서 체크
    invalid_depts = [d for d in depts if d not in KNOWN_DEPARTMENTS]
    if invalid_depts:
        warnings.append(f"화이트리스트 밖 부서: {invalid_depts}")
    
    # 로깅
    log.info(f"Block {block_idx:2d}: 제목=[{title[:50]}{'...' if len(title)>50 else ''}]")
    log.info(f"           부서={depts} 기한=[{deadline}]")
    
    if warnings:
        log.warning(f"           경고: {' | '.join(warnings)}")

# ----------------------- 메인 처리 파이프라인 -----------------------

def process_pdf_with_whitelist(pdf_path: str) -> Tuple[List[Dict[str, Any]], str]:
    """화이트리스트 기반 PDF 처리 메인 함수"""
    doc = fitz.open(pdf_path)
    source = Path(pdf_path).name
    log.info(f"Processing {source} ({doc.page_count} pages)")

    all_records = []
    all_pretty_blocks = []

    for page_num, page in enumerate(doc, start=1):
        raw_text = page.get_text("text")
        category = detect_page_category(raw_text)

        # 열 구조 분석
        col_edges, last_col_start = detect_column_edges(page)
        cut_y = find_first_circle_y(page)
        
        log.info(f"Page {page_num}: last_col_start={last_col_start:.1f}pt, cut_y={cut_y:.1f}pt")

        # Y축 기반 블록-부서 매칭 시스템 사용
        blocks_with_y = build_blocks_with_y_ranges(page, last_col_start)
        if not blocks_with_y:
            continue

        # 부서열에서 부서 추출 (Y축 기반)
        dept_rows = extract_dept_rows(page, last_col_start, KNOWN_DEPARTMENTS)

        # Y축 좌표 기반 부서-블록 매칭
        column_depts_per_block = assign_departments_by_y(blocks_with_y, dept_rows, KNOWN_DEPARTMENTS)

        # 각 블록 처리
        for block_idx, block_data in enumerate(blocks_with_y, start=1):
            block_text = block_data["text"]
            y_info = f"Y:{block_data['y_top']:.1f}-{block_data['y_bottom']:.1f}"
            
            log.info(f"Block {block_idx}: {y_info}")
            # 처리기한 추출
            deadline = extract_deadline_from_text(block_text)
            
            # 날짜 제거된 블록으로 제목/본문 분리
            clean_block = remove_all_dates_from_text(block_text)
            title, body, title_depts = process_block_content(clean_block)
            
            # 최종 날짜 제거
            title = remove_all_dates_from_text(title)
            body = remove_all_dates_from_text(body)
            
            # 최소 텍스트 정제
            title = minimal_text_cleanup(title)
            body = minimal_text_cleanup(body)

            # 부서 통합 (부서열 + 제목)
            column_depts = column_depts_per_block[block_idx - 1] if block_idx - 1 < len(column_depts_per_block) else []
            final_depts = merge_department_lists(column_depts, title_depts)

            # 단위 테스트 로깅
            validate_and_log_block(block_idx, title, final_depts, deadline)

            # TXT 포맷 생성
            txt_parts = [f"○ {title}"]
            if body:
                txt_parts.append(body)
            if deadline:
                txt_parts.append(f"처리기한: {deadline}")
            if final_depts:
                txt_parts.append("부서: " + ", ".join(final_depts))
            
            pretty_block = "\n".join(txt_parts)
            all_pretty_blocks.append(pretty_block)

            # JSON 레코드 생성
            record = {
                "source_file": source,
                "page": page_num,
                "index": block_idx,
                "category": category,
                "title": title,
                "body": body.replace("- ", "").replace("\n", " ").strip() if body else "",
                "deadline": deadline,
                "departments": final_depts,
                "lang": "ko",
                "doc_type": "gucheong_jisisa",
                "directive": clean_block
            }
            all_records.append(record)

    doc.close()

    # 중복 제거 (텍스트 기반)
    seen = set()
    unique_records = []
    for r in all_records:
        key = f"{r.get('title', '')}||{r.get('body', '')}||{','.join(r.get('departments', []))}"
        key = re.sub(r'\s+', ' ', key)[:500]
        if key not in seen:
            seen.add(key)
            unique_records.append(r)

    seen_blocks = set()
    unique_blocks = []
    for block in all_pretty_blocks:
        key = re.sub(r'\s+', ' ', block)[:500]
        if key not in seen_blocks:
            seen_blocks.add(key)
            unique_blocks.append(block)

    pretty_text = "\n\n".join(unique_blocks)
    return unique_records, pretty_text

# ----------------------- 저장 및 CLI -----------------------

def save_results(records: List[Dict], pretty_text: str, pdf_path: str):
    """결과 파일 저장"""
    stem = Path(pdf_path).with_suffix("")
    
    jsonl_path = f"{stem}_whitelist.jsonl"
    txt_path = f"{stem}_whitelist.txt"
    
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(pretty_text + ("\n" if not pretty_text.endswith("\n") else ""))
    
    log.info(f"Saved: {jsonl_path} ({len(records)} records)")
    log.info(f"Saved: {txt_path} ({len(pretty_text)} chars)")
    
    return jsonl_path, txt_path

def print_validation_summary(records: List[Dict]):
    """최종 검증 요약 출력"""
    print("\n" + "="*50)
    print("화이트리스트 기반 부서 추출 검증 결과")
    print("="*50)
    
    total_blocks = len(records)
    blocks_with_depts = sum(1 for r in records if r.get('departments'))
    blocks_with_deadline = sum(1 for r in records if r.get('deadline'))
    
    # 제목 끝 부서 접미사 체크
    org_suffixes = ["과", "소", "국", "실", "관", "센터", "사업소", "팀", "단"]
    title_suffix_issues = 0
    for r in records:
        title = r.get('title', '').strip()
        if any(title.endswith(suffix) for suffix in org_suffixes):
            title_suffix_issues += 1
    
    # 화이트리스트 밖 부서 체크
    invalid_dept_issues = 0
    for r in records:
        depts = r.get('departments', [])
        if any(d not in KNOWN_DEPARTMENTS for d in depts):
            invalid_dept_issues += 1
    
    print(f"✓ 총 추출 블록: {total_blocks}개")
    print(f"✓ 부서 있는 블록: {blocks_with_depts}개")
    print(f"✓ 처리기한 있는 블록: {blocks_with_deadline}개")
    print(f"✓ 제목 끝 부서 접미사 남음: {title_suffix_issues}개 (0이어야 함)")
    print(f"✓ 화이트리스트 밖 부서: {invalid_dept_issues}개 (0이어야 함)")
    print(f"✓ 화이트리스트 부서 수: {len(KNOWN_DEPARTMENTS)}개")
    
    if title_suffix_issues == 0 and invalid_dept_issues == 0:
        print("\n🎉 모든 검증 통과!")
    else:
        print(f"\n⚠️  검증 실패: {title_suffix_issues + invalid_dept_issues}개 이슈")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("사용법: python directive_extractor_whitelist_final.py <PDF_파일_경로>")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    if not os.path.exists(pdf_file):
        print(f"파일을 찾을 수 없습니다: {pdf_file}")
        sys.exit(1)
    
    print(f"화이트리스트 기반 PDF 처리 시작: {pdf_file}")
    print(f"화이트리스트 부서 수: {len(KNOWN_DEPARTMENTS)}개")
    print(f"안전 경계값: 본문({MAIN_BOUNDARY_OFFSET}pt), 부서열({DEPT_BOUNDARY_OFFSET}pt)")
    
    # 메인 처리
    records, pretty_text = process_pdf_with_whitelist(pdf_file)
    
    # 결과 저장
    jsonl_path, txt_path = save_results(records, pretty_text, pdf_file)
    
    # 검증 요약
    print_validation_summary(records)
    
    print(f"\n완료!")
    print(f"JSONL: {jsonl_path}")
    print(f"TXT: {txt_path}")
    
    # 미리보기
    if pretty_text:
        print(f"\n--- 결과 미리보기 ---")
        lines = pretty_text.split("\n\n")
        if lines:
            preview = lines[0][:300]
            if len(lines[0]) > 300:
                preview += "..."
            print(preview)