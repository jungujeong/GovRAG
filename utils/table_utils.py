# # table_utils.py
# """
# 표(테이블) 셀 안의 긴 지시사항 문장을
# 특수기호(, ○, ●, □, ◦, -)를 기준으로 "새 행"으로 분할한다.

# • pad_row(row, length)
#     - 열 개수(col_count)를 맞추기 위해 부족한 셀을 '' 로 패딩.

# • split_row(row, headers, text_idx)
#     - row          : 원본 데이터 행 (list[str])
#     - headers      : 컬럼 이름 리스트   (list[str])
#     - text_idx     : 분할 대상 컬럼의 인덱스 (int)
#     - returns      : 분할·패딩이 완료된 행들의 리스트 (list[list[str]])
# """

# from __future__ import annotations

# import re
# from typing import List

# # ── 정규식  ----------------------------------------------------
# BULLET_RE = re.compile(
#     r"(?=(?:\uF000||○|●|□|◦|-))"      # 특수기호 앞 위치에 zero-width 매칭
# )
# DATE_RE = re.compile(r"^【[^】]+】")      # 셀 앞머리 날짜·제목 블록  【 … 】


# # ── 헬퍼 1 : 열 개수 보정  --------------------------------------
# def pad_row(row: List[str], length: int) -> List[str]:
#     """row 의 길이가 length 보다 짧으면 '' 로 패딩해서 길이를 맞춘다."""
#     return row + [""] * (length - len(row))


# # ── 헬퍼 2 : 지시사항 셀 분할  ----------------------------------
# def split_row(
#     row: List[str],
#     headers: List[str],
#     text_idx: int,
# ) -> List[List[str]]:
#     """
#     하나의 row 를 특수기호 기준으로 N 개 행으로 분할한다.
#     * text_idx 열(= 지시사항)을 분할하고,
#     * 나머지 열은 원본 값을 복제한다.
#     """
#     text_raw = row[text_idx].replace("\n", " ").strip()

#     # ① 특수기호 앞에서 분할
#     segments = [seg.strip() for seg in BULLET_RE.split(text_raw) if seg.strip()]
#     if not segments:               # 분할 결과가 없으면 원본 행 그대로 반환
#         return [row]

#     # ② 날짜 블록(【 … 】)을 모든 세그먼트 앞에 붙이기 위해 추출
#     date_hdr = ""
#     if DATE_RE.match(segments[0]):
#         date_hdr = segments.pop(0)

#     # ③ 분할된 세그먼트마다 새 행 생성
#     new_rows: List[List[str]] = []
#     for seg in segments:
#         new = row.copy()                            # 다른 열을 그대로 복제
#         new[text_idx] = (date_hdr + " " + seg).strip()
#         new_rows.append(new)

#     return new_rows

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

