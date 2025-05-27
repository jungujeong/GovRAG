import os
import hashlib
import json
import time
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import Counter

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

@dataclass
class DocumentMetrics:
    """문서 메트릭"""
    word_count: int = 0
    sentence_count: int = 0
    keyword_density: float = 0.0
    readability_score: float = 0.5
    
    @property
    def quality_score(self) -> float:
        """간단한 품질 점수 계산"""
        # 적절한 길이 (100-2000 단어)
        length_score = 1.0 if 100 <= self.word_count <= 2000 else 0.5
        
        # 문장 구조 (평균 문장 길이 10-30 단어)
        avg_sentence_length = self.word_count / max(self.sentence_count, 1)
        structure_score = 1.0 if 10 <= avg_sentence_length <= 30 else 0.7
        
        # 키워드 밀도 (5-20%)
        density_score = 1.0 if 0.05 <= self.keyword_density <= 0.20 else 0.8
        
        return (length_score + structure_score + density_score + self.readability_score) / 4

class SmartChunker:
    """스마트 청킹 시스템"""
    
    def __init__(self):
        # 기본 청킹 설정
        self.base_chunker = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""],
            length_function=len
        )
        
        # 구조화된 문서용 청킹
        self.structured_chunker = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
            separators=["\n\n\n", "\n\n", "\n", ". ", " "],
            length_function=len
        )
    
    def analyze_document_type(self, text: str) -> str:
        """문서 타입 간단 분석"""
        # 구조화된 문서 패턴
        structured_patterns = [
            r'^\s*\d+\.\s+',  # 번호 목록
            r'^\s*[-*]\s+',   # 불릿 포인트
            r'\|.*\|',        # 테이블
            r'제\d+조',       # 조항
        ]
        
        lines = text.split('\n')
        structured_count = 0
        
        for line in lines:
            for pattern in structured_patterns:
                if re.search(pattern, line):
                    structured_count += 1
                    break
        
        # 30% 이상이 구조화된 패턴이면 구조화된 문서로 분류
        if structured_count / len(lines) > 0.3:
            return "structured"
        
        return "narrative"
    
    def chunk_document(self, text: str, metadata: Dict = None) -> List[Document]:
        """문서 청킹"""
        if metadata is None:
            metadata = {}
        
        # 문서 타입 분석
        doc_type = self.analyze_document_type(text)
        
        # 청킹 방법 선택
        if doc_type == "structured":
            chunker = self.structured_chunker
        else:
            chunker = self.base_chunker
        
        # 문서 생성 및 청킹
        document = Document(page_content=text, metadata=metadata)
        chunks = chunker.split_documents([document])
        
        # 청크 메타데이터 보강
        for i, chunk in enumerate(chunks):
            chunk.metadata.update({
                'chunk_index': i,
                'total_chunks': len(chunks),
                'doc_type': doc_type,
                'chunk_size': len(chunk.page_content),
                'created_at': datetime.now().isoformat()
            })
        
        logger.info(f"{doc_type} 문서를 {len(chunks)}개 청크로 분할")
        return chunks

class DocumentAnalyzer:
    """문서 분석기"""
    
    def analyze_document(self, text: str, metadata: Dict = None) -> DocumentMetrics:
        """문서 분석"""
        if metadata is None:
            metadata = {}
        
        # 기본 통계
        words = re.findall(r'[가-힣a-zA-Z0-9]+', text)
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        word_count = len(words)
        sentence_count = len(sentences)
        
        # 키워드 밀도 계산
        keyword_density = self._calculate_keyword_density(words)
        
        # 가독성 점수 (간단한 버전)
        readability_score = self._calculate_readability(words, sentences)
        
        return DocumentMetrics(
            word_count=word_count,
            sentence_count=sentence_count,
            keyword_density=keyword_density,
            readability_score=readability_score
        )
    
    def _calculate_keyword_density(self, words: List[str]) -> float:
        """키워드 밀도 계산"""
        if not words:
            return 0.0
        
        # 불용어 제거
        stopwords = {'은', '는', '이', '가', '을', '를', '에', '에서', '으로', '로', '하다', '되다', '있다', '없다'}
        meaningful_words = [w for w in words if w not in stopwords and len(w) >= 2]
        
        if not meaningful_words:
            return 0.0
        
        # 고유 단어 비율
        unique_words = set(meaningful_words)
        return len(unique_words) / len(words)
    
    def _calculate_readability(self, words: List[str], sentences: List[str]) -> float:
        """가독성 점수 계산"""
        if not sentences or not words:
            return 0.5
        
        # 평균 문장 길이
        avg_sentence_length = len(words) / len(sentences)
        
        # 적절한 문장 길이 (10-25 단어)
        if 10 <= avg_sentence_length <= 25:
            length_score = 1.0
        elif 5 <= avg_sentence_length <= 35:
            length_score = 0.8
        else:
            length_score = 0.5
        
        # 문장 다양성
        sentence_lengths = [len(s.split()) for s in sentences]
        if len(set(sentence_lengths)) > len(sentence_lengths) * 0.3:
            variety_score = 1.0
        else:
            variety_score = 0.7
        
        return (length_score + variety_score) / 2

class SimpleVectorStore:
    """단순하고 효과적인 벡터 저장소"""
    
    def __init__(self, vector_db_path=VECTOR_DB_PATH):
        """벡터 저장소 초기화"""
        self.vector_db_path = vector_db_path
        os.makedirs(vector_db_path, exist_ok=True)
        
        # 컴포넌트 초기화
        self.chunker = SmartChunker()
        self.analyzer = DocumentAnalyzer()
        
        # 임베딩 초기화
        self.embeddings = None
        self._initialize_embeddings()
        
        # 벡터 저장소 초기화
        self._initialize_vector_db()
        
        # 문서 정보 캐시
        self.document_info = {}
        
        # 성능 메트릭
        self.metrics = {
            'total_documents': 0,
            'total_chunks': 0,
            'avg_quality': 0.0,
            'last_updated': datetime.now()
        }
        
        # 초기 상태 확인
        self._check_db_status()
        
        logger.info("단순 벡터 저장소 초기화 완료")
    
    def _initialize_embeddings(self):
        """임베딩 모델 초기화"""
        for model_info in EMBEDDING_MODELS:
            try:
                self.embeddings = OllamaEmbeddings(model=model_info["model"])
                # 테스트
                test_emb = self.embeddings.embed_query("테스트")
                if len(test_emb) > 0:
                    logger.info(f"임베딩 초기화 완료: {model_info['name']}")
                    return
            except Exception as e:
                logger.warning(f"임베딩 초기화 실패 {model_info['name']}: {e}")
        
        # 모든 모델 실패 시 대체 방안
        logger.warning("모든 임베딩 모델 실패, FakeEmbeddings 사용")
        self.embeddings = FakeEmbeddings(size=384)
    
    def _initialize_vector_db(self):
        """벡터 DB 초기화"""
        try:
            self.vector_db = Chroma(
                persist_directory=self.vector_db_path,
                embedding_function=self.embeddings,
                collection_metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"벡터 저장소 초기화: {self.vector_db_path}")
        except Exception as e:
            logger.error(f"벡터 저장소 초기화 오류: {e}")
            raise
    
    def _check_db_status(self):
        """DB 상태 확인"""
        try:
            collection = self.vector_db._collection
            doc_count = collection.count()
            self.metrics['total_documents'] = doc_count
            
            if doc_count == 0:
                logger.info("벡터 DB가 비어 있습니다")
            else:
                logger.info(f"벡터 DB 상태: {doc_count}개 문서")
                
            return doc_count
        except Exception as e:
            logger.warning(f"DB 상태 확인 실패: {e}")
            return 0
    
    def add_document(self, text: str, metadata: Optional[Dict] = None) -> List[str]:
        """문서 추가"""
        start_time = time.time()
        
        try:
            if metadata is None:
                metadata = {}
            
            source = metadata.get('source', 'unknown')
            logger.info(f"문서 추가: {source} ({len(text)} 문자)")
            
            # 1. 문서 분석
            doc_metrics = self.analyzer.analyze_document(text, metadata)
            quality_score = doc_metrics.quality_score
            
            # 2. 메타데이터 보강
            metadata.update({
                'quality_score': quality_score,
                'word_count': doc_metrics.word_count,
                'sentence_count': doc_metrics.sentence_count,
                'keyword_density': doc_metrics.keyword_density,
                'readability_score': doc_metrics.readability_score,
                'added_at': datetime.now().isoformat()
            })
            
            # 3. 청킹
            chunks = self.chunker.chunk_document(text, metadata)
            
            # 4. 벡터 저장소에 추가
            ids = self.vector_db.add_documents(chunks)
            
            # 5. 정보 캐시 업데이트
            self.document_info[source] = {
                'chunks': len(chunks),
                'quality_score': quality_score,
                'metrics': doc_metrics,
                'added_at': datetime.now().isoformat()
            }
            
            # 6. 메트릭 업데이트
            self.metrics['total_chunks'] += len(chunks)
            self.metrics['last_updated'] = datetime.now()
            
            # 7. 변경사항 저장
            self._persist_changes()
            
            elapsed = time.time() - start_time
            logger.info(f"문서 추가 완료: {len(chunks)}개 청크, 품질: {quality_score:.3f}, {elapsed:.2f}초")
            
            # 8. 상태 업데이트
            self._check_db_status()
            
            return ids
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"문서 추가 오류: {e}, {elapsed:.2f}초")
            raise
    
    def similarity_search(self, query: str, k: int = 4) -> List[Document]:
        """유사도 검색 - 개선된 버전"""
        try:
            logger.info(f"검색 시작: '{query}' (k={k})")
            
            # DB 크기 확인
            db_size = self._check_db_status()
            if db_size == 0:
                logger.warning("벡터 DB가 비어 있습니다")
                return []
            
            # 검색 수행
            k = min(k, db_size)
            
            # 1차 검색 - 더 많은 문서 검색
            search_k = min(k * 2, 20)
            docs = self.vector_db.similarity_search(query, k=search_k)
            
            if not docs:
                logger.warning("검색 결과가 없습니다")
                return []
            
            # 2차 필터링 - 키워드 기반
            filtered_docs = self._filter_by_keywords(docs, query)
            
            # 품질 점수로 정렬
            if filtered_docs:
                filtered_docs.sort(key=lambda x: x.metadata.get('quality_score', 0), reverse=True)
            
            result = filtered_docs[:k]
            logger.info(f"검색 완료: {len(docs)}개 → 필터링 후 {len(filtered_docs)}개 → 최종 {len(result)}개")
            return result
            
        except Exception as e:
            logger.error(f"검색 오류: {e}")
            return []
    
    def _filter_by_keywords(self, docs: List[Document], query: str) -> List[Document]:
        """키워드 기반 문서 필터링"""
        if not docs:
            return []
        
        # 쿼리에서 키워드 추출
        keywords = re.findall(r'[가-힣a-zA-Z0-9]{2,}', query.lower())
        
        if not keywords:
            return docs
        
        scored_docs = []
        for doc in docs:
            doc_text = doc.page_content.lower()
            
            # 키워드 매칭 점수 계산
            matches = sum(1 for keyword in keywords if keyword in doc_text)
            match_ratio = matches / len(keywords) if keywords else 0
            
            # 품질 점수와 결합
            quality_score = doc.metadata.get('quality_score', 0.5)
            final_score = 0.7 * match_ratio + 0.3 * quality_score
            
            # 메타데이터에 점수 저장
            doc.metadata['keyword_match_score'] = match_ratio
            doc.metadata['combined_score'] = final_score
            
            # 최소 매칭이 있는 문서만 포함
            if match_ratio > 0 or quality_score > 0.6:
                scored_docs.append((doc, final_score))
        
        # 점수 기준 정렬
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        return [doc for doc, score in scored_docs]
    
    def hierarchical_search(self, query: str, k: int = 8) -> List[Document]:
        """계층적 검색 - 품질 기반"""
        try:
            logger.info(f"계층적 검색: '{query}' (k={k})")
            
            # 더 많은 문서 검색
            search_k = min(k * 2, 20)
            docs = self.similarity_search(query, k=search_k)
            
            if not docs:
                return []
            
            # 품질 점수로 필터링 및 정렬
            high_quality = [d for d in docs if d.metadata.get('quality_score', 0) >= 0.7]
            medium_quality = [d for d in docs if 0.4 <= d.metadata.get('quality_score', 0) < 0.7]
            low_quality = [d for d in docs if d.metadata.get('quality_score', 0) < 0.4]
            
            # 계층적 선택
            result = []
            
            # 고품질 문서 우선
            result.extend(high_quality[:k//2])
            remaining = k - len(result)
            
            # 중품질 문서 추가
            if remaining > 0:
                result.extend(medium_quality[:remaining])
                remaining = k - len(result)
            
            # 저품질 문서 추가 (필요시)
            if remaining > 0:
                result.extend(low_quality[:remaining])
            
            logger.info(f"계층적 검색 완료: 고품질 {len(high_quality)}, 중품질 {len(medium_quality)}, 저품질 {len(low_quality)}")
            return result[:k]
            
        except Exception as e:
            logger.error(f"계층적 검색 오류: {e}")
            return self.similarity_search(query, k)
    
    def get_relevant_documents(self, query: str, k: int = 4) -> List[Document]:
        """관련 문서 검색 (하위 호환성)"""
        return self.hierarchical_search(query, k)
    
    def clear(self) -> bool:
        """벡터 저장소 초기화"""
        try:
            logger.info("벡터 저장소 초기화 시작")
            
            collection = self.vector_db._collection
            results = collection.get()
            ids = results.get('ids', [])
            
            if ids:
                logger.info(f"{len(ids)}개 문서 삭제 중")
                collection.delete(ids=ids)
                self._persist_changes()
            
            # 캐시 초기화
            self.document_info.clear()
            self.metrics = {
                'total_documents': 0,
                'total_chunks': 0,
                'avg_quality': 0.0,
                'last_updated': datetime.now()
            }
            
            # 벡터 DB 재초기화
            self._initialize_vector_db()
            self._check_db_status()
            
            logger.info("벡터 저장소 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"벡터 저장소 초기화 오류: {e}")
            return False
    
    def delete_document(self, source_name: str) -> bool:
        """문서 삭제"""
        try:
            collection = self.vector_db._collection
            where_filter = {"source": source_name}
            
            results = collection.get(where=where_filter)
            
            if not results or not results['ids']:
                logger.warning(f"문서를 찾을 수 없음: {source_name}")
                return False
            
            collection.delete(ids=results['ids'])
            
            # 캐시에서 제거
            if source_name in self.document_info:
                del self.document_info[source_name]
            
            self._persist_changes()
            
            logger.info(f"문서 삭제 완료: {source_name} ({len(results['ids'])}개 청크)")
            self._check_db_status()
            
            return True
            
        except Exception as e:
            logger.error(f"문서 삭제 오류: {e}")
            return False
    
    def _persist_changes(self):
        """변경사항 저장"""
        try:
            if hasattr(self.vector_db, 'persist'):
                self.vector_db.persist()
        except Exception as e:
            logger.warning(f"변경사항 저장 오류: {e}")
    
    def get_metrics(self) -> Dict:
        """성능 메트릭 반환"""
        return self.metrics.copy()
    
    def get_document_info(self, source_name: str) -> Optional[Dict]:
        """문서 정보 조회"""
        return self.document_info.get(source_name)

# 하위 호환성을 위한 별칭
VectorStore = SimpleVectorStore
EnhancedVectorStore = SimpleVectorStore 