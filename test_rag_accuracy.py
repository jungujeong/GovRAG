#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from utils.rag_chain import SimpleRAGChain
import time

def test_rag_accuracy():
    """RAG 시스템 정확도 종합 테스트"""
    
    rag = SimpleRAGChain()
    
    # 테스트 질문들 - 다양한 유형과 난이도
    test_cases = [
        {
            "category": "116호 문서 - 구체적 지시사항",
            "questions": [
                "홍티예술촌 등 입주작가의 지역환경 개선 역할 강화에 대해 알려주세요",
                "노후계획도시 정비사업의 선도지구 지정 노력을 위해 어떤 지시를 했습니까?",
                "관내 기업 제품 등 적극 구매에 대한 지시는 무엇입니까?",
            ]
        },
        {
            "category": "다른 문서들 - 일반 지시사항",
            "questions": [
                "감천문화마을 특별관리지역 지정 용역에 대한 지시사항은?",
                "해피챌린지 사업 추진과 관련된 지시사항을 알려주세요",
                "체납징수를 위한 전담팀 신설에 대해 설명해주세요",
            ]
        },
        {
            "category": "경계 케이스",
            "questions": [
                "정월대보름 달집태우기 행사 지원에 대한 내용은?",
                "을숙도 카페 운영 개선에 대한 지시사항은?",
                "빈집 가림막 설치 등 자치경찰사무 지원에 대해 알려주세요",
            ]
        },
        {
            "category": "관련 없는 질문들",
            "questions": [
                "코로나19 방역 지침에 대해 알려주세요",
                "서울시 정책에 대해 설명해주세요",
                "날씨 정보를 알려주세요",
            ]
        }
    ]
    
    print("=" * 80)
    print("한국어 RAG 시스템 종합 정확도 테스트")
    print("=" * 80)
    print()
    
    total_questions = 0
    accurate_answers = 0
    accurate_sources = 0
    
    for test_case in test_cases:
        category = test_case["category"]
        questions = test_case["questions"]
        
        print(f"📂 {category}")
        print("-" * 60)
        
        for i, question in enumerate(questions, 1):
            total_questions += 1
            
            print(f"{i}. 질문: {question}")
            
            start_time = time.time()
            answer = rag.query(question)
            elapsed = time.time() - start_time
            
            print(f"   답변: {answer}")
            print(f"   응답시간: {elapsed:.2f}초")
            
            # 답변 품질 평가
            if "제공된 문서에서 해당 정보를 찾을 수 없습니다" in answer:
                if category == "관련 없는 질문들":
                    accurate_answers += 1
                    print("   ✅ 답변 정확도: 우수 (관련 없는 질문 적절히 거부)")
                else:
                    print("   ❌ 답변 정확도: 불량 (관련 있는 질문을 거부)")
            else:
                if category != "관련 없는 질문들":
                    accurate_answers += 1
                    print("   ✅ 답변 정확도: 우수 (구체적 답변 제공)")
                else:
                    print("   ❌ 답변 정확도: 불량 (관련 없는 질문에 답변)")
            
            # 출처 정확도 평가 - 완전히 새로운 로직
            if "출처:" in answer:
                sources = answer.split("출처:")[-1].strip()
                print(f"   [디버그] 추출된 출처: '{sources}'")
                
                if category == "116호 문서 - 구체적 지시사항":
                    # 116호 문서 관련 질문은 116호가 포함되어야 함
                    # 다양한 형태로 116호가 표시될 수 있음을 고려
                    has_116 = any(pattern in sources for pattern in [
                        "116호", "제116호", "(제116호)", "116호).hwp", "116호.hwp", "지시사항(제116호)"
                    ])
                    
                    if has_116:
                        accurate_sources += 1
                        print("   ✅ 출처 정확도: 우수 (116호 포함)")
                    else:
                        print(f"   ❌ 출처 정확도: 불량 (116호 누락, 출처: {sources})")
                        
                elif category == "관련 없는 질문들":
                    # 관련 없는 질문에는 출처가 없어야 함
                    print(f"   ❌ 출처 정확도: 불량 (관련 없는 질문에 출처 제공: {sources})")
                else:
                    # 다른 카테고리는 적절한 출처가 있으면 OK
                    if sources.strip():  # 출처가 비어있지 않으면 OK
                        accurate_sources += 1
                        print(f"   ✅ 출처 정확도: 우수 (출처: {sources})")
                    else:
                        print("   ❌ 출처 정확도: 불량 (출처가 비어있음)")
            else:
                if category == "관련 없는 질문들":
                    accurate_sources += 1
                    print("   ✅ 출처 정확도: 우수 (관련 없는 질문에 출처 없음)")
                else:
                    print("   ❌ 출처 정확도: 불량 (출처 누락)")
            
            print()
        
        print()
    
    # 최종 결과
    print("=" * 80)
    print("📊 최종 테스트 결과")
    print("=" * 80)
    print(f"총 질문 수: {total_questions}")
    print(f"답변 정확도: {accurate_answers}/{total_questions} ({accurate_answers/total_questions*100:.1f}%)")
    print(f"출처 정확도: {accurate_sources}/{total_questions} ({accurate_sources/total_questions*100:.1f}%)")
    print(f"전체 정확도: {(accurate_answers + accurate_sources)/(total_questions*2)*100:.1f}%")
    
    if accurate_answers == total_questions and accurate_sources == total_questions:
        print("🎉 모든 테스트 통과! 시스템이 완벽하게 작동합니다.")
    else:
        print("⚠️  일부 테스트 실패. 추가 개선이 필요합니다.")
        
        if accurate_answers < total_questions:
            print(f"   - 답변 정확도 개선 필요: {total_questions - accurate_answers}개 질문")
        if accurate_sources < total_questions:
            print(f"   - 출처 정확도 개선 필요: {total_questions - accurate_sources}개 질문")

if __name__ == "__main__":
    test_rag_accuracy() 