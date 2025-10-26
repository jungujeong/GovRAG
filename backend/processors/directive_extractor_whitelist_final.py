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
DEPT_BOUNDARY_OFFSET = -15  # 부서열 영역: last_col_start + 이 값 이상만 사용 (더 넓게 조정)

# 화이트리스트 부서 목록 (사용자 제공)
KNOWN_DEPARTMENTS = {
    # 핵심 부서/국/실
    "총 무 과","총무과","기획예산과","기 획 실","기획실","기획조정실","홍보담당관",
    "행정지원과","행정지원국","안전도시국","미래성장국","복지환경국","소통감사실",

    # 경제/산업/일자리
    "경제일자리과","일자리경제과","산업경제과","투자유치과","경제진흥과","경제문화국",

    # 도시·건설·교통
    "도시계획과","도시재생과","도시정비과","도시관리과",
    "건 설 과","건설과","건설관리과","건 축 과","건축과","도 로 과","하 천 과",
    "교통행정과","주차관리과","스마트도시과","정보통신과",
    "토지정보과","토지관리과",

    # 안전·재난
    "안전총괄과","재난안전과","민방위과",

    # 환경·청소·공원·자원순환
    "환경위생과","위생환경과","청소행정과","자원순환과",
    "공원녹지과","산림녹지과","환경정책과",

    # 문화·관광·체육·교육
    "문화예술과","문화체육과","관광진흥과","체육지원과",
    "평생교육과","교육정책과","평생학습과", "문화관광홍보과", "문화관광 홍 보 과", 

    # 복지·보건
    "복지정책과","복지사업과","사회복지과","어르신장애인과","노인복지과",
    "가족정책과","여성가족과","아동보육과","청년정책과",
    "건강증진과","보 건 소","보건소","주민복지국",

    # 세무·재무·회계·민원
    "세 무 과","재 무 과","재무과","회 계 과","민원여권과","민원봉사과",

    # 전략/특수 조직
    "전략사업과","도시재생지원센터","시설관리사업소","의회사무국",

    # 관·센터·단(실제 많이 쓰이는 명칭)
    "청소년상담복지센터","장애인복지관","노인복지관","여성인력개발센터",

    # 동 조직
    "다대1동","다대2동","다대 1 동","다대 2 동",

    # 전동(집합 지시용) - 전부서는 특수 처리로 별도 관리
    "전동","전 동","전부서","전 부서","해당부서", "해 당 부 서",
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
DATE_RX = re.compile(r'(?P<y>20\d{2})\.\s*(?P<m>\d{1,2})\.\s*(?P<d>\d{1,2})\.?')
YEAR_ONLY_RX = re.compile(r'20\d{2}\.')
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
    # 전부서는 특수 처리하므로 정규화에서 제외
    text = re.sub(r'전\s*동', '전동', text)
    return text

def strip_trailing_departments_from_title(title: str, known_depts: Set[str]) -> Tuple[str, List[str]]:
    """
    제목에서 화이트리스트 기반 부서명 추출 및 제거 (개선된 버전)
    반환: (정제된_제목, 추출된_부서_리스트)
    """
    # 1) 띄어쓰기 정규화
    normalized = normalize_spacing_for_departments(title)

    extracted_depts = []
    cleaned_title = normalized

    # 2) 제목 전체에서 부서명 찾기 (끝뿐만 아니라 중간에도)
    found_matches = []

    # 화이트리스트의 모든 부서명을 체크 (긴 것부터)
    for dept in sorted(known_depts, key=len, reverse=True):
        # 공백을 고려한 더 유연한 패턴
        dept_pattern = re.escape(dept)

        # 기본 패턴: 정확한 매칭
        patterns = [
            rf'\b{dept_pattern}\b',  # 단어 경계로 구분
            rf'{dept_pattern}',      # 정확한 매칭
        ]

        # 공백이 있는 부서명의 경우 공백 제거 버전도 시도
        if ' ' in dept:
            no_space_dept = dept.replace(' ', '')
            patterns.append(rf'\b{re.escape(no_space_dept)}\b')
            patterns.append(rf'{re.escape(no_space_dept)}')

        for pattern in patterns:
            matches = list(re.finditer(pattern, cleaned_title, re.I))
            for match in matches:
                found_matches.append({
                    'dept': dept,
                    'start': match.start(),
                    'end': match.end(),
                    'text': match.group()
                })

    # 겹치는 매칭 제거 (긴 것 우선)
    found_matches.sort(key=lambda x: (x['end'] - x['start']), reverse=True)

    final_matches = []
    used_ranges = []

    for match in found_matches:
        start, end = match['start'], match['end']
        overlap = False
        for used_start, used_end in used_ranges:
            if not (end <= used_start or start >= used_end):
                overlap = True
                break

        if not overlap:
            final_matches.append(match)
            used_ranges.append((start, end))

    # 위치 순으로 정렬 (앞에서 뒤로)
    final_matches.sort(key=lambda x: x['start'])

    # 부서명 제거 (뒤에서부터)
    offset = 0
    for match in reversed(final_matches):
        start, end = match['start'], match['end']
        adjusted_start = start + offset
        adjusted_end = end + offset

        # 부서명 앞뒤 공백도 함께 제거
        text_before = cleaned_title[:adjusted_start].rstrip()
        text_after = cleaned_title[adjusted_end:].lstrip()

        cleaned_title = text_before + (' ' if text_before and text_after else '') + text_after
        offset = len(cleaned_title) - len(text_before + ' ' + text_after) if text_before and text_after else 0

        extracted_depts.append(match['dept'])

    # 추출 순서 뒤집기 (뒤에서부터 제거했으므로)
    extracted_depts.reverse()

    return cleaned_title.strip(), extracted_depts

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
        # 라인 클러스터링: 같은 라인이라고 판단하는 기준을 더 엄격하게 (2.0pt 이하만)
        # 이렇게 해야 "○ 제목", "- 설명", "○ 다음제목" 등이 서로 다른 라인으로 분리됨
        if abs(w[1] - cur[-1][1]) <= 2.0:
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

def restore_korean_spacing(text: str) -> str:
    """
    한글 텍스트의 띄어쓰기를 복원합니다.
    조사, 어미, 동사/형용사 앞에 띄어쓰기를 추가합니다.
    """
    if not text:
        return text

    # 1. 조사 뒤의 명사 경계 (조사 + 명사)
    # "을향" → "을 향", "을위" → "을 위", "을지" → "을 지"
    # 단, "가지고" 같은 복합 어휘는 제외

    # 먼저 "가지고", "가지고" 같은 것들을 임시로 보호
    protected_words = ['가지고', '가지고는', '가지도', '있고', '있지']
    protected_map = {}
    for i, word in enumerate(protected_words):
        placeholder = f"__PROTECTED_{i}__"
        text = text.replace(word, placeholder)
        protected_map[placeholder] = word

    # 이제 조사 뒤의 띄어쓰기 처리
    particles_with_space = ['을', '를', '가', '는', '이', '에', '와', '로']
    for particle in particles_with_space:
        text = re.sub(f'({particle})([가-힣]+)', f'\\1 \\2', text)

    # 보호된 단어 복원
    for placeholder, original_word in protected_map.items():
        text = text.replace(placeholder, original_word)

    # 2. 자주 나오는 명사들 앞에 띄어쓰기 추가
    # 지시사항 문서에서 자주 나오는 명사들의 목록
    common_nouns = [
        '청렴도',  # "구청렴도가" → "구 청렴도가"
        '준비',    # "비준비" → "비 준비"
        '노력',    # "도노력" → "도 노력"
        '관심',    # "고관심" → "고 관심"
        '개발',    # "발개발" → "발 개발"
        '설명',    # "명설명" → "명 설명"
        '향상',    # "도향상" → "도 향상"
        '기한',    # "한기한" → "한 기한"
        '방지',    # "지방지" → "지 방지"
        '문제',    # "제문제" → "제 문제"
        '예산',    # "단예산" → "단 예산"
        '부서',    # "서부서" → "서 부서"
        '동안',    # "간동안" → "간 동안"
        '직원',    # "원직원" → "원 직원"
        '주민',    # "민주민" → "민 주민"
        '사항',    # "항사항" → "항 사항"
        '처리',    # "리처리" → "리 처리"
        '방식',    # "무방식" → "무 방식"
        '방법',    # "법방법" → "법 방법"
    ]

    for noun in common_nouns:
        # "X청렴도" → "X 청렴도" (한 글자 뒤의 명사)
        pattern = f'([가-힣]){noun}'
        text = re.sub(pattern, f'\\1 {noun}', text)

    # 3. 조사 앞에 띄어쓰기 추가
    particles = [
        '은', '는', '이', '가',  # 주격
        '을', '를',  # 목적격
        '에', '에게',  # 위치
        '와', '과',  # 접속
        '로', '으로',  # 도구/양식
        '에서',  # 위치
        '도',  # 포함
        '보다',  # 비교
        '만',  # 제한
        '부터',  # 시작
        '까지',  # 끝
    ]

    for particle in particles:
        # 예: "청렴도은" → "청렴도 은"
        # 다만 이미 띄어쓰기가 있거나 다음이 다른 한글이면 처리 안 함
        text = re.sub(f'([가-힣]){particle}(?![가-힣\s])', f'\\1 {particle}', text)

    # 4. 어미 앞에 띄어쓰기
    endings = [
        # 동사 어미
        '하기',  # "노력하기" → "노력 하기"
        '하지만', '하다', '하는', '하고', '하지', '하면',  # 동사 변형
        '되기', '되지', '되면', '되고',  # 피동사
        '있기', '있지', '있으면', '있고',  # 존재사
        # 형용사 어미
        '한데', '한다', '한다', '한다고',  # 형용사 어미
        '고', '고는', '고도',  # 연결
        '지만', '지', '지도',  # 대조
        '므로', '면', '면서',  # 조건/이유
        '았', '었', '겠', '있', '같',  # 과거/미래/추측
        '네', '네요',  # 발견/의외
        '군', '군요',  # 과거/회상
        '세요', '세',  # 존댓말
    ]

    for ending in endings:
        text = re.sub(f'([가-힣]){ending}(?![가-힣\s])', f'\\1 {ending}', text)

    # 5. 동사/형용사 뒤 공백
    # "위해노력" → "위해 노력", "준비해주" → "준비 해주"
    text = re.sub(r'(해)([가-힣]{2,})', r'\1 \2', text)
    text = re.sub(r'(주고)([가-힣]{2,})', r'\1 \2', text)
    text = re.sub(r'(주기)([가-힣]{2,})', r'\1 \2', text)

    # 6. 명사 + 해석 동사 경계
    # "준비해주고" → "준비 해주고"
    text = re.sub(r'([가-힣]{2,})(해주|해야|해서|한다|한다)', r'\1 \2', text)

    # 7. 중복 공백 제거
    text = re.sub(r'\s+', ' ', text)

    return text

def minimal_text_cleanup(text: str) -> str:
    """최소한의 텍스트 정제 (의미 변경 방지)"""
    original_text = text
    
    try:
        # 1. 가장 기본적인 회차 표현만 정리
        text = re.sub(r'제\s*(\d+)\s*회', r'제 \1회', text)

        # 2. 특정 패턴 수정 (PDF 추출 오류 보정)
        # "149 명 중 명으로 타구에 비해 주민 피해가 적었음 3" → "149명 중 3명으로 타구에 비해 주민 피해가 적었음"
        text = re.sub(r'(\d+)\s*명\s*중\s*명으로([^.]*?)적었음\s*(\d+)', r'\1명 중 \3명으로\2적었음', text)

        # 일반적인 패턴들
        text = re.sub(r'(\d+)\s*명\s*중\s*명으로([^.]*?)\s*(\d+)\.', r'\1명 중 \3명으로\2.', text)
        text = re.sub(r'(\d+)\s*명\s*중\s*명\s*으?로([^.]*?)\s*(\d+)', r'\1명 중 \3명으로\2', text)

        # 기본적인 공백 처리: "149 명" → "149명"
        text = re.sub(r'(\d+)\s+명', r'\1명', text)

        # "5 월" → "5월" 같은 기본 단위 처리
        text = re.sub(r'(\d+)\s+월', r'\1월', text)
        text = re.sub(r'(\d+)\s+일', r'\1일', text)
        text = re.sub(r'(\d+)\s+년', r'\1년', text)

        # 3. 기본적인 공백 정리 (최소한만)
        # 줄바꿈은 공백으로 변환
        text = re.sub(r'\n+', ' ', text)

        # 3. 구두점 앞 공백 제거
        text = re.sub(r'\s+([.,;:])', r'\1', text)
        text = re.sub(r'(\d+)\s*\.', r'\1.', text)  # 숫자 뒤 점 정리

        # 4. 중복 구두점만 정리 (안전하게)
        text = re.sub(r',,+', ',', text)
        text = re.sub(r'\.\.+', '.', text)

        # 5. 부서명 띄어쓰기 특별 처리
        text = re.sub(r'전\s*부\s*서', '전부서', text)
        text = re.sub(r'전\s*동', '전동', text)
        
        # 6. 빈 괄호 제거
        text = re.sub(r'\(\s*\)', '', text)
        text = re.sub(r'\[\s*\]', '', text)

        # 7. 부서 띄어쓰기 정규화 (기존 함수 사용)
        text = normalize_spacing_for_departments(text)

        # 8. 최종 중복 공백 제거 (모든 처리 후)
        text = re.sub(r'\s{2,}', ' ', text)

        # 9. 한글 띄어쓰기 복원
        text = restore_korean_spacing(text)

        # 검증: 길이가 크게 변경되었으면 원본 반환
        if len(text) < len(original_text) * 0.7:
            log.warning("Text cleanup resulted in significant length reduction, using original")
            return original_text.strip()

        # 검증: 핵심 키워드가 사라졌으면 원본 반환
        critical_keywords = ['구청장', '지시', '사항', '처리', '기한']
        original_keywords = sum(1 for kw in critical_keywords if kw in original_text)
        cleaned_keywords = sum(1 for kw in critical_keywords if kw in text)

        if original_keywords > 0 and cleaned_keywords < original_keywords * 0.8:
            log.warning("Text cleanup removed critical keywords, using original")
            return original_text.strip()

        return text.strip()

    except Exception as e:
        log.error(f"Error during text cleanup: {e}")
        return original_text.strip()

def extract_deadline_from_text(text: str) -> str:
    """날짜 패턴에서 처리기한 추출"""
    # 1. 기본 연속된 날짜 패턴 (2024. 3. 6.)
    basic_pattern = re.compile(r'(20\d{2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})\s*\.?')
    m1 = basic_pattern.search(text)
    if m1:
        y, mth, d = m1.groups()
        return f"{int(y)}. {int(mth)}. {int(d)}."

    # 2. 부서명이 중간에 끼어있는 패턴 (2024. 부서명 3. 6.)
    # 년도 다음에 부서명이 오고 그 뒤에 월.일이 오는 패턴
    dept_pattern = re.compile(r'(20\d{2})\s*\.\s*[가-힣\s]+?(\d{1,2})\s*\.\s*(\d{1,2})\s*\.?')
    m2 = dept_pattern.search(text)
    if m2:
        y, mth, d = m2.groups()
        return f"{int(y)}. {int(mth)}. {int(d)}."

    # 3. 원래 패턴도 시도
    m3 = DATE_RX.search(text)
    if m3:
        y, mth, d = m3.group('y'), m3.group('m'), m3.group('d')
        return f"{int(y)}. {int(mth)}. {int(d)}."

    return ""

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

def split_multiple_directives(block_text: str) -> List[str]:
    """
    하나의 블록에 여러 지시사항이 있는 경우 분리
    - "○ 제목\n- 설명\n○ 다음제목\n- 다음설명" 형식을 정확히 인식
    - 제목(○)과 설명(-)의 경계를 명확히 함
    """
    if not block_text:
        return []

    # 먼저 라인 단위로 분리 (문장 끝 기준이 아닌 명시적 줄바꿈)
    lines = block_text.split('\n')

    directives = []
    current_directive_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # "○"로 시작하면 새로운 지시사항의 시작
        if line.startswith('○'):
            # 이전 지시사항이 있으면 저장
            if current_directive_lines:
                directive_text = '\n'.join(current_directive_lines)
                if directive_text.strip():
                    directives.append(directive_text.strip())
            # 새 지시사항 시작
            current_directive_lines = [line]
        else:
            # 지시사항 내용 추가 (제목 설명, 상세 내용 등)
            if current_directive_lines:
                current_directive_lines.append(line)
            else:
                # ○가 없으면 새로운 지시사항으로 취급
                current_directive_lines = [line]

    # 마지막 지시사항 저장
    if current_directive_lines:
        directive_text = '\n'.join(current_directive_lines)
        if directive_text.strip():
            directives.append(directive_text.strip())

    return directives if directives else [block_text]

def extract_directives_with_departments(page, last_col_start: float, known_departments: Set[str]) -> List[Dict]:
    """
    개선된 방식: ○ 기준으로 구간을 나누어 정확한 부서 매칭
    각 ○ 시작점부터 다음 ○ 전까지의 범위에서 부서를 매칭하여 정확도 향상
    """
    # 전체 텍스트를 y좌표와 함께 추출
    text_instances = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") == 0:  # 텍스트 블록
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        text_instances.append({
                            "text": text,
                            "y": bbox[1],  # y 좌표
                            "x": bbox[0],  # x 좌표
                            "bbox": bbox
                        })

    # y좌표로 정렬 (위에서 아래로)
    text_instances.sort(key=lambda x: (x["y"], x["x"]))

    # 연속된 텍스트 조각들을 병합 (같은 Y라인에서 가까운 X좌표)
    merged_instances = []
    current_line = []
    current_y = None

    for item in text_instances:
        # ○ 또는 □ 기호가 있으면 새로운 라인의 시작
        has_bullet = "○" in item["text"] or "□" in item["text"]

        # 같은 라인 판단:
        # - 현재 라인이 ○/□를 가지면, 다음 항목까지 Y 차이를 15pt까지 허용 (○와 제목을 묶기 위함)
        #   15pt는 ○와 제목을 포함하되, 설명(-)과는 분리하기 충분함
        # - 그렇지 않으면 Y 차이 1.3pt 이내만
        if current_line and any("○" in t["text"] or "□" in t["text"] for t in current_line):
            # 현재 라인에 ○/□가 있으면, 다음 항목까지 Y 차이 허용을 확대 (15pt)
            same_y = (current_y is None or abs(item["y"] - current_y) <= 15.0)
        else:
            # 일반적인 라인: Y 차이 1.3pt 이내
            same_y = (current_y is None or abs(item["y"] - current_y) <= 1.3)

        # X좌표 체크: 이전 텍스트들과 비슷한 영역에 있는지 확인
        same_x_region = True
        if current_line and len(current_line) > 0:
            # 현재 라인의 평균 X좌표 계산
            avg_x = sum(t["x"] for t in current_line) / len(current_line)

            # X 범위 설정:
            # - ○/□가 있으면 매우 느슨하게 (250pt)
            # - 일반적인 경우는 느슨하게 (200pt - 원래 150에서 증가)
            # 이렇게 하면 ○와 SNS 등이 같은 라인으로 병합됨
            x_threshold = 250 if any("○" in t["text"] or "□" in t["text"] for t in current_line) else 200

            # 새 텍스트가 평균 X좌표에서 x_threshold 이상 떨어져 있으면 다른 영역
            if abs(item["x"] - avg_x) > x_threshold:
                same_x_region = False

        # ○/□가 여러 개 있으면 새 라인 강제 (같은 라인에 ○가 2개 이상 있으면 안됨)
        force_new_line = False
        if current_line and has_bullet:
            # 현재 라인에 이미 ○/□가 있고 새 항목도 ○/□를 가지면 강제로 새 라인
            if any("○" in t["text"] or "□" in t["text"] for t in current_line):
                force_new_line = True

        if (same_y and same_x_region and not force_new_line):
            current_line.append(item)
            current_y = item["y"]
        else:
            # 라인 병합
            if current_line:
                # 같은 라인의 텍스트들을 X좌표 순으로 정렬하여 병합
                current_line.sort(key=lambda x: x["x"])
                merged_text = " ".join([t["text"] for t in current_line])
                # X좌표: 가장 오른쪽 요소의 중심점 사용 (부서명이 보통 오른쪽에 있음)
                rightmost = current_line[-1]
                x_center = (rightmost["x"] + rightmost["bbox"][2]) / 2.0
                merged_instances.append({
                    "text": merged_text,
                    "y": current_y,
                    "x": x_center,  # 중심점으로 변경
                    "bbox": current_line[0]["bbox"]
                })
            current_line = [item]
            current_y = item["y"]

    # 마지막 라인 처리
    if current_line:
        current_line.sort(key=lambda x: x["x"])
        merged_text = " ".join([t["text"] for t in current_line])
        # X좌표: 가장 오른쪽 요소의 중심점 사용 (부서명이 보통 오른쪽에 있음)
        rightmost = current_line[-1]
        x_center = (rightmost["x"] + rightmost["bbox"][2]) / 2.0
        merged_instances.append({
            "text": merged_text,
            "y": current_y,
            "x": x_center,  # 중심점으로 변경
            "bbox": current_line[0]["bbox"]
        })

    text_instances = merged_instances

    # 지시사항 구간과 부서 구간을 분리
    directive_parts = []
    department_parts = []

    for item in text_instances:
        text = item["text"]
        x = item["x"]
        y = item["y"]

        # 부서열인지 본문인지 판단
        is_department_column = x >= last_col_start + DEPT_BOUNDARY_OFFSET
        is_main_content = x <= last_col_start + MAIN_BOUNDARY_OFFSET

        if is_department_column:
            # 부서열 텍스트 (부서명이 포함된 경우에만)
            normalized_text = re.sub(r'\s+', '', text)
            has_dept = any(dept in text or re.sub(r'\s+', '', dept) in normalized_text for dept in known_departments)

            # 디버그: 부서열 텍스트 출력
            if "해당" in text or "해당" in normalized_text:
                log.info(f"[DEBUG] Department column text (해당): '{text}' (normalized: '{normalized_text}', Y:{y:.1f}, has_dept:{has_dept})")

            # "전부서" 특수 처리
            is_all_dept = False
            if (text.strip() in ["전부서", "전 부서", "전 부 서"] or
                re.match(r'^\s*전\s*부\s*서\s*$', text) or
                normalized_text == "전부서" or
                re.search(r'전\s*부\s*서', text)):
                is_all_dept = True
                log.info(f"[DEBUG] '전부서' detected from text: '{text}' (normalized: '{normalized_text}')")

            # "해당부서" 특수 처리
            is_haedang_dept = False
            if (text.strip() in ["해당부서", "해당 부서", "해 당 부 서"] or
                re.match(r'^\s*해\s*당\s*부\s*서\s*$', text) or
                normalized_text == "해당부서" or
                re.search(r'해\s*당\s*부\s*서', text)):
                is_haedang_dept = True
                log.info(f"[DEBUG] '해당부서' detected from text: '{text}' (normalized: '{normalized_text}')")

            has_dept = has_dept or is_all_dept or is_haedang_dept

            # 더 유연한 부서명 매칭 - 공백으로 분리된 부서명도 포함
            if not has_dept:
                # 부분 매칭도 시도 (공백으로 분리된 부서명)
                text_without_spaces = re.sub(r'\s+', '', text)
                for dept in known_departments:
                    dept_normalized = re.sub(r'\s+', '', dept)
                    if dept_normalized and (dept_normalized in text_without_spaces or text_without_spaces in dept_normalized):
                        has_dept = True
                        break

            if has_dept:
                department_parts.append({
                    "text": text,
                    "y": y,
                    "x": x
                })
        elif is_main_content:
            # 본문 텍스트
            directive_parts.append({
                "text": text,
                "y": y,
                "x": x
            })

    # 개선된 방식: □(네모)를 헤더로, ○를 지시사항으로 인식
    # 1단계: 모든 □(헤더)와 ○(지시사항)의 위치 파악
    headers = []  # □ 헤더들
    circles = []  # ○ 지시사항들

    for idx, item in enumerate(directive_parts):
        text = item["text"]

        # □ 헤더 찾기
        if text.startswith('□') or text.lstrip().startswith('□'):
            header_text = text.lstrip().lstrip('□').strip()
            headers.append({
                "y": item["y"],
                "text": header_text
            })
            log.info(f"[DEBUG] Header (□) detected: '{header_text}' at Y:{item['y']:.1f}")

        # ○ 지시사항 찾기
        elif text.startswith('○') or text.lstrip().startswith('○'):
            circle_text = text.lstrip().lstrip('○').strip()

            # circle_text가 비어있거나 특수 문자만 있으면, 다음 아이템들을 look-ahead로 확인
            # 빈 셀과 특수 문자(, · . 등)를 건너뛰고 실제 제목을 찾기
            if (not circle_text or circle_text in [',', '·', '.', ';', ':', '/*', '*/', '▸', '▪']) and idx + 1 < len(directive_parts):
                # 다음 아이템들을 순회하면서 빈 셀과 특수 문자를 건너뛰기
                for next_idx in range(idx + 1, min(idx + 5, len(directive_parts))):
                    next_item = directive_parts[next_idx]
                    next_text = next_item["text"].strip()

                    # 빈 셀이거나 특수 문자/dash/circle 기호면 건너뛰기
                    if (next_text and
                        not next_text.startswith('-') and
                        not next_text.startswith('○') and
                        next_text not in [',', '·', '.', ';', ':', '/*', '*/', '▸', '▪', '·', '‧']):

                        circle_text = next_text
                        log.info(f"[DEBUG] Title extracted from next item (skipped empty cells): '{circle_text}' at Y:{next_item['y']:.1f}")
                        break

            circles.append({
                "y": item["y"],
                "text": circle_text
            })
            log.info(f"[DEBUG] Circle (○) detected: '{circle_text}' at Y:{item['y']:.1f}")

    headers.sort(key=lambda x: x["y"])
    circles.sort(key=lambda x: x["y"])

    log.info(f"[DEBUG] Found {len(headers)} headers (□) and {len(circles)} directives (○)")

    # 2단계: 각 ○마다 해당하는 □ 헤더 결정 및 Y범위 설정
    directive_ranges = []
    for i, circle_item in enumerate(circles):
        circle_y = circle_item["y"]
        circle_text = circle_item["text"]

        # 이 ○보다 이전의 마지막 □ 찾기
        relevant_header = ""
        for header in reversed(headers):
            if header["y"] < circle_y:
                relevant_header = header["text"]
                break

        # 범위 끝: 다음 ○의 Y좌표에서 충분한 마진을 뺌 (다음 지시사항 제목 제외)
        if i < len(circles) - 1:
            # 다음 ○까지의 거리를 25pt 마진만큼 줄여서, 다음 지시사항의 제목이 포함되지 않도록 함
            # 이전 8pt는 충분하지 않아서 다음 지시사항 번호가 포함되는 문제 발생
            next_circle_y = circles[i + 1]["y"]
            range_end = next_circle_y - 25.0
        else:
            range_end = circle_y + 1000

        directive_ranges.append({
            "circle_y": circle_y,
            "circle_text": circle_text,
            "header": relevant_header,
            "range_start": circle_y,
            "range_end": range_end
        })
        log.info(f"[DEBUG] Circle {i+1}: Header='{relevant_header}', Circle='{circle_text}', Y:{circle_y:.1f} ~ {range_end:.1f}")

    # 3단계: 각 ○별로 헤더 + ○ 지시사항 + 본문 + 부서 추출
    directives = []

    for i, range_info in enumerate(directive_ranges):
        circle_y = range_info["circle_y"]
        circle_text = range_info["circle_text"]
        header = range_info["header"]
        range_start = range_info["range_start"]
        range_end = range_info["range_end"]

        log.info(f"[DEBUG] ========== Circle {i+1} Processing ==========")
        log.info(f"[DEBUG] Header: '{header}', Circle: '{circle_text}'")

        # 해당 구간의 본문 텍스트 수집 (○부터 다음 ○ 전까지)
        body_texts = []
        title_text = circle_text  # 초기값: circle_text (비어있으면 다음 라인들에서 찾음)
        found_title = False

        for item in directive_parts:
            if range_start <= item["y"] < range_end:
                text = item["text"]
                # ○ 기호 제거
                if text.startswith('○') or text.lstrip().startswith('○'):
                    clean_text = text.lstrip().lstrip('○').strip()
                    if clean_text:  # ○ 바로 뒤의 텍스트가 있으면 제목 업데이트
                        title_text = clean_text
                        found_title = True
                    body_texts.append(clean_text)
                # circle_text가 비어있으면, "-"로 시작하지 않고 아직 제목을 찾지 못했다면
                # 이를 제목으로 취급
                elif not found_title and not title_text and not text.startswith('-') and text.strip():
                    title_text = text.strip()
                    found_title = True
                    log.info(f"[DEBUG] Title extracted from body: '{title_text}'")
                else:
                    body_texts.append(text)
                log.info(f"[DEBUG] Added text: '{text}'")

        # 전체 지시사항 텍스트 구성: 헤더 + ○ 지시사항 + 본문
        directive_text_parts = []
        if header:
            directive_text_parts.append(header)

        # title_text와 body_texts에서 다음 지시사항 번호(예: "231  재건축") 제거
        # 지시사항 번호 패턴: 3자리 숫자 + 공백으로 시작하거나 포함된 부분
        # title_text의 경우 맨 뒤에 지시사항 번호가 붙어있을 수 있음
        if title_text:
            title_text = re.sub(r'\s*\d{3}\s+.*$', '', title_text).strip()
            log.info(f"[DEBUG] Title after removing next directive number: '{title_text[:80]}'")

        # body_texts에서도 제거
        if body_texts:
            log.info(f"[DEBUG] body_texts last 3 items before cleanup: {body_texts[-3:] if len(body_texts) >= 3 else body_texts}")

        while body_texts and re.match(r'^\d{3}\s', body_texts[-1]):
            removed = body_texts.pop()
            log.info(f"[DEBUG] Removed next directive number from body: '{removed}'")

        # "보고", "훈시" 같은 카테고리 레이블도 제거
        while body_texts and body_texts[-1] in ['보고', '훈시', '지시', '보', '고']:
            removed = body_texts.pop()
            log.info(f"[DEBUG] Removed category label from body: '{removed}'")

        # title_text와 body_texts를 적절히 조합
        if title_text:
            directive_text_parts.append(f"○ {title_text}")
            # body_texts에서 이미 title로 사용된 텍스트 제거
            if found_title and body_texts and body_texts[0] == title_text:
                body_texts = body_texts[1:]
            directive_text_parts.extend(body_texts)
        else:
            # title이 없으면 ○만 표시
            directive_text_parts.append("○")
            directive_text_parts.extend(body_texts)

        directive_text = " ".join(directive_text_parts)
        directive_text = minimal_text_cleanup(directive_text)

        # 해당 구간의 부서열 텍스트에서 부서 추출
        matched_departments = []

        # 부서열에서 해당 구간의 부서만 찾기 (더 엄격한 Y 범위 적용)
        # Y 범위를 조금 좁혀서 인접 지시사항의 부서가 섞이지 않도록 함
        range_margin = 3.5  # 5pt 여유만 허용
        for dept_item in department_parts:
            if (range_start - range_margin) <= dept_item["y"] < (range_end - range_margin):
                dept_text = dept_item["text"]
                log.info(f"[DEBUG] Found department text in directive {i+1} range: '{dept_text}' at Y:{dept_item['y']:.1f}")

                # 특수 부서 처리
                # 먼저 괄호 제거 (예: "( 전  동 )" → "전  동")
                dept_text_cleaned = re.sub(r'[()（）]', '', dept_text).strip()
                normalized_text = re.sub(r'\s+', '', dept_text_cleaned)

                # "전부서" 특수 처리 - 더 엄격한 매칭
                is_all_dept = False
                if (dept_text_cleaned.strip() in ["전부서", "전 부서", "전 부 서"] or
                    re.match(r'^\s*전\s*부\s*서\s*$', dept_text_cleaned) or
                    normalized_text == "전부서" or
                    re.search(r'^\s*전\s*부\s*서\s*$', dept_text_cleaned)):  # 단어 경계로 제한
                    is_all_dept = True

                if is_all_dept:
                    matched_departments.append("전부서")
                    log.info(f"[DEBUG] Matched '전부서' from: '{dept_text}'")

                # "해당부서" 특수 처리 - 더 엄격한 매칭
                is_haedang_dept = False
                if (dept_text_cleaned.strip() in ["해당부서", "해당 부서", "해 당 부 서"] or
                    re.match(r'^\s*해\s*당\s*부\s*서\s*$', dept_text_cleaned) or
                    normalized_text == "해당부서" or
                    re.search(r'^\s*해\s*당\s*부\s*서\s*$', dept_text_cleaned)):  # 단어 경계로 제한
                    is_haedang_dept = True

                if is_haedang_dept:
                    matched_departments.append("해당부서")
                    log.info(f"[DEBUG] Matched '해당부서' from: '{dept_text}'")

                # 일반 부서명 매칭 (길이 순으로 정렬하여 더 구체적인 매칭 우선)
                sorted_depts = sorted(known_departments, key=len, reverse=False)  # 짧은 것부터
                for dept in sorted_depts:
                    dept_normalized = re.sub(r'\s+', '', dept)
                    dept_clean = dept.replace(" ", "")

                    # 이미 매칭된 부서면 스킵
                    if dept_clean in matched_departments:
                        continue

                    # 정확 매칭 (정제된 텍스트 사용)
                    if dept in dept_text_cleaned:
                        matched_departments.append(dept_clean)
                        log.info(f"[DEBUG] Exact match: '{dept_text}' -> '{dept_clean}'")
                    # 공백 제거 후 정확 매칭
                    elif dept_normalized == normalized_text:
                        matched_departments.append(dept_clean)
                        log.info(f"[DEBUG] Normalized exact match: '{dept_text}' (normalized: '{normalized_text}') -> '{dept_clean}' (dept: '{dept}')")
                    # 부분 매칭 (더 신중하게)
                    elif len(dept_normalized) >= 3 and (dept_normalized in normalized_text or normalized_text in dept_normalized):
                        matched_departments.append(dept_clean)
                        log.info(f"[DEBUG] Normalized partial match: '{dept_text}' (normalized: '{normalized_text}') -> '{dept_clean}' (dept: '{dept}')")

        # 중복 제거 (순서 유지)
        unique_departments = []
        for dept in matched_departments:
            if dept not in unique_departments:
                unique_departments.append(dept)

        log.info(f"[DEBUG] Directive {i+1} departments from range Y:{range_start:.1f}-{range_end:.1f}: {unique_departments}")

        directives.append({
            "text": directive_text,
            "departments": unique_departments,
            "y_start": range_start,
            "y_end": range_end
        })

    return directives

def extract_directives_with_departments_old(page, last_col_start: float, known_departments: Set[str]) -> List[Dict]:
    """
    페이지에서 지시사항과 해당 부서를 개별적으로 추출
    """
    # 전체 텍스트를 y좌표와 함께 추출
    text_instances = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") == 0:  # 텍스트 블록
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        text_instances.append({
                            "text": text,
                            "y": bbox[1],  # y 좌표
                            "x": bbox[0],  # x 좌표
                            "bbox": bbox
                        })

    # y좌표로 정렬 (위에서 아래로)
    text_instances.sort(key=lambda x: (x["y"], x["x"]))

    # 연속된 텍스트 조각들을 병합 (같은 Y라인에서 가까운 X좌표)
    merged_instances = []
    current_line = []
    current_y = None

    for item in text_instances:
        # 같은 라인 판단: Y좌표 차이 1pt 이내이고, X좌표도 인접한 경우만 병합
        same_y = (current_y is None or abs(item["y"] - current_y) <= 1.0)

        # X좌표 체크: 이전 텍스트들과 비슷한 영역에 있는지 확인
        same_x_region = True
        if current_line and len(current_line) > 0:
            # 현재 라인의 평균 X좌표 계산
            avg_x = sum(t["x"] for t in current_line) / len(current_line)
            # 새 텍스트가 평균 X좌표에서 200pt 이상 떨어져 있으면 다른 영역
            if abs(item["x"] - avg_x) > 200:
                same_x_region = False

        if same_y and same_x_region:
            current_line.append(item)
            current_y = item["y"]
        else:
            # 라인 병합
            if current_line:
                # 같은 라인의 텍스트들을 X좌표 순으로 정렬하여 병합
                current_line.sort(key=lambda x: x["x"])
                merged_text = " ".join([t["text"] for t in current_line])
                merged_instances.append({
                    "text": merged_text,
                    "y": current_y,
                    "x": current_line[0]["x"],
                    "bbox": current_line[0]["bbox"]
                })
            current_line = [item]
            current_y = item["y"]

    # 마지막 라인 처리
    if current_line:
        current_line.sort(key=lambda x: x["x"])
        merged_text = " ".join([t["text"] for t in current_line])
        merged_instances.append({
            "text": merged_text,
            "y": current_y,
            "x": current_line[0]["x"],
            "bbox": current_line[0]["bbox"]
        })

    text_instances = merged_instances

    # 지시사항 구간과 부서 구간을 분리
    directive_parts = []
    department_parts = []

    for item in text_instances:
        text = item["text"]
        x = item["x"]
        y = item["y"]

        # 부서열인지 본문인지 판단
        is_department_column = x >= last_col_start + DEPT_BOUNDARY_OFFSET
        is_main_content = x <= last_col_start + MAIN_BOUNDARY_OFFSET

        # X좌표 경계 체크 완료

        if is_department_column:
            # 부서열 텍스트 (부서명이 포함된 경우에만)
            normalized_text = re.sub(r'\s+', '', text)
            has_dept = any(dept in text or re.sub(r'\s+', '', dept) in normalized_text for dept in known_departments)
            # "전부서" 특수 처리 - 더 정확한 매칭
            is_all_dept = False
            # 정확한 "전부서" 매칭만 허용 (더 관대하게)
            if (text.strip() in ["전부서", "전 부서", "전 부 서"] or
                re.match(r'^\s*전\s*부\s*서\s*$', text) or
                normalized_text == "전부서" or
                re.search(r'전\s*부\s*서', text)):  # 조금 더 관대한 매칭
                is_all_dept = True
                log.info(f"[DEBUG] '전부서' detected from text: '{text}' (normalized: '{normalized_text}')")
            has_dept = has_dept or is_all_dept

            # 더 유연한 부서명 매칭 - 공백으로 분리된 부서명도 포함
            if not has_dept:
                # 부분 매칭도 시도 (공백으로 분리된 부서명)
                text_without_spaces = re.sub(r'\s+', '', text)
                for dept in known_departments:
                    dept_normalized = re.sub(r'\s+', '', dept)
                    if dept_normalized and (dept_normalized in text_without_spaces or text_without_spaces in dept_normalized):
                        has_dept = True
                        break

            if has_dept:
                department_parts.append({
                    "text": text,
                    "y": y,
                    "x": x
                })
                # 디버깅: 부서열 텍스트 로그
                log.debug(f"Department column text found: '{text}' at Y:{y:.1f}, X:{x:.1f}")
        elif is_main_content:
            # 본문 텍스트
            directive_parts.append({
                "text": text,
                "y": y,
                "x": x
            })

    # 부서들을 Y좌표로 그룹화 (연속된 부서 vs 빈 줄 이후 부서 구분)
    def group_consecutive_departments(dept_parts):
        """연속된 부서들을 그룹으로 묶기"""
        if not dept_parts:
            return []

        # Y좌표로 정렬
        sorted_depts = sorted(dept_parts, key=lambda x: x["y"])

        groups = []
        current_group = [sorted_depts[0]]

        for i in range(1, len(sorted_depts)):
            prev_y = sorted_depts[i-1]["y"]
            curr_y = sorted_depts[i]["y"]

            # Y좌표 차이가 10pt 이하이면 연속된 부서로 간주
            if curr_y - prev_y <= 10:
                current_group.append(sorted_depts[i])
            else:
                # 빈 줄이 있는 경우 새 그룹 시작
                groups.append(current_group)
                current_group = [sorted_depts[i]]

        groups.append(current_group)
        return groups

    # 부서 그룹화
    dept_groups = group_consecutive_departments(department_parts)

    # 디버깅: 부서 그룹 정보 출력
    for i, group in enumerate(dept_groups):
        group_depts = []
        group_texts = []
        for item in group:
            dept_text = item["text"]
            group_texts.append(f"'{dept_text}'")

            # "전부서" 특수 처리 - 더 정확한 매칭
            normalized_text = re.sub(r'\s+', '', dept_text)
            is_all_dept = False

            # 정확한 "전부서" 매칭만 허용
            if (dept_text.strip() in ["전부서", "전 부서", "전 부 서"] or
                re.match(r'^\s*전\s*부\s*서\s*$', dept_text) or
                normalized_text == "전부서"):
                is_all_dept = True

            if is_all_dept:
                group_depts.append("전부서")

            # 일반 부서명
            for dept in known_departments:
                # 정확 매칭
                if dept in dept_text:
                    group_depts.append(dept.replace(" ", ""))
                # 공백 제거 후 매칭
                elif re.sub(r'\s+', '', dept) in normalized_text:
                    group_depts.append(dept.replace(" ", ""))

        group_y_range = f"Y:{min(item['y'] for item in group):.1f}-{max(item['y'] for item in group):.1f}"
        log.info(f"Department Group {i+1}: texts={group_texts}, depts={group_depts} at {group_y_range}")

    # 지시사항별로 그룹화 (○ 기준으로)
    directives = []
    current_directive = []
    current_y_start = None
    current_y_end = None

    for item in directive_parts:
        text = item["text"]
        y = item["y"]

        # 지시사항 시작 (○로 시작)
        if text.startswith('○') or text.lstrip().startswith('○'):
            # 이전 지시사항 저장
            if current_directive:
                # 해당 지시사항에 맞는 모든 관련 부서 그룹 찾기 (개선된 매칭)
                related_depts = []
                candidate_groups = []

                directive_text = ' '.join([d["text"] for d in current_directive])[:100]
                log.info(f"[DEBUG] Processing directive: '{directive_text}...' Y-range: {current_y_start:.1f}-{current_y_end:.1f}")

                for group in dept_groups:
                    group_y_start = min(item["y"] for item in group)
                    group_y_end = max(item["y"] for item in group)

                    # 지시사항 Y 범위와 부서 그룹 Y 범위 비교
                    if current_y_start and current_y_end:
                        directive_bottom = current_y_end
                        directive_top = current_y_start
                        dept_group_top = group_y_start
                        dept_group_bottom = group_y_end

                        # 1. Y 범위가 겹치는 경우 (같은 라인)
                        overlap = not (directive_bottom < dept_group_top or directive_top > dept_group_bottom)

                        # 2. 부서가 지시사항 바로 아래에 있는 경우
                        distance_below = dept_group_top - directive_bottom
                        distance_above = directive_top - dept_group_bottom

                        # 매칭 조건 확장: 겹치거나 가까운 거리에 있는 경우
                        if overlap:
                            priority = 0  # 최우선: 겹치는 경우
                            log.info(f"[DEBUG] Group Y:{group_y_start:.1f}-{group_y_end:.1f} OVERLAPS with directive, priority=0")
                        elif 0 <= distance_below <= 38:  # 지시사항 아래 38pt 이내로 더 엄격하게
                            priority = 1 + distance_below
                            log.info(f"[DEBUG] Group Y:{group_y_start:.1f}-{group_y_end:.1f} BELOW directive by {distance_below:.1f}pt, priority={priority}")
                        elif 0 <= distance_above <= 25:  # 지시사항 위 25pt 이내로 더 엄격하게
                            priority = 1 + distance_above
                            log.info(f"[DEBUG] Group Y:{group_y_start:.1f}-{group_y_end:.1f} ABOVE directive by {distance_above:.1f}pt, priority={priority}")
                        else:
                            log.info(f"[DEBUG] Group Y:{group_y_start:.1f}-{group_y_end:.1f} TOO FAR: below={distance_below:.1f}, above={distance_above:.1f}")
                            continue  # 매칭 조건에 맞지 않음

                        candidate_groups.append({
                            'group': group,
                            'priority': priority,
                            'distance': distance_below if distance_below >= 0 else distance_above
                        })

                # 우선순위로 정렬 (낮은 값이 높은 우선순위)
                candidate_groups.sort(key=lambda x: x['priority'])

                # 상위 후보들에서 부서 추출 (너무 멀리 떨어진 것은 제외)
                for candidate in candidate_groups:
                    if candidate['priority'] > 42:  # 42pt 이상 떨어진 경우 제외 (더 엄격하게)
                        break

                    group = candidate['group']
                    for dept_item in group:
                        dept_text = dept_item["text"]

                        # "전부서", "전 부서" 등 특수 표현 처리 - 더 정확한 매칭
                        normalized_text = re.sub(r'\s+', '', dept_text)
                        is_all_dept = False
                        # 더 관대한 "전부서" 매칭
                        if (dept_text.strip() in ["전부서", "전 부서", "전 부 서"] or
                            re.match(r'^\s*전\s*부\s*서\s*$', dept_text) or
                            normalized_text == "전부서" or
                            re.search(r'전\s*부\s*서', dept_text) or
                            ("전" in dept_text and "부서" in dept_text)):
                            is_all_dept = True
                            log.info(f"[DEBUG] '전부서' matched in directive from text: '{dept_text}' (normalized: '{normalized_text}')")

                        if is_all_dept and "전부서" not in related_depts:
                            related_depts.append("전부서")

                        # 일반 부서명 매칭
                        for dept in known_departments:
                            dept_clean = dept.replace(" ", "")
                            if dept in dept_text and dept_clean not in related_depts:
                                related_depts.append(dept_clean)
                            elif re.sub(r'\s+', '', dept) in normalized_text and dept_clean not in related_depts:
                                related_depts.append(dept_clean)

                # 지시사항 텍스트 결합 및 정리
                directive_text = ' '.join([d["text"] for d in current_directive])
                directive_text = minimal_text_cleanup(directive_text)

                directives.append({
                    "text": directive_text,
                    "departments": list(set(related_depts)),
                    "y_start": current_y_start,
                    "y_end": current_y_end
                })

            # 새 지시사항 시작
            current_directive = [item]
            current_y_start = y
            current_y_end = y
        else:
            # 기존 지시사항에 추가
            if current_directive:
                current_directive.append(item)
                current_y_end = y

    # 마지막 지시사항 저장
    if current_directive:
        # 해당 지시사항에 맞는 모든 관련 부서 그룹 찾기 (개선된 매칭)
        related_depts = []
        candidate_groups = []

        for group in dept_groups:
            group_y_start = min(item["y"] for item in group)
            group_y_end = max(item["y"] for item in group)

            if current_y_start and current_y_end:
                directive_bottom = current_y_end
                directive_top = current_y_start
                dept_group_top = group_y_start
                dept_group_bottom = group_y_end

                # 1. Y 범위가 겹치는 경우 (같은 라인)
                overlap = not (directive_bottom < dept_group_top or directive_top > dept_group_bottom)

                # 2. 부서가 지시사항 바로 아래/위에 있는 경우
                distance_below = dept_group_top - directive_bottom
                distance_above = directive_top - dept_group_bottom

                # 매칭 조건 확장: 겹치거나 가까운 거리에 있는 경우
                if overlap:
                    priority = 0  # 최우선: 겹치는 경우
                elif 0 <= distance_below <= 38:  # 지시사항 아래 38pt 이내로 더 엄격하게
                    priority = 1 + distance_below
                elif 0 <= distance_above <= 25:  # 지시사항 위 25pt 이내로 더 엄격하게
                    priority = 1 + distance_above
                else:
                    continue  # 매칭 조건에 맞지 않음

                candidate_groups.append({
                    'group': group,
                    'priority': priority,
                    'distance': distance_below if distance_below >= 0 else distance_above
                })

        # 우선순위로 정렬 (낮은 값이 높은 우선순위)
        candidate_groups.sort(key=lambda x: x['priority'])

        # 상위 후보들에서 부서 추출 (너무 멀리 떨어진 것은 제외)
        for candidate in candidate_groups:
            if candidate['priority'] > 42:  # 42pt 이상 떨어진 경우 제외 (더 엄격하게)
                break

            group = candidate['group']
            for dept_item in group:
                dept_text = dept_item["text"]

                # "전부서" 특수 처리 - 더 정확한 매칭
                normalized_text = re.sub(r'\s+', '', dept_text)
                is_all_dept = False
                # 더 관대한 "전부서" 매칭
                if (dept_text.strip() in ["전부서", "전 부서", "전 부 서"] or
                    re.match(r'^\s*전\s*부\s*서\s*$', dept_text) or
                    normalized_text == "전부서" or
                    re.search(r'전\s*부\s*서', dept_text) or
                    ("전" in dept_text and "부서" in dept_text)):
                    is_all_dept = True
                    log.info(f"[DEBUG] '전부서' matched in directive from text: '{dept_text}' (normalized: '{normalized_text}')")

                if is_all_dept and "전부서" not in related_depts:
                    related_depts.append("전부서")

                # 일반 부서명 매칭
                for dept in known_departments:
                    dept_clean = dept.replace(" ", "")
                    if dept in dept_text and dept_clean not in related_depts:
                        related_depts.append(dept_clean)
                    elif re.sub(r'\s+', '', dept) in normalized_text and dept_clean not in related_depts:
                        related_depts.append(dept_clean)

        # 마지막 지시사항 텍스트 결합 및 정리
        directive_text = ' '.join([d["text"] for d in current_directive])
        directive_text = minimal_text_cleanup(directive_text)

        directives.append({
            "text": directive_text,
            "departments": list(set(related_depts)),
            "y_start": current_y_start,
            "y_end": current_y_end
        })

    return directives

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
    body_text = []

    for line in body_lines:
        line = line.strip()
        if line:
            # 부서명으로만 구성된 줄은 제외
            if line not in KNOWN_DEPARTMENTS and not all(dept in line for dept in KNOWN_DEPARTMENTS if len(dept) > 2):
                body_text.append(line)

    body = "\n".join(body_text).strip()

    if body:
        # 문장 구조 정리
        body = re.sub(r'\s*([.?!])\s*', r'\1\n', body)
        body = re.sub(r'\n{2,}', '\n', body).strip()

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

        # 새로운 방식: 지시사항과 부서를 개별적으로 추출
        directives_with_depts = extract_directives_with_departments(page, last_col_start, KNOWN_DEPARTMENTS)

        if not directives_with_depts:
            continue

        # 각 지시사항별로 처리
        for directive_data in directives_with_depts:
            directive_text = directive_data["text"]
            matched_departments = directive_data["departments"]

            if not directive_text.strip():
                continue

            current_idx = len(all_records) + 1

            # 처리기한 추출
            deadline = extract_deadline_from_text(directive_text)

            # 날짜 제거된 블록으로 제목/본문 분리
            clean_block = remove_all_dates_from_text(directive_text)
            title, body, title_depts = process_block_content(clean_block)

            # 최종 날짜 제거
            title = remove_all_dates_from_text(title)
            body = remove_all_dates_from_text(body)

            # 최소 텍스트 정제
            title = minimal_text_cleanup(title)
            body = minimal_text_cleanup(body)

            # 다음 지시사항 번호 제거 (예: "231  재건축...")
            # title의 맨 뒤에 붙어있는 다음 지시사항 번호 제거
            title = re.sub(r'\s*\d{3}\s+.*$', '', title).strip()

            # 본문에서 부서명 추출 (예: "토지정보과에서는" 등)
            text_depts = []
            full_text = title + " " + body
            normalized_full_text = re.sub(r'\s+', '', full_text)

            # "전부서" 특수 처리 - 더 정확한 매칭
            is_all_dept = (
                any(phrase in full_text for phrase in ["전부서", "전 부서", "전 부 서"]) or
                re.match(r'.*\s*전\s*부\s*서\s*.*', full_text) or
                normalized_full_text == "전부서"
            )
            if is_all_dept:
                text_depts.append("전부서")
                log.info(f"[DEBUG] '전부서' matched in text extraction from: '{full_text[:100]}...')")

            for dept in KNOWN_DEPARTMENTS:
                # 정확 매칭
                if dept in full_text:
                    text_depts.append(dept.replace(" ", ""))
                # 공백 제거 후 매칭
                elif re.sub(r'\s+', '', dept) in normalized_full_text:
                    text_depts.append(dept.replace(" ", ""))

            # 새로운 ○ 기반 방식으로 이미 정확하게 추출된 부서만 사용
            final_depts = []

            # ○ 기반 방식에서 추출된 부서만 사용 (제목/본문 추가 추출 완전 비활성화)
            if matched_departments:
                final_depts.extend(matched_departments)
                log.info(f"[DEBUG] ○ 기반 방식에서 추출된 부서: {matched_departments}")
            else:
                # 부서열에서 부서가 없을 때만 제목에서 추출
                for dept in title_depts:
                    if dept not in final_depts:
                        final_depts.append(dept)
                log.info(f"[DEBUG] 부서열이 비어있어 제목에서 부서 추출: {title_depts}")

            # ○ 기반 방식을 우선하고, 필요한 경우에만 제목 부서 추가
            if matched_departments:
                # ○ 기반 방식 결과를 기본으로 사용 (가장 정확함)
                final_depts = list(matched_departments)

                # 제목에서 추출한 부서는 추가하지 않음
                # (본문에 언급된 부서명을 제목으로 오인하여 추출하는 문제 방지)
                # for dept in title_depts:
                #     if dept not in final_depts:
                #         final_depts.append(dept)

                log.info(f"[DEBUG] ○ 기반 방식만 사용: ○방식={matched_departments}, 제목={title_depts}(무시), 최종={final_depts}")

            # 본문에서의 추가 부서 추출 완전 비활성화 (○ 기반 방식이 더 정확하므로)
            # if not matched_departments:
            #     for dept in text_depts:
            #         if dept not in final_depts:
            #             final_depts.append(dept)
            #     log.info(f"[DEBUG] 부서열이 비어있어 본문에서 부서 추출: {text_depts}")
            # else:
            #     log.info(f"[DEBUG] 부서열에 부서가 있어 본문 부서 무시: {text_depts}")

            # 중복 제거 (순서 유지)
            seen = set()
            unique_final_depts = []
            for dept in final_depts:
                if dept not in seen:
                    seen.add(dept)
                    unique_final_depts.append(dept)
            final_depts = unique_final_depts

            # 단위 테스트 로깅
            validate_and_log_block(current_idx, title, final_depts, deadline)

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

            # 구조화된 지시사항 텍스트 생성
            structured_directive = ""
            if title:
                structured_directive += f"○ {title}\n"
            if body:
                # 본문을 적절히 포맷팅
                formatted_body = body.strip()
                if formatted_body:
                    # 줄바꿈과 들여쓰기 보존
                    lines = formatted_body.split('\n')
                    formatted_lines = []
                    for line in lines:
                        line = line.strip()
                        if line:
                            if not line.startswith('-'):
                                formatted_lines.append(f"- {line}")
                            else:
                                formatted_lines.append(line)
                    structured_directive += "\n".join(formatted_lines)

            # JSON 레코드 생성
            record = {
                "source_file": source,
                "page": page_num,
                "index": current_idx,
                "category": category,
                "title": title,
                "body": body.replace("- ", "").replace("\n", " ").strip() if body else "",
                "deadline": deadline,
                "departments": final_depts,
                "lang": "ko",
                "doc_type": "gucheong_jisisa",
                "directive": structured_directive.strip()
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