import re
from typing import List, Tuple, Optional
import unicodedata
from rapidfuzz import fuzz
import hashlib

def normalize_korean(text: str) -> str:
    """Normalize Korean text"""
    # Normalize Unicode
    text = unicodedata.normalize('NFKC', text)
    
    # Remove zero-width characters
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def extract_korean_numbers(text: str) -> List[Tuple[str, int]]:
    """Extract Korean number expressions"""
    korean_nums = {
        '영': 0, '일': 1, '이': 2, '삼': 3, '사': 4,
        '오': 5, '육': 6, '칠': 7, '팔': 8, '구': 9,
        '십': 10, '백': 100, '천': 1000, '만': 10000,
        '억': 100000000, '조': 1000000000000
    }
    
    results = []
    pattern = r'[일이삼사오육칠팔구십백천만억조]+'
    
    for match in re.finditer(pattern, text):
        korean_str = match.group()
        try:
            value = parse_korean_number(korean_str, korean_nums)
            results.append((korean_str, value))
        except:
            continue
    
    return results

def parse_korean_number(korean_str: str, korean_nums: dict) -> int:
    """Parse Korean number string to integer"""
    result = 0
    current = 0
    
    for char in korean_str:
        if char in korean_nums:
            num = korean_nums[char]
            
            if num == 10 or num == 100 or num == 1000:
                if current == 0:
                    current = 1
                current *= num
            elif num == 10000 or num == 100000000:
                current = (result + current) * num
                result = 0
            else:
                current = current * 10 + num
    
    return result + current

def split_sentences_korean(text: str) -> List[str]:
    """Split Korean text into sentences"""
    # Korean sentence endings
    endings = r'[.!?。]'
    
    # Split by sentence endings
    sentences = re.split(f'({endings})', text)
    
    # Reconstruct sentences
    result = []
    current = ""
    
    for i, part in enumerate(sentences):
        if re.match(endings, part):
            current += part
            result.append(current.strip())
            current = ""
        else:
            current = part
    
    if current.strip():
        result.append(current.strip())
    
    return [s for s in result if s]

def calculate_text_similarity(text1: str, text2: str, method: str = "ratio") -> float:
    """Calculate similarity between two texts"""
    text1 = normalize_korean(text1)
    text2 = normalize_korean(text2)
    
    if method == "ratio":
        return fuzz.ratio(text1, text2) / 100.0
    elif method == "partial":
        return fuzz.partial_ratio(text1, text2) / 100.0
    elif method == "token_sort":
        return fuzz.token_sort_ratio(text1, text2) / 100.0
    elif method == "token_set":
        return fuzz.token_set_ratio(text1, text2) / 100.0
    else:
        return fuzz.ratio(text1, text2) / 100.0

def extract_legal_references(text: str) -> List[str]:
    """Extract legal references from Korean text"""
    references = []
    
    # Pattern for laws: XX법 제N조
    law_pattern = r'[가-힣]+법\s*제?\s*\d+\s*조'
    references.extend(re.findall(law_pattern, text))
    
    # Pattern for regulations: XX규정 제N조
    reg_pattern = r'[가-힣]+(?:규정|규칙|령)\s*제?\s*\d+\s*조'
    references.extend(re.findall(reg_pattern, text))
    
    # Pattern for articles: 제N조 제N항
    article_pattern = r'제\s*\d+\s*조(?:\s*제\s*\d+\s*항)?'
    references.extend(re.findall(article_pattern, text))
    
    return list(set(references))

def mask_pii(text: str) -> str:
    """Mask PII in Korean text"""
    # Mask phone numbers
    text = re.sub(
        r'(\d{2,3}[-.\s]?\d{3,4}[-.\s]?\d{4})',
        '[전화번호]',
        text
    )
    
    # Mask resident registration numbers
    text = re.sub(
        r'(\d{6}[-\s]?\d{7})',
        '[주민등록번호]',
        text
    )
    
    # Mask email addresses
    text = re.sub(
        r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        '[이메일]',
        text
    )
    
    # Mask credit card numbers
    text = re.sub(
        r'(\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4})',
        '[카드번호]',
        text
    )
    
    return text

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to maximum length"""
    if len(text) <= max_length:
        return text
    
    # Try to truncate at word boundary
    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.8:
        truncated = truncated[:last_space]
    
    return truncated + suffix

def generate_text_hash(text: str) -> str:
    """Generate hash for text"""
    normalized = normalize_korean(text)
    return hashlib.sha256(normalized.encode()).hexdigest()

def highlight_keywords(text: str, keywords: List[str], 
                       start_tag: str = "<mark>", 
                       end_tag: str = "</mark>") -> str:
    """Highlight keywords in text"""
    for keyword in keywords:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        text = pattern.sub(f"{start_tag}{keyword}{end_tag}", text)
    
    return text

def extract_numbers_with_units(text: str) -> List[Tuple[str, str]]:
    """Extract numbers with their units"""
    pattern = r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*([가-힣]+)'
    matches = re.findall(pattern, text)
    
    results = []
    for number, unit in matches:
        # Common Korean units
        common_units = ['원', '명', '개', '건', '년', '월', '일', '시간', '분', '초',
                       '미터', '킬로미터', '그램', '킬로그램', '리터', '평', '톤']
        
        if any(unit.endswith(u) for u in common_units):
            results.append((number, unit))
    
    return results