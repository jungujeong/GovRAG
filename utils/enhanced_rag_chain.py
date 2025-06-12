import re
import time
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter
from datetime import datetime

from langchain.prompts import PromptTemplate
from langchain_ollama import OllamaLLM
from langchain.schema.output_parser import StrOutputParser
from langchain.schema import Document

from .enhanced_vector_store import EnhancedVectorStore
from config import (
    OLLAMA_MODEL, 
    OLLAMA_BASE_URL, 
    TEMPERATURE,
    logger
)

class EnhancedRAGChain:
    """고급 RAG 체인 - 다단계 추론 및 답변 검증"""
    
    def __init__(self, vector_store: Optional[EnhancedVectorStore] = None):
        """RAG 체인 초기화"""
        
        # 벡터 스토어 설정
        self.vector_store = vector_store or EnhancedVectorStore()
        
        # LLM 초기화
        self._initialize_llm()
        
        # 프롬프트 템플릿 초기화
        self._initialize_prompts()
        
        # 체인 설정
        self._setup_chains()
        
        # 성능 추적
        self.query_cache = {}
        self.performance_stats = defaultdict(int)
        
        # 답변 품질 추적
        self.answer_quality_tracker = defaultdict(list)
        
        logger.info("고급 RAG 체인 초기화 완료")
    
    def _initialize_llm(self):
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
        """프롬프트 템플릿 초기화"""
        
        # 1. 질문 분석 프롬프트
        self.query_analysis_prompt = PromptTemplate.from_template(
            """다음 질문을 분석하여 핵심 정보를 추출하세요.

질문: {question}

다음 형식으로 분석 결과를 작성하세요:
- 핵심 키워드: [주요 키워드들을 쉼표로 구분]
- 질문 유형: [사실 확인/방법 설명/비교 분석/기타]
- 필요한 정보: [답변을 위해 필요한 구체적 정보]

분석 결과:"""
        )
        
        # 2. 컨텍스트 평가 프롬프트
        self.context_evaluation_prompt = PromptTemplate.from_template(
            """다음 문서 내용이 질문에 답하기에 충분한지 평가하세요.

질문: {question}

문서 내용:
{context}

평가 기준:
1. 관련성: 문서가 질문과 직접적으로 관련되어 있는가?
2. 완전성: 질문에 완전히 답할 수 있는 정보가 있는가?
3. 신뢰성: 정보가 명확하고 일관된가?

평가 결과를 다음 형식으로 작성하세요:
- 관련성: [높음/보통/낮음]
- 완전성: [완전함/부분적/불완전함]
- 신뢰성: [높음/보통/낮음]
- 종합 평가: [적합/부분적합/부적합]

평가:"""
        )
        
        # 3. 메인 QA 프롬프트 (개선된 버전)
        self.qa_prompt = PromptTemplate.from_template(
            """당신은 한국어 문서 전문 분석 AI입니다. 제공된 문서를 바탕으로 정확하고 상세한 답변을 제공하세요.

📋 질문: {question}

📄 관련 문서:
{context}

📌 답변 작성 지침:
1. 문서에 명시된 내용만을 바탕으로 정확히 답변하세요
2. 구체적인 근거와 인용을 포함하여 상세히 답변하세요  
3. 문서에서 확인할 수 없는 내용은 "문서에서 명확하지 않습니다"라고 명시하세요
4. 문서에 관련 정보가 전혀 없으면 "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답변하세요
5. 답변은 한국어로 자연스럽고 논리적으로 구성하세요
6. 가능한 한 구체적인 수치, 날짜, 기관명 등을 포함하세요

💬 답변:"""
        )
        
        # 4. 답변 검증 프롬프트
        self.answer_verification_prompt = PromptTemplate.from_template(
            """다음 답변이 제공된 문서 내용과 일치하는지 검증하세요.

원본 질문: {question}

문서 내용:
{context}

생성된 답변:
{answer}

검증 기준:
1. 사실 정확성: 답변이 문서의 사실과 일치하는가?
2. 완전성: 문서에서 찾을 수 있는 관련 정보를 충분히 포함하는가?
3. 일관성: 답변이 논리적으로 일관되는가?

검증 결과:
- 사실 정확성: [정확/부분적 정확/부정확]
- 완전성: [완전/부분적/불완전]
- 일관성: [일관됨/부분적 일관/불일치]
- 최종 평가: [검증됨/수정 필요/부적절]

검증:"""
        )
        
        # 5. 요약 프롬프트
        self.summarization_prompt = PromptTemplate.from_template(
            """다음 문서를 핵심 내용 위주로 요약하세요.

문서:
{document}

요약 지침:
- 3-5개 문장으로 요약
- 핵심 내용과 주요 세부사항 포함
- 명확하고 간결한 표현 사용

요약:"""
        )
    
    def _setup_chains(self):
        """체인 설정"""
        self.query_analysis_chain = self.query_analysis_prompt | self.llm | StrOutputParser()
        self.context_evaluation_chain = self.context_evaluation_prompt | self.llm | StrOutputParser()
        self.qa_chain = self.qa_prompt | self.llm | StrOutputParser()
        self.answer_verification_chain = self.answer_verification_prompt | self.llm | StrOutputParser()
        self.summarization_chain = self.summarization_prompt | self.llm | StrOutputParser()
    
    def _analyze_query(self, question: str) -> Dict[str, Any]:
        """질문 분석"""
        try:
            analysis_result = self.query_analysis_chain.invoke({"question": question})
            
            # 분석 결과 파싱
            analysis = {}
            for line in analysis_result.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip('- ').lower().replace(' ', '_')
                    analysis[key] = value.strip()
            
            return analysis
        except Exception as e:
            logger.error(f"질문 분석 실패: {e}")
            return {"핵심_키워드": question, "질문_유형": "기타"}
    
    def _search_with_multiple_strategies(self, question: str, analysis: Dict[str, Any]) -> List[Document]:
        """다중 검색 전략 적용"""
        try:
            all_results = []
            
            # 1. 하이브리드 검색 (메인)
            hybrid_results = self.vector_store.hybrid_search(
                query=question, 
                k=8,
                vector_weight=0.7,
                bm25_weight=0.3
            )
            all_results.extend(hybrid_results)
            
            # 2. 키워드 기반 검색 (보완)
            if "핵심_키워드" in analysis:
                keywords = analysis["핵심_키워드"]
                keyword_results = self.vector_store.keyword_search(
                    query=keywords,
                    k=5
                )
                all_results.extend(keyword_results)
            
            # 3. 의미적 검색 (추가)
            semantic_results = self.vector_store.semantic_search(
                query=question,
                k=5,
                similarity_threshold=0.4
            )
            all_results.extend(semantic_results)
            
            # 중복 제거 (내용 기반)
            unique_results = self._deduplicate_documents(all_results)
            
            # 최대 10개로 제한
            return unique_results[:10]
            
        except Exception as e:
            logger.error(f"다중 검색 실패: {e}")
            return []
    
    def _deduplicate_documents(self, documents: List[Document]) -> List[Document]:
        """문서 중복 제거"""
        seen_content = set()
        unique_docs = []
        
        for doc in documents:
            # 내용의 해시값으로 중복 확인
            content_hash = hashlib.md5(doc.page_content.encode()).hexdigest()
            
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_docs.append(doc)
        
        return unique_docs
    
    def _evaluate_context_relevance(self, question: str, documents: List[Document]) -> List[Document]:
        """컨텍스트 관련성 평가"""
        try:
            if not documents:
                return []
            
            # 문서가 너무 많으면 상위 5개만 평가
            docs_to_evaluate = documents[:5]
            
            evaluated_docs = []
            
            for doc in docs_to_evaluate:
                try:
                    # 컨텍스트 평가
                    evaluation = self.context_evaluation_chain.invoke({
                        "question": question,
                        "context": doc.page_content[:1000]  # 길이 제한
                    })
                    
                    # "적합" 또는 "부분적합"인 경우만 포함
                    if "적합" in evaluation:
                        evaluated_docs.append(doc)
                    
                except Exception as e:
                    logger.warning(f"개별 문서 평가 실패: {e}")
                    # 평가 실패시에도 문서 포함 (안전장치)
                    evaluated_docs.append(doc)
            
            # 평가된 문서가 없으면 원본 문서 중 일부라도 반환
            if not evaluated_docs and documents:
                evaluated_docs = documents[:3]
            
            return evaluated_docs
            
        except Exception as e:
            logger.error(f"컨텍스트 평가 실패: {e}")
            return documents[:5]  # 폴백: 상위 5개 반환
    
    def _build_context(self, documents: List[Document]) -> str:
        """컨텍스트 구성"""
        if not documents:
            return ""
        
        context_parts = []
        
        for i, doc in enumerate(documents, 1):
            # 메타데이터에서 출처 정보 추출
            source = doc.metadata.get('source', f'문서 {i}')
            page = doc.metadata.get('page', '')
            
            # 출처 정보 구성
            source_info = f"[출처: {source}"
            if page:
                source_info += f", 페이지 {page}"
            source_info += "]"
            
            # 문서 내용 (길이 제한)
            content = doc.page_content
            if len(content) > 800:
                content = content[:800] + "..."
            
            context_parts.append(f"{source_info}\n{content}")
        
        return "\n\n".join(context_parts)
    
    def _generate_answer(self, question: str, context: str) -> str:
        """답변 생성"""
        try:
            if not context.strip():
                return "제공된 문서에서 해당 정보를 찾을 수 없습니다."
            
            answer = self.qa_chain.invoke({
                "question": question,
                "context": context
            })
            
            return answer.strip()
            
        except Exception as e:
            logger.error(f"답변 생성 실패: {e}")
            return "답변 생성 중 오류가 발생했습니다."
    
    def _verify_answer(self, question: str, context: str, answer: str) -> Tuple[str, bool]:
        """답변 검증"""
        try:
            # 검증하지 않을 답변들
            skip_verification = [
                "제공된 문서에서 해당 정보를 찾을 수 없습니다",
                "답변 생성 중 오류가 발생했습니다"
            ]
            
            if any(skip_text in answer for skip_text in skip_verification):
                return answer, True
            
            verification = self.answer_verification_chain.invoke({
                "question": question,
                "context": context,
                "answer": answer
            })
            
            # 검증 결과 파싱
            is_verified = "검증됨" in verification or "정확" in verification
            
            return answer, is_verified
            
        except Exception as e:
            logger.error(f"답변 검증 실패: {e}")
            return answer, False  # 검증 실패시 False 반환
    
    def _extract_sources(self, documents: List[Document]) -> List[str]:
        """출처 정보 추출"""
        sources = []
        seen_sources = set()
        
        for doc in documents:
            source = doc.metadata.get('source', '')
            if source and source not in seen_sources:
                seen_sources.add(source)
                sources.append(source)
        
        return sources
    
    def _format_final_answer(self, answer: str, sources: List[str], 
                           confidence_score: float = 0.0) -> str:
        """최종 답변 포맷팅"""
        formatted_answer = answer
        
        # 출처 정보 추가
        if sources:
            source_text = ", ".join(sources)
            formatted_answer += f"\n\n📄 출처: {source_text}"
        
        # 신뢰도 점수 추가 (옵션)
        if confidence_score > 0:
            formatted_answer += f"\n🎯 신뢰도: {confidence_score:.1%}"
        
        return formatted_answer
    
    def query(self, question: str, use_cache: bool = True) -> str:
        """메인 질의 처리"""
        start_time = time.time()
        
        try:
            logger.info(f"RAG 질의 시작: '{question}'")
            
            # 캐시 확인
            cache_key = hashlib.md5(question.encode()).hexdigest()
            if use_cache and cache_key in self.query_cache:
                logger.info("캐시에서 답변 반환")
                return self.query_cache[cache_key]
            
            # 1단계: 질문 분석
            analysis = self._analyze_query(question)
            logger.info(f"질문 분석 완료: {analysis.get('질문_유형', '알 수 없음')}")
            
            # 2단계: 다중 전략 검색
            documents = self._search_with_multiple_strategies(question, analysis)
            logger.info(f"문서 검색 완료: {len(documents)}개 문서")
            
            if not documents:
                answer = "관련된 문서를 찾을 수 없습니다."
                return self._format_final_answer(answer, [])
            
            # 3단계: 컨텍스트 관련성 평가
            relevant_docs = self._evaluate_context_relevance(question, documents)
            logger.info(f"관련성 평가 완료: {len(relevant_docs)}개 문서 선택")
            
            # 4단계: 컨텍스트 구성
            context = self._build_context(relevant_docs)
            
            # 5단계: 답변 생성
            answer = self._generate_answer(question, context)
            
            # 6단계: 답변 검증
            verified_answer, is_verified = self._verify_answer(question, context, answer)
            
            # 7단계: 출처 정보 추출
            sources = self._extract_sources(relevant_docs)
            
            # 8단계: 최종 답변 포맷팅
            confidence = 0.8 if is_verified else 0.6
            final_answer = self._format_final_answer(verified_answer, sources, confidence)
            
            # 캐시 저장
            if use_cache:
                self.query_cache[cache_key] = final_answer
                # 캐시 크기 제한
                if len(self.query_cache) > 50:
                    oldest_key = next(iter(self.query_cache))
                    del self.query_cache[oldest_key]
            
            # 성능 통계 업데이트
            elapsed_time = time.time() - start_time
            self.performance_stats['total_queries'] += 1
            self.performance_stats['total_time'] += elapsed_time
            self.performance_stats['verified_answers'] += (1 if is_verified else 0)
            
            logger.info(f"RAG 질의 완료: {elapsed_time:.2f}초, 검증됨: {is_verified}")
            
            return final_answer
            
        except Exception as e:
            logger.error(f"RAG 질의 처리 실패: {e}")
            return "죄송합니다. 답변 처리 중 오류가 발생했습니다."
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 조회"""
        stats = dict(self.performance_stats)
        
        if stats.get('total_queries', 0) > 0:
            stats['avg_response_time'] = stats['total_time'] / stats['total_queries']
            stats['verification_rate'] = stats['verified_answers'] / stats['total_queries']
        
        return stats
    
    def clear_cache(self):
        """캐시 초기화"""
        self.query_cache.clear()
        logger.info("캐시 초기화 완료")
    
    def summarize_document(self, document: str) -> str:
        """문서 요약"""
        try:
            if len(document) < 100:
                return document  # 너무 짧은 문서는 그대로 반환
            
            summary = self.summarization_chain.invoke({"document": document})
            return summary.strip()
            
        except Exception as e:
            logger.error(f"문서 요약 실패: {e}")
            return "요약 생성에 실패했습니다." 