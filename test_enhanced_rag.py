#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import os
from pathlib import Path
from utils import EnhancedDocumentProcessor, EnhancedVectorStore, EnhancedRAGChain
from config import logger

def test_enhanced_rag_system():
    """개선된 RAG 시스템 종합 테스트"""
    
    print("🚀 개선된 RAG 시스템 테스트 시작")
    print("=" * 80)
    
    # 컴포넌트 초기화
    print("📦 컴포넌트 초기화 중...")
    
    try:
        document_processor = EnhancedDocumentProcessor()
        vector_store = EnhancedVectorStore()
        rag_chain = EnhancedRAGChain(vector_store=vector_store)
        print("✅ 모든 컴포넌트 초기화 완료")
    except Exception as e:
        print(f"❌ 컴포넌트 초기화 실패: {e}")
        return
    
    print("\n" + "=" * 80)
    
    # 테스트 질문들
    test_questions = [
        {
            "category": "🔍 기본 검색 테스트",
            "questions": [
                "정월대보름 달집태우기 행사에 대해 알려주세요",
                "감천문화마을 특별관리지역에 대한 내용은?",
                "홍티예술촌 입주작가 관련 지시사항은 무엇인가요?",
            ]
        },
        {
            "category": "🎯 복합 질문 테스트", 
            "questions": [
                "116호 문서에 포함된 주요 지시사항들을 요약해주세요",
                "체납징수 전담팀과 관련된 모든 정보를 알려주세요",
                "을숙도와 관련된 내용이 있다면 모두 알려주세요",
            ]
        },
        {
            "category": "🚫 관련 없는 질문 테스트",
            "questions": [
                "날씨는 어떤가요?",
                "파이썬 프로그래밍을 어떻게 배우나요?",
                "서울시 정책에 대해 설명해주세요",
            ]
        }
    ]
    
    total_questions = 0
    successful_answers = 0
    response_times = []
    
    # 각 카테고리별 테스트
    for test_case in test_questions:
        category = test_case["category"]
        questions = test_case["questions"]
        
        print(f"\n{category}")
        print("-" * 60)
        
        for i, question in enumerate(questions, 1):
            total_questions += 1
            
            print(f"\n{i}. 질문: {question}")
            
            try:
                # 응답 시간 측정
                start_time = time.time()
                answer = rag_chain.query(question)
                end_time = time.time()
                
                response_time = end_time - start_time
                response_times.append(response_time)
                
                print(f"   답변: {answer}")
                print(f"   ⏱️ 응답시간: {response_time:.2f}초")
                
                # 답변 품질 평가
                if "제공된 문서에서 해당 정보를 찾을 수 없습니다" in answer:
                    if "관련 없는 질문" in category:
                        successful_answers += 1
                        print("   ✅ 품질: 우수 (부적절한 질문 적절히 거부)")
                    else:
                        print("   ⚠️ 품질: 개선 필요 (관련 있는 질문 거부)")
                else:
                    if "관련 없는 질문" not in category:
                        successful_answers += 1
                        print("   ✅ 품질: 우수 (적절한 답변 제공)")
                    else:
                        print("   ⚠️ 품질: 개선 필요 (부적절한 질문에 답변)")
                
                # 출처 확인
                if "📄 출처:" in answer:
                    print("   ✅ 출처: 포함됨")
                else:
                    print("   ⚠️ 출처: 누락됨")
                
                # 신뢰도 확인
                if "🎯 신뢰도:" in answer:
                    print("   ✅ 신뢰도: 표시됨")
                
            except Exception as e:
                print(f"   ❌ 오류 발생: {e}")
                response_times.append(0)
    
    # 성능 통계 출력
    print("\n" + "=" * 80)
    print("📊 테스트 결과 요약")
    print("=" * 80)
    
    print(f"총 질문 수: {total_questions}")
    print(f"성공적인 답변: {successful_answers} ({successful_answers/total_questions*100:.1f}%)")
    
    if response_times:
        avg_response_time = sum(response_times) / len(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        
        print(f"평균 응답시간: {avg_response_time:.2f}초")
        print(f"최소 응답시간: {min_response_time:.2f}초") 
        print(f"최대 응답시간: {max_response_time:.2f}초")
    
    # RAG 체인 성능 통계
    try:
        perf_stats = rag_chain.get_performance_stats()
        print(f"\n🔧 시스템 성능 통계:")
        print(f"   검증된 답변 비율: {perf_stats.get('verification_rate', 0):.1%}")
        print(f"   총 처리된 질의: {perf_stats.get('total_queries', 0)}")
    except Exception as e:
        print(f"성능 통계 조회 실패: {e}")
    
    # 벡터 스토어 정보
    try:
        db_info = vector_store.get_collection_info()
        print(f"\n💾 데이터베이스 정보:")
        print(f"   벡터 문서 수: {db_info.get('document_count', 0)}")
        print(f"   BM25 문서 수: {db_info.get('bm25_documents', 0)}")
        print(f"   검색 통계: {db_info.get('search_stats', {})}")
    except Exception as e:
        print(f"데이터베이스 정보 조회 실패: {e}")
    
    # 개선사항 추천
    print(f"\n💡 개선사항 추천:")
    success_rate = successful_answers / total_questions if total_questions > 0 else 0
    
    if success_rate >= 0.9:
        print("   🎉 시스템이 매우 잘 작동하고 있습니다!")
    elif success_rate >= 0.7:
        print("   ✅ 시스템이 잘 작동하고 있습니다. 소폭 개선 가능")
        print("   - 프롬프트 최적화 고려")
        print("   - 검색 가중치 조정 고려")
    elif success_rate >= 0.5:
        print("   ⚠️ 시스템 개선이 필요합니다.")
        print("   - 문서 전처리 개선")
        print("   - 임베딩 모델 업그레이드")
        print("   - 청크 크기 조정")
    else:
        print("   🚨 시스템에 심각한 문제가 있습니다.")
        print("   - 전체 파이프라인 재검토 필요")
        print("   - 데이터 품질 확인")
        print("   - 모델 설정 재확인")
    
    print("\n" + "=" * 80)
    print("🏁 테스트 완료")

def test_document_processing():
    """문서 처리 성능 테스트"""
    print("\n📄 문서 처리 성능 테스트")
    print("-" * 40)
    
    processor = EnhancedDocumentProcessor()
    
    # data 디렉토리에서 테스트 파일 찾기
    data_dir = Path("data")
    if not data_dir.exists():
        print("⚠️ data 디렉토리가 없습니다. 테스트 스킵.")
        return
    
    test_files = list(data_dir.glob("*.pdf")) + list(data_dir.glob("*.hwp"))
    
    if not test_files:
        print("⚠️ 테스트할 파일이 없습니다.")
        return
    
    for file_path in test_files[:3]:  # 최대 3개 파일만 테스트
        try:
            print(f"\n📄 처리 중: {file_path.name}")
            
            start_time = time.time()
            chunks, summary = processor.process_document(str(file_path))
            end_time = time.time()
            
            processing_time = end_time - start_time
            
            print(f"   ✅ 처리 완료")
            print(f"   📊 청크 수: {len(chunks)}")
            print(f"   ⏱️ 처리 시간: {processing_time:.2f}초")
            print(f"   📋 요약 정보: {summary}")
            
            # 첫 번째 청크 미리보기
            if chunks:
                preview = chunks[0].page_content[:200] + "..." if len(chunks[0].page_content) > 200 else chunks[0].page_content
                print(f"   👀 첫 청크 미리보기: {preview}")
            
        except Exception as e:
            print(f"   ❌ 처리 실패: {e}")

if __name__ == "__main__":
    try:
        # 문서 처리 테스트
        test_document_processing()
        
        # 전체 RAG 시스템 테스트
        test_enhanced_rag_system()
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류: {e}")
        logger.error(f"테스트 실행 오류: {e}") 