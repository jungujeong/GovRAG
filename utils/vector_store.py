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
        
        # 임베딩 초기화
        self.embeddings = None
        self._initialize_embeddings()
        
        # 텍스트 분할기 초기화
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ".", " ", ""],
            length_function=len
        )
        
        # 벡터 저장소 초기화
        self._initialize_vector_db()
        
        # 초기화 후 벡터 DB 크기 확인 및 로깅
        self._log_db_size()

    def _initialize_embeddings(self):
        """임베딩 모델 초기화"""
        for model_info in EMBEDDING_MODELS:
            try:
                self.embeddings = OllamaEmbeddings(model=model_info["model"])
                # 임베딩 테스트
                test_emb = self.embeddings.embed_query("Test query")
                if len(test_emb) > 0:
                    logger.info(f"{model_info['name']}로 임베딩 초기화 완료")
                    return
            except Exception as e:
                logger.warning(f"{model_info['name']}로 임베딩 초기화 실패: {e}")
        
        # 모든 임베딩 모델 실패 시 FakeEmbeddings 사용
        logger.warning("모든 임베딩 모델이 실패했습니다. 대체 방안으로 FakeEmbeddings를 사용합니다.")
        self.embeddings = FakeEmbeddings(size=384)  # 기본 임베딩 크기
    
    def _initialize_vector_db(self):
        """벡터 DB 초기화"""
        # HNSW 인덱스 파라미터 설정
        collection_metadata = {
            "hnsw:space": "cosine",  # 코사인 유사도 사용
            "hnsw:construction_ef": 100,  # 구축 시 탐색 범위
            "hnsw:search_ef": 100,  # 검색 시 탐색 범위
            "hnsw:M": 16,  # 각 노드 당 최대 연결 수
        }
        
        try:
            self.vector_db = Chroma(
                persist_directory=self.vector_db_path,
                embedding_function=self.embeddings,
                collection_metadata=collection_metadata,
            )
            logger.info(f"벡터 저장소 {self.vector_db_path}에 초기화 완료 (HNSW 파라미터 적용)")
        except Exception as e:
            logger.error(f"벡터 저장소 초기화 오류: {e}")
            
            # 오류 발생 시 기본 파라미터로 재시도
            try:
                logger.info("기본 파라미터로 벡터 저장소 초기화 재시도")
                self.vector_db = Chroma(
                    persist_directory=self.vector_db_path,
                    embedding_function=self.embeddings
                )
                logger.info(f"벡터 저장소 {self.vector_db_path}에 기본 파라미터로 초기화 완료")
            except Exception as e2:
                logger.error(f"기본 파라미터로 벡터 저장소 초기화 재시도 오류: {e2}")
                raise
    
    def _log_db_size(self):
        """벡터 DB 크기 확인 및 로깅"""
        try:
            collection = self.vector_db._collection
            collection_stats = collection.count()
            logger.info(f"벡터 DB 크기: {collection_stats}개 문서")
            if collection_stats == 0:
                logger.warning("벡터 DB가 비어 있습니다. 문서를 추가해야 검색이 가능합니다.")
            return collection_stats
        except Exception as e:
            logger.warning(f"벡터 DB 크기 확인 실패: {e}")
            return 0
    
    def add_document(self, text, metadata=None):
        """벡터 저장소에 문서 추가"""
        try:
            # 메타데이터 처리
            if metadata is None:
                metadata = {}
            source = metadata.get('source', 'unknown')
            logger.info(f"문서 '{source}' 추가 시작 (길이: {len(text)} 문자)")
            
            # 텍스트를 청크로 분할
            text_documents = [Document(page_content=text, metadata=metadata)]
            splits = self.text_splitter.split_documents(text_documents)
            
            # 청크가 비어있지 않은지 확인
            if not splits:
                logger.warning(f"문서에서 청크가 생성되지 않았습니다. 최소 하나의 청크를 생성합니다.")
                splits = [Document(page_content=text[:min(len(text), CHUNK_SIZE)], metadata=metadata)]
            
            # 청크를 벡터 저장소에 추가
            ids = self.vector_db.add_documents(splits)
            
            # 변경사항 저장
            self._persist_changes()
            
            logger.info(f"벡터 저장소에 {len(splits)}개 청크 추가 완료 (문서: {source})")
            
            # 현재 벡터 DB 크기 확인
            self._log_db_size()
            
            return ids
        except Exception as e:
            logger.error(f"벡터 저장소에 문서 추가 오류: {e}")
            raise
    
    def _persist_changes(self):
        """벡터 DB 변경사항 저장"""
        try:
            if hasattr(self.vector_db, 'persist'):
                self.vector_db.persist()
                logger.info("벡터 DB 변경사항 저장 완료")
        except Exception as e:
            logger.warning(f"벡터 DB 변경사항 저장 중 오류 (무시됨): {e}")
    
    def similarity_search(self, query, k=3):
        """유사한 문서 검색"""
        query = query.strip()
        logger.info(f"검색 쿼리: '{query}' (k={k})")
        
        # 먼저 DB 크기 확인
        db_size = self._log_db_size()
        
        # DB가 비어있는 경우
        if db_size == 0:
            logger.error("벡터 DB가 비어 있어 검색할 수 없습니다. 먼저 문서를 추가하세요.")
            return []
        
        # 요청 개수(k)가 DB 크기보다 크면 조정
        if k > db_size:
            logger.warning(f"요청 개수(k={k})가 DB 크기({db_size})보다 큽니다. k={db_size}로 조정합니다.")
            k = db_size
        
        try:
            results = self.vector_db.similarity_search(query, k=k)
            
            if results:
                logger.info(f"검색 성공: '{query}'에 대해 {len(results)}개 결과 찾음")
                return results
            else:
                logger.warning(f"검색 결과 없음: '{query}'에 대한 문서를 찾을 수 없음")
                return []
                
        except Exception as e:
            logger.error(f"벡터 저장소 검색 오류: {e}")
            
            # ChromaDB의 결과 개수 오류 처리
            if "Number of requested results" in str(e) and "is greater than number of elements in index" in str(e):
                # 정확한 인덱스 크기 추출
                import re
                match = re.search(r"number of elements in index (\d+)", str(e))
                
                if match:
                    actual_size = int(match.group(1))
                    logger.info(f"인덱스 크기에 맞게 검색 재시도 (k={actual_size})")
                    
                    if actual_size == 0:
                        logger.error("인덱스에 문서가 없습니다. 먼저 문서를 추가하세요.")
                        return []
                    
                    try:
                        # 실제 인덱스 크기에 맞게 k 조정
                        results = self.vector_db.similarity_search(query, k=actual_size)
                        return results
                    except Exception as e2:
                        logger.error(f"조정된 k로 검색 실패: {e2}")
            
            # k 값을 줄여서 재시도
            try:
                new_k = min(2, db_size)
                if new_k > 0:
                    logger.info(f"k 값을 줄여서 재시도 (k={new_k})")
                    results = self.vector_db.similarity_search(query, k=new_k)
                    return results
            except Exception as e2:
                logger.error(f"k 값 조정 후 검색 실패: {e2}")
            
            # 마지막 시도
            try:
                if db_size > 0:
                    logger.info(f"마지막 시도 (k=1)")
                    results = self.vector_db.similarity_search(query, k=1)
                    return results
            except Exception as e3:
                logger.error(f"최종 검색 시도 실패: {e3}")
            
            logger.error("모든 검색 시도가 실패했습니다.")
            return []
    
    def get_relevant_documents(self, query, k=4):
        """쿼리에 대한 관련 문서 검색"""
        return self.similarity_search(query, k=k)
    
    def clear(self):
        """벡터 저장소 초기화"""
        try:
            # 컬렉션 가져오기
            collection = self.vector_db._collection
            
            # 모든 문서 ID 조회
            results = collection.get()
            ids = results.get('ids', [])
            
            # 데이터가 있는 경우에만 삭제 수행
            if ids and len(ids) > 0:
                logger.info(f"벡터 저장소에서 {len(ids)}개 문서 삭제 중")
                collection.delete(ids=ids)
                self._persist_changes()
            else:
                logger.info("벡터 저장소가 이미 비어 있습니다")
            
            # 벡터 DB 재초기화
            try:
                # 이전 객체 정리
                if hasattr(self.vector_db, '_client'):
                    if hasattr(self.vector_db._client, 'close'):
                        self.vector_db._client.close()
                
                self.vector_db = None
                
                # 잠시 대기 후 새 객체 생성
                import time
                time.sleep(0.5)
                
                # 임베딩 재초기화
                self._initialize_embeddings()
                
                # 벡터 DB 재초기화
                self._initialize_vector_db()
                
                # 크기 확인
                self._log_db_size()
                
                logger.info("벡터 저장소 초기화 완료")
                return True
            except Exception as e:
                logger.error(f"벡터 저장소 재초기화 오류: {e}")
                return False
        except Exception as e:
            logger.error(f"벡터 저장소 초기화 오류: {e}")
            return False
    
    def delete_document(self, source_name):
        """소스 이름으로 벡터 저장소에서 문서 삭제"""
        try:
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
            
            # 변경사항 저장
            self._persist_changes()
            
            logger.info(f"소스가 {source_name}인 {len(results['ids'])}개 청크를 벡터 저장소에서 삭제 완료")
            
            # 현재 DB 크기 확인
            self._log_db_size()
            
            return True
        except Exception as e:
            logger.error(f"벡터 저장소에서 문서 삭제 오류: {e}")
            return False 