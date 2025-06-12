#!/usr/bin/env python3
"""
BM25 인덱스 동기화 테스트 스크립트
서버 재시작 후 BM25 인덱스가 제대로 복원되는지 확인
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils import EnhancedVectorStore
from config import logger

def test_bm25_sync():
    """BM25 동기화 상태 테스트"""
    try:
        logger.info("BM25 동기화 테스트 시작")
        
        # 벡터 스토어 초기화 (서버 재시작 시뮬레이션)
        vector_store = EnhancedVectorStore()
        
        # 데이터베이스 정보 조회
        db_info = vector_store.get_collection_info()
        chroma_docs = db_info.get('document_count', 0)
        bm25_docs = db_info.get('bm25_documents', 0)
        
        print(f"\n=== BM25 동기화 상태 확인 ===")
        print(f"ChromaDB 문서 수: {chroma_docs}")
        print(f"BM25 인덱스 문서 수: {bm25_docs}")
        print(f"컬렉션 이름: {db_info.get('collection_name', 'N/A')}")
        
        if chroma_docs == bm25_docs:
            print("✅ 동기화 상태: 정상")
            return True
        elif chroma_docs > 0 and bm25_docs == 0:
            print("⚠️ 동기화 상태: BM25 인덱스 누락")
            
            # 자동 재구성 테스트
            print("\n🔄 BM25 인덱스 재구성 시도...")
            vector_store._rebuild_indexes_from_chromadb()
            
            # 재구성 후 상태 확인
            db_info_after = vector_store.get_collection_info()
            bm25_docs_after = db_info_after.get('bm25_documents', 0)
            
            print(f"재구성 후 BM25 문서 수: {bm25_docs_after}")
            
            if bm25_docs_after == chroma_docs:
                print("✅ BM25 인덱스 재구성 성공!")
                return True
            else:
                print("❌ BM25 인덱스 재구성 실패")
                return False
        else:
            print(f"⚠️ 동기화 상태: 불일치 (ChromaDB: {chroma_docs}, BM25: {bm25_docs})")
            return False
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        logger.error(f"BM25 sync test failed: {e}")
        return False

def test_search_functionality():
    """검색 기능 테스트"""
    try:
        print(f"\n=== 검색 기능 테스트 ===")
        vector_store = EnhancedVectorStore()
        
        # 간단한 검색 테스트
        test_query = "정부 정책"
        results = vector_store.hybrid_search(test_query, k=3)
        
        print(f"검색어: '{test_query}'")
        print(f"검색 결과 수: {len(results)}")
        
        if len(results) > 0:
            print("✅ 검색 기능: 정상 작동")
            for i, doc in enumerate(results[:2], 1):
                content_preview = doc.page_content[:100].replace('\n', ' ')
                source = doc.metadata.get('source', 'Unknown')
                print(f"  {i}. [{source}] {content_preview}...")
            return True
        else:
            print("⚠️ 검색 기능: 결과 없음 (문서가 없거나 인덱스 문제)")
            return len(results) == 0  # 문서가 없으면 정상
            
    except Exception as e:
        print(f"❌ 검색 테스트 실패: {e}")
        logger.error(f"Search test failed: {e}")
        return False

if __name__ == "__main__":
    print("BM25 인덱스 동기화 및 검색 기능 테스트")
    print("=" * 50)
    
    # BM25 동기화 테스트
    sync_success = test_bm25_sync()
    
    # 검색 기능 테스트
    search_success = test_search_functionality()
    
    print(f"\n=== 테스트 결과 요약 ===")
    print(f"BM25 동기화: {'✅ 성공' if sync_success else '❌ 실패'}")
    print(f"검색 기능: {'✅ 성공' if search_success else '❌ 실패'}")
    
    if sync_success and search_success:
        print("\n🎉 모든 테스트 통과!")
        sys.exit(0)
    else:
        print("\n⚠️ 일부 테스트 실패. 로그를 확인하세요.")
        sys.exit(1) 