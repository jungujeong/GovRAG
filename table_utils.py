# 정준구 PDF 정규화 테스트 파일

# table_utils.py
"""
지시사항 셀을 3-단계 계층(날짜->->○)으로 분할해
'부모 항목() + 자식 항목(○)'이 한 행에 담기도록 만든다.
"""

from __future__ import annotations
from typing import List
import re

# ── 분할·인식용 정규식 ──────────────────────────────────────────
DATE_RE = re.compile(r"^【[^】]+】")             #   【YYYY …】
PARENT_BULLETS = ("\uF000", "")                #   최상위 , \uF000
CHILD_BULLETS  = ("○", "●", "□", "◦")          #   하위 ○ 계열
ALL_BULLETS    = PARENT_BULLETS + CHILD_BULLETS
BULLET_SPLIT   = re.compile(
    rf"(?=(?:{'|'.join(map(re.escape, ALL_BULLETS))}))"
)

# ── 헬퍼: 열 개수 맞추기 ────────────────────────────────────────
def pad_row(row: List[str], length: int) -> List[str]:
    """row 의 길이가 length 보다 짧으면 '' 로 패딩."""
    return row + [""] * (length - len(row))

# ── 핵심: 행 분할 +  계층 보존 ─────────────────────────────────
def split_row(
    row: List[str],
    headers: List[str],
    text_idx: int,
) -> List[List[str]]:
    """
    • 지시사항(text_idx) 셀을
        날짜 > (부모) > ○(자식) 3-단계로 분할.
    • ○ 세그먼트에는 **직전에 등장한 (부모) 문구**를 자동으로 앞에 붙인다.
    • 반환값: 분할 완료된 여러 행(List[List[str]])
    """
    text = row[text_idx].replace("\n", " ").strip()

    # ① 날짜 헤더 추출
    date_hdr = ""
    m = DATE_RE.match(text)
    if m:
        date_hdr = m.group(0).strip()
        text = text[len(date_hdr):].lstrip()

    # ② 특수기호 앞에서 토막 내기
    parts = BULLET_SPLIT.split(text)
    # parts 예시: ['', '', ' 당면 …', '○', ' 서부 …', '○', ' 임대 …']
    if parts and parts[0] == '':
        parts = parts[1:]                      # 맨 앞 빈 토막 제거

    parent_ctx = ""                            # 가장 최근  내용
    out_rows: List[List[str]] = []

    i = 0
    while i < len(parts):
        bullet = parts[i]
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        i += 2

        # ── (부모) 세그먼트
        if bullet in PARENT_BULLETS:
            parent_ctx = f"{bullet} {content}".strip()
            full_text = f"{date_hdr} {parent_ctx}".strip()
        # ── ○(자식) 세그먼트
        else:                                   # bullet in CHILD_BULLETS
            prefix = f"{date_hdr} {parent_ctx}".strip()
            full_text = f"{prefix} {bullet} {content}".strip()

        new = row.copy()
        new[text_idx] = full_text
        out_rows.append(new)

    return out_rows
