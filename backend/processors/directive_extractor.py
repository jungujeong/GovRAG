#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
구청장 지시사항 PDF → 사람읽기용 지시사항 + 부서 매칭 → JSONL (RAG 적재용)
- 본문: page.get_text("text") 기반, '○' 시작 블록만 추출, 문장부호 기준 줄 병합 (원문 숫자/날짜 보존)
- 부서: page.get_text("words") 기반, 첫 페이지에서 열 경계(x) 고정 후, 마지막 열 텍스트에서 화이트리스트 매칭
- 같은 '페이지' 안에서 지시사항 리스트 ↔ 부서 리스트를 순서대로 매칭
"""

import os
import re
import glob
import json
import argparse
import fitz  # PyMuPDF
from itertools import zip_longest

# ============================ 유틸 ============================

def read_dept_list(path: str):
    """부서 화이트리스트 파일 읽기"""
    if not os.path.exists(path): 
        return []
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

def collapse_blank_lines(text: str) -> str:
    """3개 이상 연속 개행 → 2개로 축소"""
    return re.sub(r'\n{3,}', '\n\n', text)

def clean_paragraph_for_reading(text: str) -> str:
    """
    문맥 복원:
    - 문장부호(.,?! 또는 '다') 뒤 개행만 유지, 그 외 개행은 공백으로 병합
    - 빈 괄호 ( ) 제거
    - 도메인 치환: "전 부서 동 는" → "전 부서, 전 동은"
    - 숫자/날짜는 원문 유지(임의 결합/수정 금지)
    """
    text = collapse_blank_lines(text)
    lines = [ln.rstrip() for ln in text.splitlines()]
    out, buf = [], ""
    
    for ln in lines:
        ln = ln.strip()
        if not ln:
            if buf:
                out.append(buf)
                buf = ""
            continue
        
        if buf:
            # 이전 줄이 문장부호로 끝났는지 확인
            if re.search(r'[.?!다]$', buf):
                out.append(buf)
                buf = ln
            else:
                # 문장부호로 끝나지 않으면 공백으로 연결
                buf = (buf + " " + ln).strip()
        else:
            buf = ln
    
    if buf: 
        out.append(buf)
    
    text = "\n".join(out)
    text = re.sub(r'\(\s*\)', '', text)  # 빈 괄호 제거
    text = text.replace("전 부서 동 는", "전 부서, 전 동은")
    return text.strip()

# ===================== 열 경계 탐지/그리드 =====================

HEADER_HINTS = ["일련", "처리", "지시", "기한", "주관", "관련"]

def get_words(page):
    """페이지에서 단어 위치 정보 추출 (x0, y0, x1, y1, text)"""
    return [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words", sort=True)]

def find_header_columns(page, y_top=0, y_bottom=220, min_cols=4):
    """첫 페이지에서 표 헤더를 찾고 열 경계 추출"""
    words = get_words(page)
    if not words: 
        return None
    
    # 상단 영역에서 단어 찾기
    band = [w for w in words if y_top <= w[1] <= y_bottom]
    if not band: 
        return None

    # y-클러스터링으로 라인 구성
    y_tol, lines = 4, []
    for w in sorted(band, key=lambda t: t[1]):
        x0, y0, x1, y1, tx = w
        placed = False
        for ln in lines:
            avg = sum(it[1] for it in ln) / len(ln)
            if abs(y0 - avg) <= y_tol:
                ln.append(w)
                placed = True
                break
        if not placed:
            lines.append([w])

    def has_hints(ln):
        """헤더 힌트 단어 포함 여부 확인"""
        joined = "".join(t[4] for t in ln)
        return any(h in joined for h in HEADER_HINTS)

    # 헤더 라인 찾기
    cand = [ln for ln in lines if len(ln) >= 3]
    header, best = None, -1
    
    # 힌트가 있는 라인 우선
    for ln in cand:
        if not has_hints(ln): 
            continue
        xs = [t[0] for t in ln] + [t[2] for t in ln]
        span = max(xs) - min(xs)
        if span > best: 
            best, header = span, ln
    
    # 힌트가 없으면 가장 긴 라인
    if header is None:
        for ln in cand:
            xs = [t[0] for t in ln] + [t[2] for t in ln]
            span = max(xs) - min(xs)
            if span > best: 
                best, header = span, ln

    if header is None:
        # 기본 5열 분할
        w = page.rect.width
        return [-1e9] + [w * i / 5.0 for i in range(1, 5)] + [1e9]

    # 열 중심점 계산
    centers = sorted(((t[0] + t[2]) / 2) for t in header)
    if len(centers) < min_cols:
        w = page.rect.width
        return [-1e9] + [w * i / 5.0 for i in range(1, 5)] + [1e9]

    # 갭 기반 열 경계 찾기
    gaps = [centers[i] - centers[i-1] for i in range(1, len(centers))]
    sg = sorted(gaps, reverse=True)
    k = max(1, int(len(sg) * 0.4))
    thr = sg[k-1] if sg else 1e9
    
    cuts = []
    for i, g in enumerate(gaps):
        if g >= thr:
            cuts.append((centers[i-1] + centers[i]) / 2)
    
    edges = [-1e9] + sorted(set(cuts)) + [1e9]
    if len(edges) < min_cols:
        w = page.rect.width
        edges = [-1e9] + [w * i / 5.0 for i in range(1, 5)] + [1e9]
    
    return edges

def cluster_rows(words, y_tol=4):
    """단어들을 y 좌표 기준으로 행별로 클러스터링"""
    y0s = sorted(w[1] for w in words)
    refs = []
    for y in y0s:
        if not refs or abs(y - refs[-1]) > y_tol:
            refs.append(y)
    
    rows = [[] for _ in refs]
    for (x0, y0, x1, y1, tx) in words:
        ridx = min(range(len(refs)), key=lambda i: abs(y0 - refs[i]))
        rows[ridx].append((x0, y0, x1, y1, tx))
    
    for r in rows:
        r.sort(key=lambda t: (t[0], t[1]))
    
    return rows

def assign_to_columns(rows, col_edges, y_tol=4):
    """행별 단어를 열에 할당하여 그리드 생성"""
    grid = []
    for r in rows:
        cells = [[] for _ in range(len(col_edges) - 1)]
        for (x0, y0, x1, y1, tx) in r:
            xc = (x0 + x1) / 2
            c = None
            for j in range(len(col_edges) - 1):
                if col_edges[j] <= xc < col_edges[j + 1]:
                    c = j
                    break
            if c is not None:
                cells[c].append((y0, x0, tx))
        
        # 각 셀 내 텍스트 병합
        merged = []
        for cell in cells:
            cell.sort(key=lambda t: (t[0], t[1]))
            lines, cur_y, buf = [], None, []
            for (yy, xx, tx) in cell:
                if cur_y is None or abs(yy - cur_y) <= y_tol:
                    cur_y = yy if cur_y is None else (cur_y + yy) / 2
                    buf.append(tx)
                else:
                    lines.append(" ".join(buf))
                    buf = [tx]
                    cur_y = yy
            if buf: 
                lines.append(" ".join(buf))
            merged.append("\n".join(s.strip() for s in lines if s.strip()))
        
        grid.append(merged)
    
    return grid

# ====================== 본문/부서 추출 ======================

def extract_directives_from_page_text(page_text: str):
    """
    페이지 텍스트 → '○' 시작 블록만 추출 → 문장부호 기준 병합
    (표 머리말/풋터 제거는 '○' 앞부분 무시로 해결)
    """
    page_text = collapse_blank_lines(page_text)
    parts = re.split(r'(?=^\s*○)', page_text, flags=re.M)  # 줄 시작의 ○ 기준
    out = []
    for p in parts:
        p = p.strip()
        if not p.startswith("○"): 
            continue
        out.append(clean_paragraph_for_reading(p))
    return out

def extract_departments_from_last_col(page, col_edges, dept_whitelist):
    """마지막 열에서 부서명 추출 (화이트리스트 매칭)"""
    words = get_words(page)
    if not words: 
        return []
    
    rows = cluster_rows(words, y_tol=4)
    grid = assign_to_columns(rows, col_edges, y_tol=4)
    found = []
    
    for row in grid:
        if not row: 
            continue
        last = (row[-1] or "").strip()
        last = re.sub(r'\s+', ' ', last)  # 공백만 정리
        depts = []
        
        for name in dept_whitelist:
            # 단어 경계 확인하여 정확한 매칭
            if re.search(rf'(?<!\w){re.escape(name)}(?!\w)', last):
                if name not in depts:
                    depts.append(name)
        
        if depts:
            found.append(depts)
    
    return found  # 페이지 내 부서 리스트들 (빈 행은 스킵됨)

# ====================== 메인 파이프라인 ======================

def process_pdf_to_jsonl(pdf_path: str, out_jsonl: str, dept_whitelist):
    """PDF 파일을 처리하여 JSONL 형식으로 출력"""
    doc = fitz.open(pdf_path)
    if len(doc) == 0:
        return

    # 첫 페이지에서 열 경계 고정
    col_edges = find_header_columns(doc[0])
    
    with open(out_jsonl, "w", encoding="utf-8") as out:
        for pidx, page in enumerate(doc, start=1):
            # 1) 지시사항(○ 단위)
            text = page.get_text("text")
            directives = extract_directives_from_page_text(text)

            # 2) 부서(마지막 열)
            page_depts = extract_departments_from_last_col(page, col_edges, dept_whitelist) if col_edges else []

            # 3) 페이지 내 순서 매칭 (길이 다르면 부족분은 빈 리스트)
            for idx, (directive, depts) in enumerate(zip_longest(directives, page_depts, fillvalue=[]), start=1):
                if not directive:  # 드물게 부서행이 더 많을 때
                    directive = "(지시사항 없음)"
                
                rec = {
                    "source_file": os.path.basename(pdf_path),
                    "page": pidx,
                    "index": idx,
                    "directive": directive,
                    "departments": depts,
                    "lang": "ko",
                    "doc_type": "gucheong_jisisa"
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")

def run(pdf_glob: str, out_dir: str, dept_list_path: str):
    """메인 실행 함수"""
    os.makedirs(out_dir, exist_ok=True)
    whitelist = read_dept_list(dept_list_path)
    
    pdf_files = glob.glob(pdf_glob)
    print(f"Found {len(pdf_files)} PDF files matching pattern: {pdf_glob}")
    
    for path in pdf_files:
        if not path.lower().endswith(".pdf"): 
            continue
        
        print(f"Processing: {path}")
        base = os.path.splitext(os.path.basename(path))[0]
        out_jsonl = os.path.join(out_dir, base + ".jsonl")
        
        try:
            process_pdf_to_jsonl(path, out_jsonl, whitelist)
            print(f"  → Saved to: {out_jsonl}")
        except Exception as e:
            print(f"  → Error: {e}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="구청장 지시사항 PDF를 JSONL로 변환")
    ap.add_argument("--pdf_glob", required=True, 
                   help="PDF 파일 glob 패턴 (예: '/data/**/구청장*지시사항*.pdf')")
    ap.add_argument("--out_dir", required=True, 
                   help="출력 JSONL 파일들을 저장할 디렉터리")
    ap.add_argument("--dept_list", required=True, 
                   help="부서 화이트리스트 파일 경로")
    args = ap.parse_args()
    
    run(args.pdf_glob, args.out_dir, args.dept_list)