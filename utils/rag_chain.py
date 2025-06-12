import time
import hashlib
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter, defaultdict
import numpy as np

from langchain.prompts import PromptTemplate
from langchain_ollama import OllamaLLM
from langchain.schema.output_parser import StrOutputParser
from langchain.schema import Document

from .vector_store import EnhancedVectorStore
from config import (
    OLLAMA_MODEL, 
    OLLAMA_BASE_URL, 
    TEMPERATURE,
    logger
)

class SimpleRAGChain:
    """단순하고 효과적인 RAG 체인"""
    
    def __init__(self, vector_store=None, max_documents=20):
        """RAG 체인 초기화"""
        # 벡터 스토어 설정
        if vector_store is None:
            self.vector_store = EnhancedVectorStore()
        else:
            self.vector_store = vector_store
        
        self.max_documents = max_documents
        
        # LLM 초기화
        self._initialize_llms()
        
        # 프롬프트 초기화
        self._initialize_prompts()
        
        # 체인 설정
        self._setup_chains()
        
        # 간단한 캐시 (최근 10개 질문만)
        self.query_cache = {}
        self.max_cache_size = 10
        
        # 출처 신뢰도 추적
        self.source_reliability = defaultdict(lambda: {'score': 0.5, 'count': 0})
        
        logger.info("단순 RAG 체인 초기화 완료")
    
    def _initialize_llms(self):
        """LLM 초기화"""
        try:
            self.llm = OllamaLLM(
                model=OLLAMA_MODEL,
                base_url=OLLAMA_BASE_URL,
                temperature=TEMPERATURE
            )
            logger.info(f"LLM 초기화 완료: {OLLAMA_MODEL}")
        except Exception as e:
            logger.error(f"LLM 초기화 오류: {e}")
            raise
        
    def _initialize_prompts(self):
        """프롬프트 초기화 - 한국어 특화 개선"""
        # 메인 QA 프롬프트 - 한국어 특화 개선
        self.qa_prompt = PromptTemplate.from_template(
            """당신은 한국어 문서 전문 분석 AI입니다. 제공된 문서를 정확히 분석하여 질문에 답변해주세요.

📋 질문: {question}

📄 관련 문서:
{context}

📌 답변 작성 규칙:
1. 문서에 명시된 내용만을 근거로 정확히 답변하세요
2. 문서에서 직접 인용할 수 있는 구체적인 내용을 포함하세요
3. 추측이나 일반적인 지식으로 답변하지 마세요
4. 문서에 관련 정보가 없으면 "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 명확히 답변하세요
5. 답변은 한국어로 자연스럽고 정확하게 작성하세요

💬 답변:"""
        )
        
        # 요약 프롬프트 - 한국어 특화 개선
        self.summarize_prompt = PromptTemplate.from_template(
            """다음 한국어 문서를 정확하고 간결하게 요약해주세요.

📄 문서 내용:
{document}

📌 요약 규칙:
- 3-5문장으로 핵심 내용 요약
- 중요한 키워드와 주요 정보 포함
- 한국어 문법에 맞는 자연스러운 문체 사용
- 원문의 의미를 정확히 전달

📝 요약:"""
        )
    
    def _setup_chains(self):
        """체인 설정"""
        self.qa_chain = self.qa_prompt | self.llm | StrOutputParser()
        self.summarize_chain = self.summarize_prompt | self.llm | StrOutputParser()
    
    def _clean_response(self, response: str) -> str:
        """응답에서 think 태그 제거"""
        if not response:
            return response
        
        # <think>...</think> 태그와 내용을 모두 제거
        cleaned = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL | re.IGNORECASE)
        
        # 연속된 공백이나 줄바꿈 정리
        cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)
        cleaned = re.sub(r'^\s+|\s+$', '', cleaned, flags=re.MULTILINE)
        
        return cleaned.strip()
    
    def _check_db_status(self) -> int:
        """벡터 DB 상태 확인"""
        try:
            if hasattr(self.vector_store, '_check_db_status'):
                return self.vector_store._check_db_status()
            elif hasattr(self.vector_store, '_collection'):
                collection = self.vector_store._collection
                return collection.count()
            else:
                # 간단한 검색으로 DB 상태 확인
                test_docs = self.vector_store.similarity_search("test", k=1)
                return len(test_docs) if test_docs else 0
        except Exception as e:
            logger.warning(f"DB 상태 확인 실패: {e}")
            return 0
    
    def _clean_query(self, query: str) -> str:
        """쿼리 정리 및 핵심 키워드 추출"""
        # 기본 정리
        query = query.strip()
        
        # 너무 긴 쿼리는 자르기
        if len(query) > 200:
            query = query[:200]
        
        # 핵심 키워드 추출 - 더 정교하게
        keywords = []
        
        # 1. 고유명사 패턴 (2글자 이상)
        proper_nouns = re.findall(r'[가-힣]{2,}(?:대보름|달집태우기|행사|지원|지시)', query)
        keywords.extend(proper_nouns)
        
        # 2. 일반 키워드 (2글자 이상)
        general_words = re.findall(r'[가-힣a-zA-Z0-9]{2,}', query)
        
        # 불용어 제거 - 더 포괄적으로
        stopwords = {
            '은', '는', '이', '가', '을', '를', '에', '에서', '으로', '로', 
            '하다', '되다', '있다', '없다', '것', '그', '저', '이것', '저것', '그것',
            '무엇', '어떤', '어떻게', '언제', '어디', '누구', '왜', '어느',
            '대한', '관한', '대해', '통해', '위한', '같은', '다른', '모든', '각각',
            '또한', '그리고', '하지만', '그러나', '따라서', '그래서', '때문에'
        }
        
        meaningful_words = [w for w in general_words if w not in stopwords and len(w) >= 2]
        
        # 3. 중요도 기반 정렬
        word_counts = Counter(meaningful_words)
        
        # 질문에서 중요한 단어들 우선 선택
        important_words = []
        for word, count in word_counts.most_common():
            if word not in keywords:  # 중복 제거
                important_words.append(word)
        
        # 최종 키워드 조합 (최대 8개)
        final_keywords = (keywords + important_words)[:8]
        
        # 원본 질문이 짧으면 그대로 사용
        if len(query) <= 50 and len(final_keywords) <= 3:
            return query
        
        result = ' '.join(final_keywords) if final_keywords else query
        logger.info(f"키워드 추출: '{query}' → '{result}'")
        return result
        
    def _search_documents(self, query: str, k: int = 8) -> List[Document]:
        """문서 검색 - 정확도 개선"""
        try:
            logger.info(f"문서 검색: '{query}' (k={k})")
            
            # DB 크기 확인
            db_size = self._check_db_status()
            if db_size == 0:
                logger.warning("벡터 DB가 비어 있습니다")
                return []
            
            k = min(k, db_size)
            
            # 1차 검색 - 더 많은 문서 검색
            search_k = min(k * 3, 30)
            
            # 벡터 스토어에서 검색
            if hasattr(self.vector_store, 'hierarchical_search'):
                docs = self.vector_store.hierarchical_search(query, k=search_k)
            elif hasattr(self.vector_store, 'similarity_search'):
                docs = self.vector_store.similarity_search(query, k=search_k)
            else:
                logger.error("검색 메서드를 찾을 수 없습니다")
                return []
            
            if not docs:
                return []
    
            # 2차 필터링 - 키워드 매칭 기반
            filtered_docs = self._advanced_filter_docs(docs, query)
            
            # 최종 결과 (상위 k개)
            result = filtered_docs[:k]
            
            logger.info(f"검색 완료: {len(docs)}개 → 필터링 후 {len(filtered_docs)}개 → 최종 {len(result)}개")
            return result
            
        except Exception as e:
            logger.error(f"문서 검색 오류: {e}")
            return []
            
    def _advanced_filter_docs(self, docs: List[Document], query: str) -> List[Document]:
        """고급 문서 필터링"""
        if not docs:
            return []
        
        # 쿼리 키워드 추출
        query_keywords = set(re.findall(r'[가-힣a-zA-Z0-9]{2,}', query.lower()))
        
        scored_docs = []
        for doc in docs:
            doc_text = doc.page_content.lower()
            
            # 1. 정확한 키워드 매칭 점수
            exact_matches = sum(1 for keyword in query_keywords if keyword in doc_text)
            exact_score = exact_matches / len(query_keywords) if query_keywords else 0
            
            # 2. 부분 매칭 점수 (키워드의 일부가 포함된 경우)
            partial_matches = 0
            for keyword in query_keywords:
                if len(keyword) >= 3:
                    # 3글자 이상 키워드의 앞 2글자가 문서에 있는지 확인
                    if keyword[:2] in doc_text:
                        partial_matches += 0.5
            
            partial_score = partial_matches / len(query_keywords) if query_keywords else 0
            
            # 3. 문서 품질 점수
            quality_score = doc.metadata.get('quality_score', 0.5)
            
            # 4. 문서 길이 점수 (너무 짧거나 길지 않은 문서 선호)
            doc_length = len(doc.page_content)
            if 100 <= doc_length <= 1500:
                length_score = 1.0
            elif 50 <= doc_length <= 2000:
                length_score = 0.8
            else:
                length_score = 0.5
            
            # 5. 최종 점수 계산
            final_score = (
                exact_score * 0.4 +           # 정확한 매칭 40%
                partial_score * 0.2 +         # 부분 매칭 20%
                quality_score * 0.2 +         # 품질 20%
                length_score * 0.2            # 길이 20%
            )
            
            # 메타데이터에 점수 저장
            doc.metadata['relevance_score'] = final_score
            doc.metadata['exact_match_score'] = exact_score
            doc.metadata['partial_match_score'] = partial_score
            
            # 최소 임계값 이상인 문서만 포함
            if final_score >= 0.1:  # 임계값 낮춤
                scored_docs.append((doc, final_score))
        
        # 점수 기준 정렬
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        
        # 상위 문서들 반환
        result = [doc for doc, score in scored_docs]
        
        # 로깅
        if scored_docs:
            top_score = scored_docs[0][1]
            logger.info(f"필터링 결과: 최고 점수 {top_score:.3f}, {len(result)}개 문서 선택")
        
        return result
    
    def _filter_relevant_docs(self, docs: List[Document], query: str) -> List[Document]:
        """관련성 높은 문서만 필터링 - 더 엄격하게"""
        if not docs:
            return []
        
        # 이미 고급 필터링을 거쳤으므로 추가 필터링은 최소화
        # 단지 relevance_score 기준으로 재정렬
        docs_with_scores = [(doc, doc.metadata.get('relevance_score', 0)) for doc in docs]
        docs_with_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 상위 문서들만 선택 (최소 점수 0.15 이상)
        filtered = [doc for doc, score in docs_with_scores if score >= 0.15]
        
        # 최소 1개는 보장 (검색 결과가 있다면)
        if not filtered and docs:
            filtered = [docs_with_scores[0][0]]
        
        return filtered[:self.max_documents]
    
    def _build_context(self, docs: List[Document]) -> str:
        """컨텍스트 구성 - 관련 내용 우선 포함"""
        if not docs:
            return ""
        
        context_parts = []
        for i, doc in enumerate(docs):
            # 출처 정보 정리
            source = doc.metadata.get('source', f'문서{i+1}')
            if '/' in source:
                source = source.split('/')[-1]
            elif '\\' in source:
                source = source.split('\\')[-1]
                
            # 점수 정보 (있는 경우만)
            score_info = ""
            relevance = doc.metadata.get('relevance_score')
            if relevance is not None:
                score_info = f" (관련성: {relevance:.2f})"
            
            # 문서 내용 - 자르지 않고 전체 사용 (최대 2000자까지)
            content = doc.page_content
            if len(content) > 2000:
                content = content[:2000] + "..."
            
            context_parts.append(f"[{source}{score_info}]\n{content}")
        
        return "\n\n".join(context_parts)
    
    def _extract_sources(self, docs: List[Document], question: str = "") -> List[str]:
        """출처 추출 - 실제 관련 내용이 있는 문서만"""
        sources_with_scores = []
        
        # 질문에서 핵심 키워드 추출
        question_keywords = set()
        if question:
            # 1. 기본 키워드 추출 (3글자 이상)
            keywords = re.findall(r'[가-힣]{3,}', question.lower())
            
            # 2. 조사, 어미 제거하여 어근 추출
            processed_keywords = []
            for keyword in keywords:
                # 일반적인 조사/어미 패턴 제거
                if keyword.endswith(('에서', '에게', '에는', '에도', '에만')):
                    processed_keywords.append(keyword[:-2])
                elif keyword.endswith(('은', '는', '이', '가', '을', '를', '에', '로', '와', '과', '의', '도', '만', '부터', '까지', '에게', '한테')):
                    processed_keywords.append(keyword[:-1])
                elif keyword.endswith(('습니까', '습니다', '했습니까', '입니까')):
                    # 의문사/존댓말 어미 제거
                    if keyword.endswith('습니까'):
                        processed_keywords.append(keyword[:-3])
                    elif keyword.endswith('습니다'):
                        processed_keywords.append(keyword[:-3])
                    elif keyword.endswith('했습니까'):
                        processed_keywords.append(keyword[:-4])
                    elif keyword.endswith('입니까'):
                        processed_keywords.append(keyword[:-3])
                else:
                    processed_keywords.append(keyword)
            
            # 3. 불용어 제거
            stopwords = {'무엇', '어떤', '어떻게', '언제', '어디', '누구', '왜', '어느', '지시', '했', '바람'}
            
            # 4. 최종 키워드 선택 (2글자 이상, 불용어 제외)
            final_keywords = [k for k in processed_keywords if len(k) >= 2 and k not in stopwords]
            question_keywords = set(final_keywords)
        
        for doc in docs:
            source = doc.metadata.get('source', 'unknown')
            if '/' in source:
                source = source.split('/')[-1]
            elif '\\' in source:
                source = source.split('\\')[-1]
            
            # 관련성 점수 기준으로 정렬
            relevance_score = doc.metadata.get('relevance_score', 0)
            
            # 문서 내용에서 질문 키워드 매칭 확인
            doc_text = doc.page_content.lower()
            keyword_matches = 0
            for keyword in question_keywords:
                if keyword in doc_text:
                    keyword_matches += 1
            
            # 키워드 매칭률 계산
            keyword_match_rate = keyword_matches / len(question_keywords) if question_keywords else 0
            
            # 관련성이 높고 실제 키워드가 매칭되는 문서만 출처로 포함 (더 엄격하게)
            if relevance_score >= 0.6 and keyword_match_rate >= 0.5:
                # 출처 사용 횟수 증가
                self.source_reliability[source]['count'] += 1
                
                # 관련성 점수로 신뢰도 업데이트
                current_score = self.source_reliability[source]['score']
                count = self.source_reliability[source]['count']
                
                # 가중 평균으로 신뢰도 업데이트
                new_score = (current_score * (count - 1) + relevance_score) / count
                self.source_reliability[source]['score'] = new_score
                
                sources_with_scores.append((source, relevance_score))
        
        # 관련성 점수 기준 정렬 및 중복 제거
        unique_sources = {}
        for source, score in sources_with_scores:
            if source not in unique_sources or unique_sources[source] < score:
                unique_sources[source] = score
        
        sorted_sources = sorted(unique_sources.items(), key=lambda x: x[1], reverse=True)
        return [source for source, _ in sorted_sources[:1]]  # 가장 관련성 높은 1개만
    
    def _validate_relevance(self, docs: List[Document], query: str) -> bool:
        """질문과 문서의 관련성 엄격 검증 - 개선된 버전"""
        if not docs:
            return False
        
        # 쿼리에서 핵심 키워드 추출 - 더 정교하게
        query_lower = query.lower()
        
        # 1. 중요한 키워드들 (3글자 이상)
        important_keywords = re.findall(r'[가-힣]{3,}', query_lower)
        
        # 2. 일반 키워드들 (2글자 이상)
        general_keywords = re.findall(r'[가-힣a-zA-Z0-9]{2,}', query_lower)
        
        # 불용어 제거
        stopwords = {
            '은', '는', '이', '가', '을', '를', '에', '에서', '으로', '로', 
            '하다', '되다', '있다', '없다', '것', '그', '저', '이것', '저것', '그것',
            '무엇', '어떤', '어떻게', '언제', '어디', '누구', '왜', '어느',
            '대한', '관한', '대해', '통해', '위한', '같은', '다른', '모든', '각각',
            '또한', '그리고', '하지만', '그러나', '따라서', '그래서', '때문에',
            '지시', '했습니까', '무엇입니까', '어떤', '위해'
        }
        
        # 중요 키워드 우선, 일반 키워드 보조
        filtered_important = [k for k in important_keywords if k not in stopwords]
        filtered_general = [k for k in general_keywords if k not in stopwords and k not in filtered_important]
        
        # 최종 키워드 리스트 (중요 키워드 + 일반 키워드 상위 5개)
        final_keywords = filtered_important + filtered_general[:5]
        
        if not final_keywords:
            return True  # 키워드가 없으면 통과
        
        logger.info(f"검증 키워드: {final_keywords}")
        
        # 각 문서에서 키워드 매칭 확인
        total_relevance = 0
        for doc in docs:
            doc_text = doc.page_content.lower()
            
            # 정확한 매칭
            exact_matches = sum(1 for keyword in final_keywords if keyword in doc_text)
            
            # 부분 매칭 (키워드의 일부가 포함된 경우)
            partial_matches = 0
            for keyword in final_keywords:
                if len(keyword) >= 4:
                    # 4글자 이상 키워드의 앞 3글자가 문서에 있는지 확인
                    if keyword[:3] in doc_text:
                        partial_matches += 0.5
                elif len(keyword) >= 3:
                    # 3글자 키워드의 앞 2글자가 문서에 있는지 확인
                    if keyword[:2] in doc_text:
                        partial_matches += 0.3
            
            # 관련성 계산
            relevance = (exact_matches + partial_matches) / len(final_keywords) if final_keywords else 0
            total_relevance += relevance
        
        # 평균 관련성이 5% 이상이면 관련 있다고 판단 (매우 완화)
        avg_relevance = total_relevance / len(docs) if docs else 0
        
        logger.info(f"관련성 검증: 키워드 {len(final_keywords)}개, 평균 관련성 {avg_relevance:.3f}")
        
        return avg_relevance >= 0.05
    
    def query(self, question: str) -> str:
        """질문 처리 - 관련성 검증 강화"""
        start_time = time.time()
        
        try:
            # 입력 검증
            if not question.strip():
                return "질문을 입력해주세요."
            
            # 캐시 확인
            cache_key = hashlib.md5(question.encode()).hexdigest()
            if cache_key in self.query_cache:
                logger.info(f"캐시에서 응답 반환: {question[:30]}...")
                return self.query_cache[cache_key]
            
            logger.info(f"질문 처리 시작: {question}")
            
            # 1. 쿼리 정리
            cleaned_query = self._clean_query(question)
            logger.info(f"정리된 쿼리: {cleaned_query}")
            
            # 2. 문서 검색
            docs = self._search_documents(cleaned_query, k=min(5, self.max_documents))
            
            if not docs:
                return "질문에 관련된 문서를 찾을 수 없습니다. 다른 질문을 시도하거나 문서를 추가해주세요."
            
            logger.info(f"검색된 문서: {len(docs)}개")
            
            # 3. 관련성 엄격 검증 - 다시 활성화
            if not self._validate_relevance(docs, question):
                return "제공된 문서에서 해당 정보를 찾을 수 없습니다."
            
            # 4. 관련성 필터링 - 상위 2개만 선택
            filtered_docs = self._filter_relevant_docs(docs, cleaned_query)[:2]
            
            if not filtered_docs:
                return "제공된 문서에서 해당 정보를 찾을 수 없습니다."
            
            logger.info(f"필터링된 문서: {len(filtered_docs)}개")
            
            # 5. 컨텍스트 구성
            context = self._build_context(filtered_docs)
            
            # 6. 답변 생성
            response = self.qa_chain.invoke({
                "question": question,
                "context": context
            })
            
            # 7. think 태그 제거
            response = self._clean_response(response)
            
            # 7. 답변 검증 - "찾을 수 없다"는 답변이 아닌 경우에만 출처 추가
            if "찾을 수 없" not in response and "없습니다" not in response:
                sources = self._extract_sources(filtered_docs, question)
                if sources and "출처:" not in response:
                    sources_text = ", ".join(sources)
                    response = f"{response}\n\n출처: {sources_text}"
                elif not sources and "출처:" not in response:
                    # 출처가 없어도 문서에서 답변을 생성했다면 가장 관련성 높은 1개 문서만 출처로 추가
                    if filtered_docs:
                        # 가장 관련성 높은 문서 1개만 선택
                        best_doc = max(filtered_docs, key=lambda x: x.metadata.get('relevance_score', 0))
                        source = best_doc.metadata.get('source', '')
                        if source and source != '알 수 없음':
                            if '/' in source:
                                source = source.split('/')[-1]
                            elif '\\' in source:
                                source = source.split('\\')[-1]
                            response = f"{response}\n\n출처: {source}"
            
            # 8. 캐시 저장
            if len(self.query_cache) >= self.max_cache_size:
                # 가장 오래된 항목 제거
                oldest_key = next(iter(self.query_cache))
                del self.query_cache[oldest_key]
            
            self.query_cache[cache_key] = response
            
            elapsed = time.time() - start_time
            logger.info(f"질문 처리 완료: {elapsed:.2f}초")
            
            return response
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"질문 처리 오류: {e}, 소요시간: {elapsed:.2f}초")
            return f"죄송합니다. 질문 처리 중 오류가 발생했습니다: {str(e)}"
    
    def summarize(self, document: str) -> str:
        """문서 요약"""
        try:
            if not document.strip():
                return "요약할 내용이 없습니다."
            
            # 문서가 너무 길면 앞부분만 사용
            if len(document) > 3000:
                document = document[:3000] + "..."
            
            response = self.summarize_chain.invoke({"document": document})
            return self._clean_response(response)
            
        except Exception as e:
            logger.error(f"문서 요약 오류: {e}")
            return "문서 요약 중 오류가 발생했습니다."
                
    def clear_cache(self):
        """캐시 초기화"""
        self.query_cache.clear()
        logger.info("캐시가 초기화되었습니다.")
    
    def get_source_reliability(self) -> Dict[str, Dict]:
        """출처 신뢰도 정보 반환"""
        return dict(self.source_reliability)

# 하위 호환성을 위한 별칭
RAGChain = SimpleRAGChain 