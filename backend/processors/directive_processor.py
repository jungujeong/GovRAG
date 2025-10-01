#!/usr/bin/env python3
"""
PDF 구청장 지시사항 문서 후처리 모듈
테이블 구조를 사람이 읽기 좋은 문맥으로 변환하여 RAG 시스템에 통합
"""

import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Iterable
from itertools import zip_longest
from collections import defaultdict
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class DirectiveProcessor:
    """구청장 지시사항 PDF 처리기"""
    
    def __init__(self, dept_whitelist: List[str] = None):
        """
        Args:
            dept_whitelist: 부서명 화이트리스트
        """
        self.dept_whitelist = dept_whitelist or self._get_default_departments()
        self.column_edges = []
    
    def _get_default_departments(self) -> List[str]:
        """기본 부서 목록"""
        return [
            "경제일자리과", "전부서", "전 부서", "토지정보과", "건축과",
            "문화예술과", "관광진흥과", "총무과", "안전총괄과", 
            "교통행정과", "주차관리과", "자원순환과", "평생교육과",
            "민원여권과", "산림녹지과", "도시재생과", "복지정책과",
            "교육지원과", "건설과", "환경위생과", "세무1과", "세무2과",
            "기획감사실", "행정지원과", "구청장", "부구청장"
        ]
    
    def extract_directives_from_page_text(self, text: str) -> List[str]:
        """
        페이지 텍스트에서 ○로 시작하는 지시사항 블록들을 추출하고 문맥 정리
        
        Args:
            text: 페이지 전체 텍스트
            
        Returns:
            정리된 지시사항 문단 리스트
        """
        # ○로 시작하는 부분으로 분리
        blocks = re.split(r'(?=^\s*○)', text, flags=re.MULTILINE)
        
        directives = []
        for block in blocks:
            block = block.strip()
            if not block or not block.startswith('○'):
                continue
            
            # 3개 이상 연속 개행은 2개로 축소
            block = re.sub(r'\n{3,}', '\n\n', block)
            
            # 문장부호 뒤가 아닌 개행은 공백으로 변환
            lines = block.split('\n')
            processed_lines = []
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    processed_lines.append('')
                    continue
                    
                # 이전 줄이 문장부호로 끝나는지 확인
                if i > 0 and processed_lines[-1]:
                    last_char = processed_lines[-1].rstrip()[-1] if processed_lines[-1].rstrip() else ''
                    if last_char not in '.。!?다':
                        # 문장부호로 끝나지 않으면 이전 줄과 공백으로 연결
                        if processed_lines[-1]:
                            processed_lines[-1] = processed_lines[-1].rstrip() + ' ' + line
                            continue
                
                processed_lines.append(line)
            
            # 재조합
            block = '\n'.join(processed_lines)
            
            # 빈 괄호 제거
            block = re.sub(r'\(\s*\)', '', block)
            
            # 도메인 특화 치환
            block = block.replace('전 부서 동 는', '전 부서, 전 동은')
            
            # 최종 정리
            block = re.sub(r'\s+', ' ', block).strip()
            block = block.replace(' \n ', '\n').replace('\n ', '\n').replace(' \n', '\n')
            
            if block:
                directives.append(block)
        
        return directives
    
    def detect_column_edges_from_header(self, page) -> List[float]:
        """
        첫 페이지의 표 머리말에서 열 경계 x좌표 검출
        
        Args:
            page: PyMuPDF 페이지 객체
            
        Returns:
            열 경계 x좌표 리스트
        """
        words = page.get_text("words", sort=True)
        if not words:
            # 폴백: 페이지 폭 5등분
            page_width = page.rect.width
            return [page_width * i / 5 for i in range(1, 5)]
        
        # 상단 영역(y < 220)에서 헤더 찾기
        header_words = [w for w in words if w[3] < 220]  # y1 < 220
        
        if not header_words:
            # 폴백
            page_width = page.rect.width
            return [page_width * i / 5 for i in range(1, 5)]
        
        # y좌표로 클러스터링하여 행 구성
        rows_by_y = defaultdict(list)
        for word in header_words:
            y_center = (word[1] + word[3]) / 2
            # 근접한 y값끼리 그룹핑 (허용 오차 5pt)
            found = False
            for y_key in list(rows_by_y.keys()):
                if abs(y_center - y_key) < 5:
                    rows_by_y[y_key].append(word)
                    found = True
                    break
            if not found:
                rows_by_y[y_center].append(word)
        
        # 헤더 키워드를 포함하는 행 찾기
        header_keywords = ['일련', '처리', '지시', '기한', '주관', '관련']
        best_row = None
        best_score = 0
        
        for y_key, row_words in rows_by_y.items():
            row_text = ' '.join([w[4] for w in row_words])
            score = sum(1 for kw in header_keywords if kw in row_text)
            if score > best_score:
                best_score = score
                best_row = row_words
        
        if not best_row or best_score < 3:
            # 헤더를 찾지 못함, 폴백
            page_width = page.rect.width
            return [page_width * i / 5 for i in range(1, 5)]
        
        # x좌표 정렬하여 간격 계산
        best_row.sort(key=lambda w: w[0])  # x0로 정렬
        x_centers = [(w[0] + w[2]) / 2 for w in best_row]
        
        # 연속된 단어 간 간격 계산
        gaps = []
        for i in range(len(x_centers) - 1):
            gap = x_centers[i + 1] - x_centers[i]
            gaps.append((gap, (x_centers[i] + x_centers[i + 1]) / 2))
        
        if not gaps:
            page_width = page.rect.width
            return [page_width * i / 5 for i in range(1, 5)]
        
        # 큰 간격 상위 40%를 경계로 설정
        gaps.sort(key=lambda x: x[0], reverse=True)
        num_edges = max(1, int(len(gaps) * 0.4))
        edges = sorted([g[1] for g in gaps[:num_edges]])
        
        return edges if edges else [page.rect.width / 2]
    
    def rows_to_grid(self, words: List, col_edges: List[float]) -> List[List[str]]:
        """
        단어들을 행/열 그리드로 변환
        
        Args:
            words: PyMuPDF words 리스트
            col_edges: 열 경계 x좌표
            
        Returns:
            행별 열 텍스트 2차원 리스트
        """
        if not words:
            return []
        
        # y좌표로 클러스터링하여 행 구성
        rows_by_y = defaultdict(list)
        for word in words:
            y_center = (word[1] + word[3]) / 2
            # 근접한 y값끼리 그룹핑 (허용 오차 10pt)
            found = False
            for y_key in list(rows_by_y.keys()):
                if abs(y_center - y_key) < 10:
                    rows_by_y[y_key].append(word)
                    found = True
                    break
            if not found:
                rows_by_y[y_center].append(word)
        
        # y좌표 순으로 정렬
        sorted_rows = sorted(rows_by_y.items(), key=lambda x: x[0])
        
        grid = []
        for _, row_words in sorted_rows:
            # x좌표로 정렬
            row_words.sort(key=lambda w: w[0])
            
            # 열 경계에 따라 분류
            num_cols = len(col_edges) + 1
            cols = [[] for _ in range(num_cols)]
            
            for word in row_words:
                x_center = (word[0] + word[2]) / 2
                # 어느 열에 속하는지 결정
                col_idx = 0
                for i, edge in enumerate(col_edges):
                    if x_center > edge:
                        col_idx = i + 1
                    else:
                        break
                
                if col_idx < num_cols:
                    cols[col_idx].append(word[4])  # 텍스트만 추가
            
            # 각 열의 텍스트를 공백으로 연결
            row_texts = [' '.join(col).strip() for col in cols]
            grid.append(row_texts)
        
        return grid
    
    def extract_departments_from_last_col(
        self, 
        page, 
        col_edges: List[float], 
        whitelist: List[str]
    ) -> List[List[str]]:
        """
        페이지의 마지막 열에서 부서명 추출
        
        Args:
            page: PyMuPDF 페이지 객체
            col_edges: 열 경계 x좌표
            whitelist: 부서명 화이트리스트
            
        Returns:
            행별 부서명 리스트 (순서 유지, 빈 리스트 포함)
        """
        words = page.get_text("words", sort=True)
        if not words or not whitelist:
            return []
        
        grid = self.rows_to_grid(words, col_edges)
        if not grid:
            return []
        
        # 각 행의 마지막 열에서 부서명 찾기
        departments_by_row = []
        for row in grid:
            if not row:
                departments_by_row.append([])
                continue
            
            last_col_text = row[-1] if row else ''
            found_depts = []
            
            # 화이트리스트에서 정확히 일치하는 부서명 찾기
            for dept in whitelist:
                if dept in last_col_text:
                    found_depts.append(dept)
            
            # 중복 제거하되 순서 유지
            unique_depts = []
            for dept in found_depts:
                if dept not in unique_depts:
                    unique_depts.append(dept)
            
            departments_by_row.append(unique_depts)
        
        # 부서가 있는 행만 추출 (빈 행 제거)
        dept_rows = [deps for deps in departments_by_row if deps]
        
        return dept_rows
    
    def process_pdf_to_structured_data(self, pdf_path: str) -> Dict:
        """
        PDF를 RAG 시스템용 구조화된 데이터로 변환
        
        Returns:
            {
                "doc_id": str,
                "file_path": str,
                "pages": List[Dict],  # 각 페이지별 지시사항
                "metadata": Dict
            }
        """
        pdf_path = Path(pdf_path)
        doc = fitz.open(str(pdf_path))
        
        result = {
            "doc_id": pdf_path.name,  # Use name instead of stem to include extension
            "file_path": str(pdf_path),
            "pages": [],
            "directives": [],  # 구조화된 지시사항 리스트
            "metadata": {
                "doc_type": "gucheong_jisisa",
                "total_pages": len(doc)
            }
        }
        
        try:
            # 첫 페이지에서 열 경계 검출
            if len(doc) > 0:
                self.column_edges = self.detect_column_edges_from_header(doc[0])
                logger.info(f"Detected column edges: {self.column_edges}")
            
            # 각 페이지 처리
            for page_num, page in enumerate(doc, start=1):
                # 지시사항 추출
                text = page.get_text("text")
                directives = self.extract_directives_from_page_text(text)
                
                # 부서 추출
                page_depts = self.extract_departments_from_last_col(
                    page, self.column_edges, self.dept_whitelist
                )
                
                # 페이지 데이터
                page_data = {
                    "page_num": page_num,
                    "text": "",  # 전체 텍스트는 지시사항들로 구성
                    "directives": []
                }
                
                # 순서 매칭
                all_directives_text = []
                for idx, (directive, departments) in enumerate(
                    zip_longest(directives, page_depts, fillvalue=[]), 
                    start=1
                ):
                    if not directive:
                        continue
                    
                    # 부서 정보를 지시사항에 통합
                    if departments:
                        directive_with_dept = f"{directive}\n담당부서: {', '.join(departments)}"
                    else:
                        directive_with_dept = directive
                    
                    all_directives_text.append(directive_with_dept)
                    
                    # 구조화된 지시사항 저장
                    directive_info = {
                        "page": page_num,
                        "index": idx,
                        "text": directive,
                        "departments": departments,
                        "full_text": directive_with_dept
                    }
                    page_data["directives"].append(directive_info)
                    result["directives"].append(directive_info)
                
                # 페이지 전체 텍스트 구성
                page_data["text"] = "\n\n".join(all_directives_text)
                result["pages"].append(page_data)
                    
        finally:
            doc.close()
        
        return result