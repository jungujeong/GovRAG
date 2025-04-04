import os
from langchain.schema import Document
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import FakeEmbeddings
from langchain_ollama import OllamaEmbeddings
from config import (
    VECTOR_DB_PATH, 
    CHUNK_SIZE, 
    CHUNK_OVERLAP,
    EMBEDDING_MODELS,
    logger
)

class VectorStore:
    def __init__(self, vector_db_path=VECTOR_DB_PATH):
        """벡터 저장소 초기화"""
        self.vector_db_path = vector_db_path
        os.makedirs(vector_db_path, exist_ok=True)
        
        # 임베딩 초기화 - 다양한 모델 시도
        self.embeddings = None
        
        # 임베딩 모델 시도 - 순서대로 시도하며 성공하면 중단
        for model_info in EMBEDDING_MODELS:
            try:
                self.embeddings = OllamaEmbeddings(model=model_info["model"])
                # 임베딩 테스트
                test_emb = self.embeddings.embed_query("Test query")
                if len(test_emb) > 0:
                    logger.info(f"{model_info['name']}로 임베딩 초기화 완료")
                    break
            except Exception as e:
                logger.warning(f"{model_info['name']}로 임베딩 초기화 실패: {e}")
        
        # 모든 임베딩 모델 실패 시 FakeEmbeddings 사용
        if self.embeddings is None:
            logger.warning("모든 임베딩 모델이 실패했습니다. 대체 방안으로 FakeEmbeddings를 사용합니다.")
            self.embeddings = FakeEmbeddings(size=384)  # 기본 임베딩 크기
        
        # 텍스트 분할기 초기화
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ".", " ", ""],
            length_function=len
        )
        
        # 벡터 저장소 초기화
        try:
            # Chroma 컬렉션 설정
            client_settings = {
                "chroma_db_impl": "duckdb+parquet",
                "anonymized_telemetry": False,
                "persist_directory": vector_db_path,
            }
            
            # HNSW 인덱스 파라미터 설정
            collection_metadata = {
                "hnsw:space": "cosine",  # 코사인 유사도 사용
                "hnsw:construction_ef": 100,  # 구축 시 탐색 범위
                "hnsw:search_ef": 100,  # 검색 시 탐색 범위
                "hnsw:M": 16,  # 각 노드 당 최대 연결 수
            }
            
            self.vector_db = Chroma(
                persist_directory=vector_db_path,
                embedding_function=self.embeddings,
                collection_metadata=collection_metadata,
            )
            logger.info(f"벡터 저장소 {vector_db_path}에 초기화 완료 (HNSW 파라미터 적용)")
        except Exception as e:
            logger.error(f"벡터 저장소 초기화 오류: {e}")
            
            # 오류 발생 시 기본 파라미터로 재시도
            try:
                logger.info("기본 파라미터로 벡터 저장소 초기화 재시도")
                self.vector_db = Chroma(
                    persist_directory=vector_db_path,
                    embedding_function=self.embeddings
                )
                logger.info(f"벡터 저장소 {vector_db_path}에 기본 파라미터로 초기화 완료")
            except Exception as e2:
                logger.error(f"기본 파라미터로 벡터 저장소 초기화 재시도 오류: {e2}")
                raise
    
    def add_document(self, text, metadata=None):
        """벡터 저장소에 문서 추가"""
        try:
            # 메타데이터 로깅
            source = metadata.get('source', 'unknown') if metadata else 'unknown'
            logger.info(f"문서 '{source}' 추가 시작 (길이: {len(text)} 문자)")
            
            # 문서 내용 분석 (간단한 키워드 추출)
            try:
                import re
                from collections import Counter
                
                # 한글/영어 단어 추출 (2글자 이상)
                words = re.findall(r'[가-힣]{2,}|[a-zA-Z]{2,}', text.lower())
                if words:
                    # 상위 키워드 추출
                    top_keywords = Counter(words).most_common(5)
                    keywords_str = ", ".join([f"{word}" for word, count in top_keywords])
                    logger.info(f"문서 '{source}'의 주요 키워드: {keywords_str}")
            except Exception as e:
                logger.warning(f"문서 내용 분석 실패: {e}")
            
            # 텍스트를 청크로 분할
            text_documents = [Document(page_content=text, metadata=metadata or {})]
            splits = self.text_splitter.split_documents(text_documents)
            
            # 청크가 비어있지 않은지 확인
            if not splits:
                logger.warning(f"문서에서 청크가 생성되지 않았습니다")
                # 최소 하나의 청크 생성
                splits = [Document(page_content=text[:min(len(text), CHUNK_SIZE)], metadata=metadata or {})]
            
            # 청크를 벡터 저장소에 추가
            ids = self.vector_db.add_documents(splits)
            
            # 변경사항 저장 시도 (오류 발생 시 무시)
            try:
                # 일부 Chroma 버전에서는 persist()가 필요할 수 있음
                if hasattr(self.vector_db, 'persist'):
                    self.vector_db.persist()
            except Exception as e:
                logger.warning(f"벡터 저장소 변경사항 저장 시도 중 무시된 오류: {e}")
                # 오류가 발생해도 계속 진행
                pass
            
            logger.info(f"벡터 저장소에 {len(splits)}개 청크 추가 완료 (문서: {source})")
            
            # 현재 벡터 DB 크기 확인
            try:
                collection = self.vector_db._collection
                collection_stats = collection.count()
                logger.info(f"현재 벡터 DB 크기: {collection_stats}개 문서")
            except Exception as e:
                logger.warning(f"벡터 DB 크기 확인 실패: {e}")
            
            return ids
        except Exception as e:
            logger.error(f"벡터 저장소에 문서 추가 오류: {e}")
            raise
    
    def similarity_search(self, query, k=3):
        """유사한 문서 검색"""
        try:
            # 쿼리 정제 - 공백 제거 및 소문자 변환
            query = query.strip()
            
            # 관련 문서 검색 시도
            results = self.vector_db.similarity_search(query, k=k)
            
            # 결과가 있으면 즉시 반환
            if results and len(results) > 0:
                logger.info(f"검색 성공: '{query}'에 대해 {len(results)}개 결과 찾음")
                return results
            
            # 결과가 없으면 실패 기록
            logger.warning(f"검색 결과 없음: '{query}'에 대한 문서를 찾을 수 없음")
            return []
        except Exception as e:
            logger.error(f"벡터 저장소 검색 오류: {e}")
            
            # ChromaDB의 결과 개수 오류 처리 (요청 개수 > 인덱스 크기)
            if "Number of requested results" in str(e) and "is greater than number of elements in index" in str(e):
                # 정확한 인덱스 크기 추출
                import re
                match = re.search(r"number of elements in index (\d+)", str(e))
                
                if match:
                    actual_size = int(match.group(1))
                    logger.info(f"인덱스 크기에 맞게 검색 재시도 (k={actual_size})")
                    
                    try:
                        # 실제 인덱스 크기에 맞게 k 조정
                        results = self.vector_db.similarity_search(query, k=actual_size)
                        return results
                    except Exception as e2:
                        logger.error(f"조정된 k로 검색 실패: {e2}")
            
            try:
                # k 값을 줄여서 재시도
                logger.info(f"k 값을 줄여서 재시도 (k={k} -> k=2)")
                results = self.vector_db.similarity_search(query, k=2)
                return results
            except Exception as e2:
                logger.error(f"벡터 저장소 재시도 검색 오류: {e2}")
                try:
                    # 마지막으로 k=1로 시도
                    logger.info(f"마지막 시도 (k=1)")
                    results = self.vector_db.similarity_search(query, k=1)
                    return results
                except Exception as e3:
                    logger.error(f"최종 검색 시도 오류: {e3}")
                    # 모든 시도 실패 시 빈 결과 반환
                    logger.warning("검색 실패로 빈 결과 반환")
                    return []
    
    def similarity_search_with_score(self, query, k=3):
        """관련성 점수가 포함된 유사 문서 검색"""
        try:
            results = self.vector_db.similarity_search_with_score(query, k=k)
            return results
        except Exception as e:
            logger.error(f"점수 포함 벡터 저장소 검색 오류: {e}")
            try:
                # k 값을 줄여서 재시도
                logger.info(f"k 값을 줄여서 재시도 (k={k} -> k=2)")
                results = self.vector_db.similarity_search_with_score(query, k=2)
                return results
            except Exception as e2:
                logger.error(f"점수 포함 벡터 저장소 재시도 검색 오류: {e2}")
                return []
    
    def get_relevant_documents(self, query, k=4):
        """쿼리에 대한 관련 문서 검색"""
        return self.similarity_search(query, k=k)
    
    def clear(self):
        """벡터 저장소 초기화"""
        try:
            # 더 안정적인 방식으로 컬렉션 초기화
            collection = self.vector_db._collection
            
            # 모든 문서 ID 조회
            results = collection.get()
            ids = results.get('ids', [])
            
            # 데이터가 있는 경우에만 삭제 수행
            if ids and len(ids) > 0:
                logger.info(f"벡터 저장소에서 {len(ids)}개 문서 삭제 중")
                collection.delete(ids=ids)
                
                # 변경사항 저장 시도
                try:
                    # 일부 Chroma 버전에서는 persist()가 필요할 수 있음
                    if hasattr(self.vector_db, 'persist'):
                        self.vector_db.persist()
                except Exception as e:
                    logger.warning(f"벡터 저장소 변경사항 저장 시도 중 무시된 오류: {e}")
                    # 오류가 발생해도 계속 진행
                    pass
            else:
                logger.info("벡터 저장소가 이미 비어 있습니다")
            
            # Chroma 객체 완전히 새로 생성하기 위한 준비
            try:
                # 이전 객체 정리 시도
                if hasattr(self.vector_db, '_client'):
                    if hasattr(self.vector_db._client, 'close'):
                        self.vector_db._client.close()
                
                # 기존 객체 참조 해제
                self.vector_db = None
                
                # 잠시 대기 후 새 객체 생성 (리소스 정리를 위한 시간)
                import time
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"이전 벡터 저장소 객체 정리 오류 (무시됨): {e}")
            
            # HNSW 인덱스 파라미터 설정
            collection_metadata = {
                "hnsw:space": "cosine",  # 코사인 유사도 사용
                "hnsw:construction_ef": 100,  # 구축 시 탐색 범위
                "hnsw:search_ef": 100,  # 검색 시 탐색 범위
                "hnsw:M": 16,  # 각 노드 당 최대 연결 수
            }
            
            # 벡터 DB 재초기화 - 완전히 새로운 객체 생성
            try:
                # 임베딩 모델 재초기화도 시도
                # config에서 가져온 EMBEDDING_MODELS 사용
                for model_info in EMBEDDING_MODELS:
                    try:
                        # 임베딩 재초기화
                        from langchain_community.embeddings import OllamaEmbeddings
                        self.embeddings = OllamaEmbeddings(model=model_info["model"])
                        # 임베딩 테스트
                        test_emb = self.embeddings.embed_query("Test query")
                        if len(test_emb) > 0:
                            logger.info(f"{model_info['name']}로 임베딩 재초기화 완료")
                            break
                    except Exception as e:
                        logger.warning(f"{model_info['name']}로 임베딩 재초기화 실패: {e}")
                
                # 임베딩 모델이 초기화되지 않으면 FakeEmbeddings 사용
                if self.embeddings is None:
                    from langchain_community.embeddings import FakeEmbeddings
                    logger.warning("임베딩 재초기화 실패로 FakeEmbeddings를 사용합니다.")
                    self.embeddings = FakeEmbeddings(size=384)
            
                # Chroma 객체 완전히 새로 생성
                from langchain_chroma import Chroma
                self.vector_db = Chroma(
                    persist_directory=self.vector_db_path,
                    embedding_function=self.embeddings,
                    collection_metadata=collection_metadata
                )
                logger.info("벡터 저장소 완전히 재초기화 완료 (HNSW 파라미터 적용)")
            except Exception as e:
                logger.error(f"벡터 저장소 재초기화 오류: {e}")
            
                # 오류 발생 시 기본 파라미터로 재시도
                try:
                    logger.info("기본 파라미터로 벡터 저장소 재초기화 재시도")
                    from langchain_chroma import Chroma
                    self.vector_db = Chroma(
                        persist_directory=self.vector_db_path,
                        embedding_function=self.embeddings
                    )
                    logger.info("벡터 저장소 기본 파라미터로 재초기화 완료")
                except Exception as e2:
                    logger.error(f"기본 파라미터로 벡터 저장소 재초기화 재시도 오류: {e2}")
                    # 오류가 발생해도 계속 진행
            
            return True
        except Exception as e:
            logger.error(f"벡터 저장소 초기화 오류: {e}")
            return False
    
    def delete_document(self, source_name):
        """소스 이름으로 벡터 저장소에서 문서 삭제"""
        try:
            # ChromaDB에는 메타데이터 기반 삭제 기능이 있음
            # source_name과 일치하는 메타데이터를 가진 모든 문서 삭제
            collection = self.vector_db._collection
            
            # 메타데이터 필터 생성
            where_filter = {"source": source_name}
            
            # 해당 메타데이터를 가진 문서 ID 찾기
            results = collection.get(where=where_filter)
        
            if not results or not results['ids']:
                logger.warning(f"소스가 {source_name}인 문서를 찾을 수 없습니다")
                return False
            
            # 찾은 ID로 문서 삭제
            collection.delete(ids=results['ids'])
            
            # 변경사항 저장 시도 (오류 발생 시 무시)
            try:
                # 일부 Chroma 버전에서는 persist()가 필요할 수 있음
                if hasattr(self.vector_db, 'persist'):
                    self.vector_db.persist()
            except Exception as e:
                logger.warning(f"벡터 저장소 변경사항 저장 시도 중 무시된 오류: {e}")
                # 오류가 발생해도 계속 진행 (이미 삭제는 완료됨)
                pass
            
            logger.info(f"소스가 {source_name}인 {len(results['ids'])}개 청크를 벡터 저장소에서 삭제 완료")
            return True
        except Exception as e:
            logger.error(f"벡터 저장소에서 문서 삭제 오류: {e}")
            return False 