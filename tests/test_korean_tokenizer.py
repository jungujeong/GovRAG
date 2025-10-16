"""
Korean Tokenizer Comparison Test

이 테스트는 기존 정규식 토크나이저와 Kiwi 형태소 분석기의 차이를 보여줍니다.
폐쇄망 환경에서 실행 가능합니다 (외부 API 호출 없음).

실행 방법:
    python tests/test_korean_tokenizer.py
"""

import sys
import re
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

def test_regex_tokenizer():
    """기존 정규식 토크나이저 테스트"""
    print("\n" + "="*80)
    print("1. 기존 정규식 토크나이저 (Regex Tokenizer)")
    print("="*80)

    test_sentences = [
        "제99호 지시사항의 시행일은 언제입니까?",
        "혜진이가 엄청 혼났던 그날 지원이가 여친이랑 헤어진 그날",
        "이 법령은 2024년 10월 1일부터 시행한다",
        "공공기관에서 문서를 작성할 때는 반드시 표준안을 따라야 한다",
    ]

    for sentence in test_sentences:
        # Simple regex tokenization
        tokens = re.findall(r'[가-힣]+|[a-zA-Z]+|[0-9]+', sentence)
        print(f"\n원문: {sentence}")
        print(f"토큰: {tokens}")
        print(f"토큰 수: {len(tokens)}개")


def test_kiwi_tokenizer():
    """Kiwi 형태소 분석기 테스트"""
    print("\n" + "="*80)
    print("2. Kiwi 형태소 분석기 (Morphological Analyzer)")
    print("="*80)

    try:
        from kiwipiepy import Kiwi
        kiwi = Kiwi()
        print("✅ Kiwi 초기화 성공\n")
    except ImportError:
        print("❌ kiwipiepy가 설치되지 않았습니다.")
        print("   설치: pip install kiwipiepy")
        return
    except Exception as e:
        print(f"❌ Kiwi 초기화 실패: {e}")
        return

    test_sentences = [
        "제99호 지시사항의 시행일은 언제입니까?",
        "혜진이가 엄청 혼났던 그날 지원이가 여친이랑 헤어진 그날",
        "이 법령은 2024년 10월 1일부터 시행한다",
        "공공기관에서 문서를 작성할 때는 반드시 표준안을 따라야 한다",
    ]

    # POS tags to extract (nouns, verbs, adjectives)
    extract_pos = {'NNG', 'NNP', 'VV', 'VA', 'MAG', 'SN', 'SL'}

    for sentence in test_sentences:
        result = kiwi.tokenize(sentence)

        # Extract meaningful morphemes
        tokens = []
        pos_info = []

        for morph in result:
            for form, tag, start, end in morph:
                if tag in extract_pos:
                    tokens.append(form)
                    pos_info.append(f"{form}/{tag}")

        print(f"\n원문: {sentence}")
        print(f"형태소 분석: {' '.join(pos_info)}")
        print(f"추출된 토큰: {tokens}")
        print(f"토큰 수: {len(tokens)}개")


def test_search_scenario():
    """실제 검색 시나리오 비교"""
    print("\n" + "="*80)
    print("3. 실제 검색 시나리오 비교")
    print("="*80)

    # 문서 예시
    documents = [
        "본 지시사항은 2024년 10월 1일부터 시행한다.",
        "공공기관 문서 작성 표준안은 2023년에 시행되었다.",
        "법령 개정안이 국회에서 통과되었다.",
    ]

    # 사용자 질의
    query = "시행일은 언제인가?"

    print(f"\n📄 문서 목록:")
    for i, doc in enumerate(documents, 1):
        print(f"   {i}. {doc}")

    print(f"\n🔍 사용자 질의: {query}")

    # 정규식 토크나이저 결과
    print("\n[정규식 토크나이저]")
    query_tokens_regex = set(re.findall(r'[가-힣]+', query))
    print(f"  질의 토큰: {query_tokens_regex}")

    for i, doc in enumerate(documents, 1):
        doc_tokens = set(re.findall(r'[가-힣]+', doc))
        overlap = query_tokens_regex & doc_tokens
        print(f"  문서 {i} 매칭: {overlap} ({len(overlap)}개)")

    # Kiwi 토크나이저 결과
    try:
        from kiwipiepy import Kiwi
        kiwi = Kiwi()

        print("\n[Kiwi 형태소 분석기]")

        # 질의 형태소 분석
        query_result = kiwi.tokenize(query)
        query_tokens_kiwi = set()
        for morph in query_result:
            for form, tag, _, _ in morph:
                if tag in {'NNG', 'NNP', 'VV', 'VA', 'SN'}:
                    query_tokens_kiwi.add(form)

        print(f"  질의 토큰: {query_tokens_kiwi}")

        for i, doc in enumerate(documents, 1):
            doc_result = kiwi.tokenize(doc)
            doc_tokens_kiwi = set()
            for morph in doc_result:
                for form, tag, _, _ in morph:
                    if tag in {'NNG', 'NNP', 'VV', 'VA', 'SN'}:
                        doc_tokens_kiwi.add(form)

            overlap = query_tokens_kiwi & doc_tokens_kiwi
            print(f"  문서 {i} 매칭: {overlap} ({len(overlap)}개)")

        print("\n💡 결과 분석:")
        print("  - 정규식: '시행일'과 '시행한다'를 다른 단어로 취급")
        print("  - Kiwi: '시행일' → '시행', '시행한다' → '시행' (어근 추출) → 매칭 성공")

    except ImportError:
        print("\n[Kiwi 형태소 분석기]")
        print("  ❌ kiwipiepy가 설치되지 않아 비교할 수 없습니다.")


def main():
    """메인 테스트 실행"""
    print("\n" + "#"*80)
    print("# 한국어 BM25 토크나이저 비교 테스트")
    print("# 폐쇄망 환경 호환: ✅ (외부 API 호출 없음)")
    print("#"*80)

    # 1. 정규식 토크나이저 테스트
    test_regex_tokenizer()

    # 2. Kiwi 토크나이저 테스트
    test_kiwi_tokenizer()

    # 3. 검색 시나리오 비교
    test_search_scenario()

    print("\n" + "="*80)
    print("테스트 완료")
    print("="*80)
    print("\n권장 사항:")
    print("  1. pip install kiwipiepy (아직 설치 안 된 경우)")
    print("  2. make index 실행하여 인덱스 재생성")
    print("  3. 기존 대비 검색 정확도 향상 확인")
    print()


if __name__ == "__main__":
    main()
