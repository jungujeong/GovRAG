from langchain.prompts import PromptTemplate
from langchain_ollama import OllamaLLM
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough

from .vector_store import VectorStore
from config import (
    OLLAMA_MODEL, 
    OLLAMA_BASE_URL, 
    TEMPERATURE,
    logger
)
import re
import time

class RAGChain:
    def __init__(self, vector_store=None):
        """RAG 체인 초기화"""
        if vector_store is None:
            self.vector_store = VectorStore()
            self.is_vector_store_instance = True
        else:
            self.vector_store = vector_store
            self.is_vector_store_instance = False
        
        # 벡터 DB 크기 확인
        self._check_vector_db_size()
        
        # LLM 초기화
        try:
            self.llm = OllamaLLM(
                model=OLLAMA_MODEL,
                base_url=OLLAMA_BASE_URL,
                temperature=TEMPERATURE
            )
            logger.info(f"LLM이 {OLLAMA_MODEL} 모델로 초기화되었습니다")
        except Exception as e:
            logger.error(f"LLM 초기화 오류: {e}")
            raise
        
        # 쿼리 변환 프롬프트 
        self.query_transform_prompt = PromptTemplate.from_template(
            """주어진 질문을 벡터 데이터베이스에서 검색하기 좋은 형태로 변환해주세요.
            질문에 포함된 고유명사와 핵심 키워드를 추출하세요.
            특히 사람 이름, 장소, 조직 등은 반드시 포함하세요.
            
            원래 질문: {question}
            최적화된 검색어:"""
        )
        
        # QA 프롬프트 - 정확도 중심
        self.qa_prompt = PromptTemplate.from_template(
            """다음 질문과 관련된 컨텍스트를 바탕으로 답변해주세요.
            
            중요 지침:
            1. 반드시 제공된 컨텍스트 내의 정보만 사용하여 답변하세요. 컨텍스트에 없는 내용은 절대 포함하지 마세요.
            2. 컨텍스트에 있는 내용을 정확하게 답변에 포함하세요. 내용을 왜곡하거나 바꾸지 마세요.
            3. 질문과 직접적으로 관련된 정보가 있으면 반드시 그 정보를 사용하세요.
            4. 컨텍스트에서 명확히 답변할 수 있는 정보가 전혀 없을 때만 "주어진 문서에서 해당 정보를 찾을 수 없습니다."라고 답하세요.
            5. 반드시 사용한 모든 정보의 출처를 답변 마지막에 표시하세요.
            6. 답변에는 컨텍스트에 포함된 사실만 포함하고, 추측이나 일반적인 정보는 절대 포함하지 마세요.
            7. 컨텍스트의 정보를 그대로 활용하고, 불필요한 패러프레이징은 하지 마세요.
            8. 본인의 지식이나 경험을 답변에 절대 포함하지 마세요. 오직 주어진 컨텍스트만 사용하세요.
            9. 답변 끝에는 반드시 출처를 명시하세요. 컨텍스트에 없는 내용을 추가하지 마세요.
            
            질문: {question}
            
            컨텍스트:
            {context}
            
            답변:"""
        )
        
        # 요약 프롬프트
        self.summarize_prompt = PromptTemplate.from_template(
            """다음 문서 내용을 요약해주세요. 
            요약은 한글 기준 5~7문장으로 작성하세요.
            문서의 핵심 내용과 중요 정보만 포함하세요.
            
            문서:
            {document}
            
            요약:"""
        )
        
        # LCEL 패턴을 사용한 체인 구성
        self.query_transform_chain = self.query_transform_prompt | self.llm | StrOutputParser()
        self.summarize_chain = self.summarize_prompt | self.llm | StrOutputParser()
        
        # RAG 체인 설정
        self._setup_rag_chain()
    
    def _check_vector_db_size(self):
        """벡터 DB 크기 확인"""
        try:
            # VectorStore 인스턴스인 경우 해당 메소드 사용
            if self.is_vector_store_instance:
                db_size = self.vector_store._log_db_size()
            else:
                # Chroma 객체인 경우 직접 컬렉션 크기 확인
                collection = self.vector_store._collection
                db_size = collection.count()
                logger.info(f"벡터 DB 크기: {db_size}개 문서")
                
            if db_size == 0:
                logger.warning("벡터 DB가 비어 있습니다. 문서를 추가해야 검색과 질의응답이 가능합니다.")
                
            return db_size
        except Exception as e:
            logger.warning(f"벡터 DB 크기 확인 실패: {e}")
            return 0
    
    def _transform_query(self, question):
        """효율적인 쿼리 변환"""
        # 길이 제한
        if len(question) > 300:
            question = question[:300]
            logger.info(f"쿼리 길이 제한: 300자로 자름")
        
        # 1. 고유명사 질문 패턴 확인 (예: '홍길동이란?', '홍길동의 직업은?')
        patterns = [
            r'^([가-힣a-zA-Z0-9]{2,})[이가](\s)*(는|란|이란|가)(\s)*(무엇|뭐|뭔가|뭘까|누구|어디|언제).*$',
            r'^([가-힣a-zA-Z0-9]{2,})의(\s)*(은|는|이|가|란).*$'
        ]
        
        for pattern in patterns:
            match = re.match(pattern, question)
            if match:
                proper_noun = match.group(1)
                if len(proper_noun) >= 2:
                    logger.info(f"고유명사 추출: '{proper_noun}'")
                    return proper_noun
        
        # 2. 키워드 추출
        stopwords = ['은', '는', '이', '가', '을', '를', '에', '에서', '으로', '로', '하다', '되다', 
                     '있다', '없다', '것', '그', '저', '이것', '저것', '그것', '무엇', '어떤', '어떻게']
        
        keywords = []
        
        # 중요한 패턴 추출 (조직명, 인명 등)
        orgs = re.findall(r'[가-힣]{2,}(?:대학교|학교|기업|회사|조직|부서|팀)', question)
        names = re.findall(r'[가-힣]{2,4}\s*(?:씨|님|교수|박사|학생)?', question)
        keywords.extend(orgs)
        keywords.extend(names)
        
        # 일반 중요 단어 추출
        words = re.findall(r'[가-힣a-zA-Z0-9]{2,}', question)
        for word in words:
            if word not in stopwords and word not in keywords:
                keywords.append(word)
        
        if keywords and len(keywords) <= 5:
            query = ' '.join(keywords)
            if len(query) < len(question) * 0.7:
                logger.info(f"키워드 추출: '{query}'")
                return query
        
        # 3. LLM 기반 변환 (위 방법들이 실패한 경우)
        try:
            start_time = time.time()
            transformed = self.query_transform_chain.invoke({"question": question})
            elapsed = time.time() - start_time
            logger.info(f"LLM 쿼리 변환: '{transformed}' (소요 시간: {elapsed:.2f}초)")
            
            if transformed and len(transformed) < len(question) * 1.5:
                return transformed
        except Exception as e:
            logger.error(f"LLM 쿼리 변환 실패: {e}")
        
        # 모든 방법 실패시 원본 반환
        logger.info(f"원본 쿼리 사용: '{question}'")
        return question
    
    def _setup_rag_chain(self):
        """RAG 파이프라인 설정"""
        # 문서 포맷 함수
        def format_docs(docs):
            formatted = []
            for i, doc in enumerate(docs):
                source = doc.metadata.get('source', '알 수 없는 출처')
                # 실제 파일명/출처 정보를 사용
                formatted.append(f"[{source}]\n{doc.page_content}")
            return "\n\n".join(formatted)
        
        # 검색 체인 설정
        retriever = self.vector_store.similarity_search
        
        # 전체 RAG 파이프라인
        self.rag_chain = (
            lambda x: {
                "context": format_docs(retriever(self._transform_query(x["question"]), k=4)),
                "question": x["question"]
            }
            | self.qa_prompt
            | self.llm
            | StrOutputParser()
        )
    
    def _extract_sources_from_answer(self, answer, all_sources):
        """답변에서 사용된 출처 추출 또는 답변과 문서 간 유사도 기반 출처 식별"""
        # 이미 출처가 포함되어 있는지 확인
        if "출처:" in answer or "출처 :" in answer:
            return answer
        
        # "찾을 수 없습니다" 응답인 경우에도 출처 필요
        if "찾을 수 없습니다" in answer or "없습니다" in answer:
            # 참조된 모든 출처 포함
            if all_sources:
                sources_list = list(all_sources.keys())
                sources_text = ", ".join([f"{s}" for s in sources_list])
                return f"{answer}\n\n출처: {sources_text} (관련 정보 없음)"
            return answer
        
        # 문서 내용과 답변 간 유사도 기반 출처 식별
        most_relevant_sources = []
        
        # 답변에서 키워드 추출 (2글자 이상 단어)
        answer_words = set(re.findall(r'[가-힣a-zA-Z0-9]{2,}', answer))
        
        # 각 문서와 답변 간 단어 중복 확인
        for source, content in all_sources.items():
            content_words = set(re.findall(r'[가-힣a-zA-Z0-9]{2,}', content))
            # 교집합 단어 수 계산
            overlap = len(answer_words.intersection(content_words))
            overlap_ratio = overlap / len(answer_words) if answer_words else 0
            
            # 유사도가 높은 문서 선택 (단어 10% 이상 중복 - 임계값 낮춤)
            if overlap_ratio > 0.1:
                most_relevant_sources.append(source)
                logger.info(f"관련 출처 발견: {source} (유사도: {overlap_ratio:.2f})")
        
        # 관련 출처가 있으면 추가
        if most_relevant_sources:
            sources_text = ", ".join([f"{s}" for s in most_relevant_sources])
            return f"{answer}\n\n출처: {sources_text}"
        
        # 관련 출처를 찾지 못했지만 답변이 생성된 경우 모든 출처 표시
        if answer and all_sources:
            sources_list = list(all_sources.keys())
            sources_text = ", ".join([f"{s}" for s in sources_list])
            return f"{answer}\n\n출처: {sources_text}"
        
        return answer
    
    def query(self, question):
        """RAG 체인을 통해 쿼리 실행"""
        start_time = time.time()
        
        try:
            if not question.strip():
                return "질문을 입력해주세요."
            
            # 벡터 DB 문서 개수 확인
            db_size = self._check_vector_db_size()
            if db_size == 0:
                return "문서 데이터베이스가 비어 있습니다. 먼저 문서를 추가한 후 질문해주세요."
            
            # 질문 전처리
            processed_question = question.strip()
            if not processed_question.endswith(("?", ".", "!", "요")):
                processed_question += "?"
            
            logger.info(f"질문 처리 시작: '{processed_question}'")
            
            # 변환된 쿼리로 문서 검색
            transformed_query = self._transform_query(processed_question)
            docs = self.vector_store.similarity_search(transformed_query, k=min(4, db_size))
            
            # 문서를 찾지 못한 경우 원본 쿼리로 재시도
            if not docs and transformed_query != processed_question:
                logger.info("변환된 쿼리로 결과 없음, 원본 쿼리로 재시도")
                docs = self.vector_store.similarity_search(processed_question, k=min(4, db_size))
            
            # 문서를 여전히 찾지 못한 경우
            if not docs:
                logger.warning(f"검색 결과 없음: 문서를 찾을 수 없음")
                return "죄송합니다. 질문과 관련된 문서를 찾을 수 없습니다. 다른 질문을 시도해보세요."
            
            # 문서 포맷팅 및 출처 정보 수집
            context = ""
            all_sources = {}  # 출처와 문서 내용을 매핑
            
            logger.info(f"검색 성공: {len(docs)}개 관련 문서 발견")
            
            for i, doc in enumerate(docs):
                source = doc.metadata.get('source', '알 수 없는 출처')
                # 출처 이름에서 경로 부분 제거하고 파일명만 추출
                if isinstance(source, str) and '/' in source:
                    source = source.split('/')[-1]
                elif isinstance(source, str) and '\\' in source:
                    source = source.split('\\')[-1]
                
                context += f"[{source}]\n{doc.page_content}\n\n"
                all_sources[source] = doc.page_content
            
            # QA 프롬프트 실행
            final_prompt = self.qa_prompt.format(question=processed_question, context=context)
            
            # 답변 생성
            logger.info("LLM을 통한 답변 생성 시작")
            answer = self.llm.invoke(final_prompt)
            
            # 출처 확인 및 처리
            final_answer = self._extract_sources_from_answer(answer, all_sources)
            
            # 실행 시간 기록
            elapsed = time.time() - start_time
            logger.info(f"쿼리 처리 완료, 소요 시간: {elapsed:.2f}초")
            
            return final_answer
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"RAG 체인 쿼리 오류: {e}, 소요 시간: {elapsed:.2f}초")
            return f"죄송합니다. 질문 처리 중 오류가 발생했습니다: {str(e)}"
    
    def summarize(self, document):
        """문서 요약"""
        try:
            if not document.strip():
                return "요약할 내용이 없습니다."
            
            result = self.summarize_chain.invoke({"document": document})
            return result
        except Exception as e:
            logger.error(f"문서 요약 오류: {e}")
            return "죄송합니다. 문서 요약 중 오류가 발생했습니다. 다시 시도해주세요." 