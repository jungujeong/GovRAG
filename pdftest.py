# 정준구 PDF 정규화 테스트 파일




# import pymupdf

# doc = pymupdf.open("C:\coding\GovRAG\data\documents\구청장 지시사항(제056호).pdf")

# page_one = doc[0]

# find = page_one.find_tables()

# table1 = find.tables[0]

# a = table1.extract()

# print(a[1])
# print("----------------------")
# print(a[1][2])
# print("----------------------")
# print(a[1][2][300])




# test_table_utils.py
# -----------------------------------------------------------
# 목적: table_utils 모듈이 '지시사항' 셀을 특수기호로 잘 분할하는지
#       PDF 한 파일로 간단히 확인한다.
# -----------------------------------------------------------

# import fitz                         # PyMuPDF
# from pathlib import Path
# from table_utils import pad_row, split_row   # 새로 만든 모듈

# PDF_PATH = r"C:\coding\GovRAG\data\documents\구청장 지시사항(제056호).pdf"

# def main():
#     # 1) PDF 열기 ― 첫 페이지만 확인
#     doc   = fitz.open(PDF_PATH)
#     page  = doc[0]

#     # 2) 첫 번째 표 추출
#     t     = page.find_tables(strategy="lines").tables[0]
#     rows  = t.extract()
#     headers   = [h.replace("\n", "").strip() for h in rows[0]]
#     col_cnt   = len(headers)
#     text_idx  = headers.index("지시사항") if "지시사항" in headers else 2

#     # 3) 분할 로직 실행 → 새 2-차원 배열 b
#     b = []
#     for raw in rows[1:]:                       # 헤더 제외
#         row = pad_row(raw, col_cnt)            # 열 수 맞추기
#         b.extend(split_row(row, headers, text_idx))

#     doc.close()

#     # 4) 결과 확인
#     print("헤더:", headers, end="\n\n")
#     print("분할 후 행 개수:", len(b))
#     print("---- 첫 3행 미리보기 ----")
#     for r in b[:3]:
#         print(r, end="\n\n")

#     # 5) '컬럼:값' 직렬화 예시 (첫 행)
#     pairs = [f"{headers[i]}:{val.strip()}"
#              for i, val in enumerate(b[0]) if val.strip()]
#     print("직렬화 예시:", ", ".join(pairs))

# if __name__ == "__main__":
#     main()

# test_table_utils_hierarchy.py
# ---------------------------------------------
# 목적: 새 split_row()가
#   날짜 ▸ (부모) ▸ ○(자식) 계층을
#   "부모+자식 한 줄" 로 잘 합쳤는지 확인
# ---------------------------------------------

import fitz
from pathlib import Path
from table_utils import pad_row, split_row          # ← 새 버전

PDF_PATH = r"C:\coding\GovRAG\data\documents\구청장 지시사항(제056호).pdf"

def main():
    doc   = fitz.open(PDF_PATH)
    page  = doc[2]

    # 1) 첫 번째 표 → 행 추출
    t         = page.find_tables(strategy="lines").tables[0]
    rows      = t.extract()
    headers   = [h.replace("\n", "").strip() for h in rows[0]]
    col_cnt   = len(headers)
    text_idx  = headers.index("지시사항") if "지시사항" in headers else 2

    # 2) 분할 & 계층 적용
    b = []
    for raw in rows[1:]:
        row = pad_row(raw, col_cnt)
        b.extend(split_row(row, headers, text_idx))

    doc.close()

    # 3) 결과 검토
    print("헤더:", headers, end="\n\n")
    print("총 행(계층 적용 후):", len(b))
    print("---- 첫 5행 미리보기 ----")
    for r in b[:5]:
        print(r[text_idx])               # 지시사항 열만 출력
        print("---")

    # 4) 직렬화 예시 (첫 행)
    pairs = [f"{headers[i]}:{val.strip()}"
             for i, val in enumerate(b[0]) if val.strip()]
    print("\n직렬화 예시:", ", ".join(pairs))

if __name__ == "__main__":
    main()





