import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from collections import defaultdict, Counter

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from langchain.schema import Document
from langchain_chroma import Chroma
from langchain.embeddings.base import Embeddings

from config import logger, DOCUMENTS_PATH

class KoreanEmbeddings(Embeddings):
    """한국어 특화 임베딩 클래스"""
    
    def __init__(self, model_name: str = "jhgan/ko-sroberta-multitask"):
        """
        한국어 특화 임베딩 모델 초기화
        - jhgan/ko-sroberta-multitask: 한국어 문장 임베딩 최적화
        """
        try:
            self.model = SentenceTransformer(model_name)
            logger.info(f"한국어 임베딩 모델 로드 완료: {model_name}")
        except Exception as e:
            logger.warning(f"한국어 모델 로드 실패, 기본 모델 사용: {e}")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """문서들을 임베딩"""
        try:
            embeddings = self.model.encode(texts, convert_to_tensor=False)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"문서 임베딩 실패: {e}")
            return []
    
    def embed_query(self, text: str) -> List[float]:
        """쿼리를 임베딩"""
        try:
            embedding = self.model.encode([text], convert_to_tensor=False)
            return embedding[0].tolist()
        except Exception as e:
            logger.error(f"쿼리 임베딩 실패: {e}")
            return []

class EnhancedVectorStore:
    """하이브리드 검색을 지원하는 개선된 벡터 스토어"""
    
    def __init__(self, collection_name: str = "enhanced_documents", 
                 persist_directory: str = None):
        """
        벡터 스토어 초기화
        
        Args:
            collection_name: 컬렉션 이름
            persist_directory: 데이터 저장 경로
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory or os.path.join(DOCUMENTS_PATH, "chroma_db")
        
        # 한국어 임베딩 모델 초기화
        self.embeddings = KoreanEmbeddings()
        
        # ChromaDB 클라이언트 초기화
        self._initialize_chroma()
        
        # BM25 및 키워드 검색용 데이터
        self.documents = []  # 원본 문서들
        self.bm25 = None
        self.document_texts = []  # BM25용 토큰화된 텍스트
        
        # TF-IDF 벡터라이저 (키워드 검색용)
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words=None,  # 한국어는 사용자 정의 불용어 사용
            ngram_range=(1, 2)
        )
        self.tfidf_matrix = None
        
        # 검색 성능 추적
        self.search_stats = defaultdict(int)
        
        # 서버 재시작 시 기존 문서들로 BM25 인덱스 재구성
        self._load_existing_documents()
        
        logger.info("개선된 벡터 스토어 초기화 완료")
    
    def _initialize_chroma(self):
        """ChromaDB 초기화"""
        try:
            # ChromaDB 설정
            settings = Settings(
                persist_directory=self.persist_directory,
                anonymized_telemetry=False
            )
            
            # Chroma 벡터 스토어 초기화
            self.vector_store = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory
            )
            
            logger.info(f"ChromaDB 초기화 완료: {self.persist_directory}")
            
        except Exception as e:
            logger.error(f"ChromaDB 초기화 실패: {e}")
            raise
    
    def _load_existing_documents(self):
        """서버 재시작 시 기존 문서들을 로드하여 BM25 인덱스 재구성"""
        try:
            # ChromaDB에서 모든 문서 가져오기
            collection = self.vector_store._collection
            all_data = collection.get()
            
            if not all_data or not all_data.get('documents'):
                logger.info("기존 문서가 없습니다.")
                return
            
            # Document 객체로 변환
            existing_documents = []
            documents = all_data.get('documents', [])
            metadatas = all_data.get('metadatas', [])
            
            for i, doc_text in enumerate(documents):
                metadata = metadatas[i] if i < len(metadatas) else {}
                doc = Document(page_content=doc_text, metadata=metadata)
                existing_documents.append(doc)
            
            if existing_documents:
                # BM25 인덱스 재구성을 위해 문서 리스트 업데이트
                self.documents = existing_documents
                
                # 모든 문서의 텍스트 수집
                all_texts = [doc.page_content for doc in self.documents]
                
                # BM25용 토큰화된 텍스트
                tokenized_texts = [self._preprocess_text_for_bm25(text) for text in all_texts]
                self.document_texts = tokenized_texts
                
                # BM25 인덱스 재구성
                if tokenized_texts:
                    self.bm25 = BM25Okapi(tokenized_texts)
                
                # TF-IDF 매트릭스 재구성
                if all_texts:
                    self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(all_texts)
                
                logger.info(f"기존 문서 로드 및 BM25 인덱스 재구성 완료: {len(existing_documents)}개 문서")
            
        except Exception as e:
            logger.warning(f"기존 문서 로드 실패 (계속 진행): {e}")
            # 실패해도 계속 진행 - 새로운 문서 추가는 정상 동작
    
    def _tokenize_korean(self, text: str) -> List[str]:
        """한국어 텍스트 토큰화"""
        # 한글, 영어, 숫자만 추출
        tokens = re.findall(r'[가-힣a-zA-Z0-9]+', text)
        
        # 2글자 이상의 토큰만 유지
        tokens = [token for token in tokens if len(token) >= 2]
        
        return tokens
    
    def _preprocess_text_for_bm25(self, text: str) -> List[str]:
        """BM25를 위한 텍스트 전처리"""
        # 소문자 변환 및 토큰화
        tokens = self._tokenize_korean(text.lower())
        
        # 불용어 제거
        korean_stopwords = {
            '그것', '그리고', '그러나', '그래서', '그런데', '그렇지만',
            '이것', '이렇게', '이런', '저것', '저렇게', '저런',
            '있다', '없다', '되다', '하다', '이다', '아니다',
            '때문', '경우', '통해', '대해', '위해', '같은', '다른'
        }
        
        filtered_tokens = [token for token in tokens if token not in korean_stopwords]
        
        return filtered_tokens
    
    def add_documents(self, documents: List[Document]) -> List[str]:
        """문서들을 벡터 스토어에 추가"""
        try:
            logger.info(f"{len(documents)}개 문서 추가 시작")
            
            # ChromaDB에 문서 추가
            doc_ids = self.vector_store.add_documents(documents)
            
            # BM25 및 TF-IDF용 데이터 업데이트
            self._update_keyword_search_data(documents)
            
            logger.info(f"문서 추가 완료: {len(doc_ids)}개")
            return doc_ids
            
        except Exception as e:
            logger.error(f"문서 추가 실패: {e}")
            raise
    
    def _update_keyword_search_data(self, new_documents: List[Document]):
        """키워드 검색용 데이터 업데이트"""
        try:
            # 새 문서들을 기존 문서 리스트에 추가
            self.documents.extend(new_documents)
            
            # 모든 문서의 텍스트 수집
            all_texts = [doc.page_content for doc in self.documents]
            
            # BM25용 토큰화된 텍스트
            tokenized_texts = [self._preprocess_text_for_bm25(text) for text in all_texts]
            self.document_texts = tokenized_texts
            
            # BM25 인덱스 재구성
            if tokenized_texts:
                self.bm25 = BM25Okapi(tokenized_texts)
            
            # TF-IDF 매트릭스 재구성
            if all_texts:
                self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(all_texts)
            
            logger.info(f"키워드 검색 데이터 업데이트 완료: {len(self.documents)}개 문서")
            
        except Exception as e:
            logger.error(f"키워드 검색 데이터 업데이트 실패: {e}")
    
    def _rebuild_indexes_from_chromadb(self):
        """ChromaDB의 전체 문서로부터 인덱스 재구성"""
        try:
            # ChromaDB에서 모든 문서 가져오기
            collection = self.vector_store._collection
            all_data = collection.get()
            
            if not all_data or not all_data.get('documents'):
                logger.info("ChromaDB에 문서가 없습니다.")
                self.documents = []
                self.bm25 = None
                self.document_texts = []
                self.tfidf_matrix = None
                return
            
            # Document 객체로 변환
            all_documents = []
            documents = all_data.get('documents', [])
            metadatas = all_data.get('metadatas', [])
            
            for i, doc_text in enumerate(documents):
                metadata = metadatas[i] if i < len(metadatas) else {}
                doc = Document(page_content=doc_text, metadata=metadata)
                all_documents.append(doc)
            
            # 문서 리스트 전체 교체
            self.documents = all_documents
            
            # 모든 문서의 텍스트 수집
            all_texts = [doc.page_content for doc in self.documents]
            
            # BM25용 토큰화된 텍스트
            tokenized_texts = [self._preprocess_text_for_bm25(text) for text in all_texts]
            self.document_texts = tokenized_texts
            
            # BM25 인덱스 재구성
            if tokenized_texts:
                self.bm25 = BM25Okapi(tokenized_texts)
            
            # TF-IDF 매트릭스 재구성
            if all_texts:
                self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(all_texts)
            
            logger.info(f"ChromaDB 기반 인덱스 전체 재구성 완료: {len(all_documents)}개 문서")
            
        except Exception as e:
            logger.error(f"ChromaDB 기반 인덱스 재구성 실패: {e}")
            raise
    
    def hybrid_search(self, query: str, k: int = 10, 
                     vector_weight: float = 0.7, 
                     bm25_weight: float = 0.3) -> List[Document]:
        """
        하이브리드 검색 (벡터 + BM25)
        
        Args:
            query: 검색 쿼리
            k: 반환할 문서 수
            vector_weight: 벡터 검색 가중치
            bm25_weight: BM25 검색 가중치
        """
        try:
            logger.info(f"하이브리드 검색: '{query}' (k={k})")
            
            # 1. 벡터 검색
            vector_results = self._vector_search(query, k * 2)  # 더 많이 검색해서 다양성 확보
            
            # 2. BM25 검색
            bm25_results = self._bm25_search(query, k * 2)
            
            # 3. 결과 병합 및 점수 계산
            combined_results = self._combine_search_results(
                vector_results, bm25_results, 
                vector_weight, bm25_weight
            )
            
            # 4. 상위 k개 반환
            final_results = combined_results[:k]
            
            # 통계 업데이트
            self.search_stats['hybrid_search'] += 1
            
            logger.info(f"하이브리드 검색 완료: {len(final_results)}개 결과")
            return final_results
            
        except Exception as e:
            logger.error(f"하이브리드 검색 실패: {e}")
            return self._vector_search(query, k)  # 폴백: 벡터 검색만
    
    def _vector_search(self, query: str, k: int) -> List[Tuple[Document, float]]:
        """벡터 검색"""
        try:
            # ChromaDB에서 유사도 검색
            results = self.vector_store.similarity_search_with_score(query, k=k)
            
            # (Document, score) 형태로 반환
            return [(doc, 1.0 - score) for doc, score in results]  # 거리를 유사도로 변환
            
        except Exception as e:
            logger.error(f"벡터 검색 실패: {e}")
            return []
    
    def _bm25_search(self, query: str, k: int) -> List[Tuple[Document, float]]:
        """BM25 검색"""
        try:
            if not self.bm25 or not self.documents:
                return []
            
            # 쿼리 토큰화
            query_tokens = self._preprocess_text_for_bm25(query)
            if not query_tokens:
                return []
            
            # BM25 점수 계산
            scores = self.bm25.get_scores(query_tokens)
            
            # 상위 k개 선택
            top_indices = np.argsort(scores)[::-1][:k]
            
            results = []
            for idx in top_indices:
                if idx < len(self.documents) and scores[idx] > 0:
                    results.append((self.documents[idx], float(scores[idx])))
            
            return results
            
        except Exception as e:
            logger.error(f"BM25 검색 실패: {e}")
            return []
    
    def _combine_search_results(self, vector_results: List[Tuple[Document, float]], 
                              bm25_results: List[Tuple[Document, float]],
                              vector_weight: float, bm25_weight: float) -> List[Document]:
        """검색 결과 병합"""
        try:
            # 문서별 점수 집계
            doc_scores = defaultdict(float)
            doc_objects = {}  # 문서 객체 저장용
            
            # 벡터 검색 결과 처리
            max_vector_score = max([score for _, score in vector_results]) if vector_results else 1.0
            for doc, score in vector_results:
                doc_id = id(doc.page_content)  # 문서 내용 기반 고유 ID
                normalized_score = score / max_vector_score if max_vector_score > 0 else 0
                doc_scores[doc_id] += normalized_score * vector_weight
                doc_objects[doc_id] = doc
            
            # BM25 검색 결과 처리
            max_bm25_score = max([score for _, score in bm25_results]) if bm25_results else 1.0
            for doc, score in bm25_results:
                doc_id = id(doc.page_content)
                normalized_score = score / max_bm25_score if max_bm25_score > 0 else 0
                doc_scores[doc_id] += normalized_score * bm25_weight
                doc_objects[doc_id] = doc
            
            # 점수 순으로 정렬
            sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
            
            # Document 객체 반환
            return [doc_objects[doc_id] for doc_id, score in sorted_docs if score > 0]
            
        except Exception as e:
            logger.error(f"검색 결과 병합 실패: {e}")
            return [doc for doc, _ in vector_results]  # 폴백: 벡터 검색 결과만
    
    def semantic_search(self, query: str, k: int = 10, 
                       similarity_threshold: float = 0.3) -> List[Document]:
        """의미적 검색 (벡터 검색만)"""
        try:
            results = self.vector_store.similarity_search_with_score(query, k=k)
            
            # 유사도 임계값 적용
            filtered_results = [
                doc for doc, score in results 
                if (1.0 - score) >= similarity_threshold  # 거리를 유사도로 변환
            ]
            
            self.search_stats['semantic_search'] += 1
            return filtered_results
            
        except Exception as e:
            logger.error(f"의미적 검색 실패: {e}")
            return []
    
    def keyword_search(self, query: str, k: int = 10) -> List[Document]:
        """키워드 검색 (BM25만)"""
        try:
            results = self._bm25_search(query, k)
            documents = [doc for doc, score in results]
            
            self.search_stats['keyword_search'] += 1
            return documents
            
        except Exception as e:
            logger.error(f"키워드 검색 실패: {e}")
            return []
    
    def get_collection_info(self) -> Dict[str, Any]:
        """컬렉션 정보 조회"""
        try:
            collection = self.vector_store._collection
            count = collection.count()
            
            return {
                'collection_name': self.collection_name,
                'document_count': count,
                'bm25_documents': len(self.documents),
                'search_stats': dict(self.search_stats)
            }
        except Exception as e:
            logger.error(f"컬렉션 정보 조회 실패: {e}")
            return {}
    
    def clear_collection(self):
        """컬렉션 초기화"""
        try:
            # ChromaDB 컬렉션 삭제
            self.vector_store.delete_collection()
            
            # 키워드 검색 데이터 초기화
            self.documents = []
            self.bm25 = None
            self.document_texts = []
            self.tfidf_matrix = None
            
            # 벡터 스토어 재초기화
            self._initialize_chroma()
            
            logger.info("컬렉션 초기화 완료")
            
        except Exception as e:
            logger.error(f"컬렉션 초기화 실패: {e}")
            raise
    
    def get_document_by_metadata(self, metadata_filter: Dict[str, Any]) -> List[Document]:
        """메타데이터 기반 문서 검색"""
        try:
            # ChromaDB where 조건으로 필터링
            results = self.vector_store.get(where=metadata_filter)
            
            documents = []
            if results and 'documents' in results:
                for i, doc_text in enumerate(results['documents']):
                    metadata = results['metadatas'][i] if 'metadatas' in results else {}
                    documents.append(Document(page_content=doc_text, metadata=metadata))
            
            return documents
        
        except Exception as e:
            logger.error(f"메타데이터 검색 실패: {e}")
            return [] 