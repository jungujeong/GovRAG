import re
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class NormalizerGovKR:
    """Korean government document text normalizer"""
    
    def __init__(self):
        # Common government abbreviations
        self.abbreviations = {
            "예규": "예산규정",
            "훈령": "훈련령",
            "고시": "고시문",
            "공고": "공고문",
            "지침": "지침서"
        }
        
        # Number normalization patterns
        self.number_patterns = {
            "korean_numbers": {
                "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5,
                "육": 6, "칠": 7, "팔": 8, "구": 9, "십": 10,
                "백": 100, "천": 1000, "만": 10000, "억": 100000000
            },
            "roman_numerals": {
                "Ⅰ": 1, "Ⅱ": 2, "Ⅲ": 3, "Ⅳ": 4, "Ⅴ": 5,
                "Ⅵ": 6, "Ⅶ": 7, "Ⅷ": 8, "Ⅸ": 9, "Ⅹ": 10
            }
        }
    
    def normalize_text(self, text: str) -> str:
        """Apply all normalizations to text"""
        if not text:
            return ""
        
        # Apply normalizations in order
        text = self._normalize_whitespace(text)
        text = self._normalize_dates(text)
        text = self._normalize_numbers(text)
        text = self._normalize_currency(text)
        text = self._normalize_laws(text)
        text = self._normalize_punctuation(text)
        text = self._expand_abbreviations(text)
        
        return text.strip()
    
    def normalize_chunk(self, chunk: Dict) -> Dict:
        """Normalize a chunk dictionary"""
        if "text" in chunk:
            chunk["text"] = self.normalize_text(chunk["text"])
            chunk["normalized"] = True
        return chunk
    
    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace and line breaks"""
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)
        # Remove space between Korean characters and numbers
        text = re.sub(r'([가-힣])\s+(\d)', r'\1\2', text)
        text = re.sub(r'(\d)\s+([가-힣])', r'\1\2', text)
        # Normalize line breaks
        text = re.sub(r'\r\n|\r', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text
    
    def _normalize_dates(self, text: str) -> str:
        """Normalize date formats to ISO format"""
        # Pattern: 2024년 1월 5일 -> 2024-01-05
        text = re.sub(
            r'(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일',
            lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}",
            text
        )
        
        # Pattern: 24.1.5 -> 2024-01-05
        text = re.sub(
            r'(\d{2})\.(\d{1,2})\.(\d{1,2})',
            lambda m: f"20{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}",
            text
        )
        
        # Pattern: 2024/01/05 -> 2024-01-05
        text = re.sub(r'(\d{4})/(\d{2})/(\d{2})', r'\1-\2-\3', text)
        
        return text
    
    def _normalize_numbers(self, text: str) -> str:
        """Normalize number formats"""
        # Add thousand separators: 1000000 -> 1,000,000
        def add_commas(match):
            num = match.group(0)
            return f"{int(num):,}"
        
        text = re.sub(r'\b\d{4,}\b', add_commas, text)
        
        # Normalize percentage: 10% -> 10%
        text = re.sub(r'(\d+)\s*％', r'\1%', text)
        text = re.sub(r'(\d+)\s*퍼센트', r'\1%', text)
        
        # Normalize fractions: 1/2 -> 0.5
        text = re.sub(r'\b1/2\b', '0.5', text)
        text = re.sub(r'\b1/3\b', '0.33', text)
        text = re.sub(r'\b1/4\b', '0.25', text)
        text = re.sub(r'\b3/4\b', '0.75', text)
        
        return text
    
    def _normalize_currency(self, text: str) -> str:
        """Normalize currency formats"""
        # Pattern: 1000원 -> 1,000원
        text = re.sub(
            r'(\d+)\s*원',
            lambda m: f"{int(m.group(1)):,}원",
            text
        )
        
        # Pattern: 천만원 -> 10,000,000원
        korean_amounts = {
            "십만": 100000,
            "백만": 1000000,
            "천만": 10000000,
            "억": 100000000,
            "십억": 1000000000,
            "백억": 10000000000,
            "천억": 100000000000,
            "조": 1000000000000
        }
        
        for korean, number in korean_amounts.items():
            pattern = rf'(\d*)\s*{korean}\s*원'
            def replace_func(match):
                multiplier = int(match.group(1)) if match.group(1) else 1
                amount = multiplier * number
                return f"{amount:,}원"
            text = re.sub(pattern, replace_func, text)
        
        return text
    
    def _normalize_laws(self, text: str) -> str:
        """Normalize law and regulation references"""
        # Pattern: 제 3 조 -> 제3조
        text = re.sub(r'제\s*(\d+)\s*조', r'제\1조', text)
        text = re.sub(r'제\s*(\d+)\s*항', r'제\1항', text)
        text = re.sub(r'제\s*(\d+)\s*호', r'제\1호', text)
        
        # Pattern: 제3조제2항 -> 제3조 제2항
        text = re.sub(r'(제\d+조)(제\d+항)', r'\1 \2', text)
        
        # Normalize law names
        text = re.sub(r'([가-힣]+법)\s+제(\d+)', r'\1 제\2', text)
        text = re.sub(r'([가-힣]+)\s+법률\s+제(\d+)', r'\1법률 제\2', text)
        
        return text
    
    def _normalize_punctuation(self, text: str) -> str:
        """Normalize punctuation marks"""
        # Full-width to half-width
        replacements = {
            '。': '.',
            '、': ',',
            '「': '"',
            '」': '"',
            '『': '"',
            '』': '"',
            '（': '(',
            '）': ')',
            '［': '[',
            '］': ']',
            '｛': '{',
            '｝': '}',
            '：': ':',
            '；': ';',
            '！': '!',
            '？': '?',
            '～': '~',
            '－': '-',
            '＿': '_',
            '／': '/',
            '＼': '\\',
            '＠': '@',
            '＃': '#',
            '＄': '$',
            '％': '%',
            '＆': '&',
            '＊': '*',
            '＋': '+',
            '＝': '=',
            '＜': '<',
            '＞': '>',
            '｜': '|'
        }
        
        for full, half in replacements.items():
            text = text.replace(full, half)
        
        # Remove redundant punctuation
        text = re.sub(r'\.{2,}', '.', text)
        text = re.sub(r',{2,}', ',', text)
        text = re.sub(r'\s+([.,;:!?])', r'\1', text)
        
        return text
    
    def _expand_abbreviations(self, text: str) -> str:
        """Expand common abbreviations"""
        for abbr, full in self.abbreviations.items():
            # Only expand if standalone word
            pattern = rf'\b{re.escape(abbr)}\b'
            text = re.sub(pattern, full, text)
        
        return text
    
    def normalize_query(self, query: str) -> str:
        """Normalize user query for search"""
        query = self.normalize_text(query)
        
        # Additional query-specific normalizations
        # Remove question marks and other query indicators
        query = re.sub(r'[?？]', '', query)
        query = re.sub(r'(무엇|뭐|어떤|어떻게|왜|언제|어디|누가|누구)', '', query)
        query = re.sub(r'(입니까|입니다|인가요|인가|일까요|일까|예요|이에요)', '', query)
        
        # Remove particles that don't affect meaning
        particles = ['은', '는', '이', '가', '을', '를', '에', '에서', '으로', '로', '와', '과']
        for particle in particles:
            query = re.sub(rf'\b{particle}\b', '', query)
        
        # Remove extra spaces from particle removal
        query = re.sub(r'\s+', ' ', query)
        
        return query.strip()