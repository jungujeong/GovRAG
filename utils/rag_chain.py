from langchain.prompts import PromptTemplate
from langchain_community.llms import Ollama
from langchain.chains import LLMChain
from langchain.chains.question_answering import load_qa_chain
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.runnable import RunnableParallel

from .vector_store import VectorStore
from config import (
    OLLAMA_MODEL, 
    OLLAMA_BASE_URL, 
    TEMPERATURE,
    logger
)

class RAGChain:
    def __init__(self, vector_store=None):
        """RAG 체인 초기화"""
        if vector_store is None:
            self.vector_store = VectorStore()
        else:
            self.vector_store = vector_store
        
        # LLM 초기화
        try:
            self.llm = Ollama(
                model=OLLAMA_MODEL,
                base_url=OLLAMA_BASE_URL,
                temperature=TEMPERATURE
            )
            logger.info(f"LLM이 {OLLAMA_MODEL} 모델로 초기화되었습니다")
        except Exception as e:
            logger.error(f"LLM 초기화 오류: {e}")
            raise
        
        # 쿼리 변환 프롬프트 생성 - 개선된 버전
        self.query_transform_prompt = PromptTemplate.from_template(
            """당신은 검색 쿼리 최적화 전문가입니다.
            주어진 질문을 벡터 데이터베이스에서 검색하기 좋은 형태로 변환해주세요.
            
            지침:
            1. 질문에 포함된 고유명사(사람 이름, 장소, 조직 등)는 반드시 유지하세요.
            2. 고유명사가 있는 경우, 고유명사를 검색 쿼리의 맨 앞에 배치하세요.
            3. 질문을 키워드 중심으로 변환하되, 원본 의미를 유지하세요.
            4. 쿼리가 너무 길어지지 않도록 핵심 키워드만 유지하세요.
            5. 고유명사가 있는 질문(예: "염성현이란 무엇입니까?")의 경우 고유명사만으로 검색하는 것이 좋습니다(예: "염성현").
            6. 질문의 의도가 명확하지 않은 경우, 다양한 검색 키워드 조합을 생성하세요.
            7. 동의어나 관련 용어도 고려하여 검색 효율성을 높이세요.
            
            원래 질문: {question}
            최적화된 검색어:"""
        )
        
        # 대체 쿼리 생성 프롬프트 - 처음 검색이 실패할 경우 사용
        self.alternative_query_prompt = PromptTemplate.from_template(
            """원래 질문에 대한 검색이 실패했습니다. 
            동일한 의미를 가지면서 다른 표현이나 키워드를 사용한 대체 검색어를 3개 생성해주세요.
            각 검색어는 쉼표로 구분하세요.
            
            원래 질문: {question}
            대체 검색어(쉼표로 구분):"""
        )
        
        # LCEL 패턴을 사용하여 LLMChain 대신 구현
        self.query_transform_chain = self.query_transform_prompt | self.llm | StrOutputParser()
        self.alternative_query_chain = self.alternative_query_prompt | self.llm | StrOutputParser()
        
        # 출처 정보가 포함된 QA 체인 생성 - 개선된 버전
        self.qa_prompt = PromptTemplate.from_template(
            """다음 질문과 관련된 컨텍스트를 바탕으로 답변해주세요.
            
            중요 지침:
            1. 반드시 제공된 컨텍스트 내의 정보만 사용하여 답변하세요.
            2. 컨텍스트에 있는 내용은 정확하게 답변에 포함하세요. 
            3. 질문과 직접적으로 관련된 정보가 있으면 무조건 그 정보를 사용하세요.
            4. "찾을 수 없습니다"라고 답변하기 전에, 컨텍스트를 철저히 살펴보고 관련 정보가 있는지 확인하세요.
            5. 반드시 질문에 직접 관련된 정보가 포함된 문서의 출처만 인용하세요.
            6. 여러 문서를 참조한 경우 각 정보의 출처를 모두 표시하세요.
            7. 컨텍스트에서 명확히 답변할 수 있는 정보가 전혀 없을 때만 "주어진 문서에서 해당 정보를 찾을 수 없습니다."라고만 답하고, 출처를 표시하지 마세요.
            8. 문서에 있는 정보라면 단 한 가지라도 절대 누락하지 말고 답변에 포함하세요.
            9. 모든 정보는 있는 그대로 정확하게 전달하세요. 불필요한 추론은 하지 마세요.
            10. 문장의 일부만 있더라도 의미가 명확하다면 그대로 사용하세요.
            
            답변 형식:
            - 명확하고 간결하게, 중년층이 이해하기 쉬운 어조로 작성하세요.
            - 정확한 사실만 답변에 포함하세요.
            - 정보를 찾은 경우에만 답변 끝에 출처를 표시하세요.
            

            질문: {question}
            
            컨텍스트:
            {context}
            
            답변:"""
        )
        
        # 정보 검증 프롬프트 - 문서 내용과 답변 일치 여부 확인 및 사용된 출처 식별
        self.verification_prompt = PromptTemplate.from_template(
            """다음은 사용자 질문, 검색된 문서 내용, 그리고 생성된 답변입니다.
            생성된 답변이 검색된 문서의 내용을 정확하게 반영하고 있는지 검증해주세요.
            
            질문: {question}
            
            검색된 문서:
            {context}
            
            생성된 답변:
            {answer}
            
            검증 지침:
            1. 답변이 문서에 포함되지 않은 정보를 추가했는지 확인하세요.
            2. 답변이 문서의 중요한 정보를 누락했는지 확인하세요.
            3. 답변이 문서의 정보를 왜곡했는지 확인하세요.
            4. 답변에 실제로 사용된 문서의 출처만 식별하세요.
            
            검증 결과:
            1. 검증 결과: [정확함/부정확함]
            2. 불일치 내용 (있는 경우):
            3. 수정된 답변 (필요한 경우):
            4. 사용된 출처: (답변 생성에 실제로 사용된 문서의 출처만 열거하세요. 형식: [출처1, 출처2, ...])"""
        )
        
        # 요약 체인 생성
        self.summarize_prompt = PromptTemplate.from_template(
            """다음 문서 내용을 요약해주세요. 
            요약은 한글 기준 5~7문장으로 작성하세요.
            중년층이 이해하기 쉬운 명확한 어조로 작성하세요.
            문서의 핵심 내용과 중요 정보만 포함하세요.
            
            문서:
            {document}
            
            요약:"""
        )
        
        # 요약 체인에 LCEL 패턴 사용
        self.summarize_chain = self.summarize_prompt | self.llm | StrOutputParser()
        
        # RAG 체인 설정
        self._setup_rag_chain()
    
    def _transform_query_safe(self, question):
        """오류 처리가 포함된 안전한 쿼리 변환"""
        try:
            # 길이 제한 - 검색에 너무 긴 쿼리는 문제를 일으킬 수 있음
            if len(question) > 300:
                truncated = question[:300]
                logger.info(f"쿼리가 너무 길어 300자로 제한됨: '{truncated}...'")
                question = truncated
            
            # 간단한 고유명사 질문 패턴 확인 (다양한 패턴 감지를 위해 확장)
            import re
            patterns = [
                # 기본 패턴: '염성현이란?', '염성현이 뭐야?' 등
                r'^([가-힣a-zA-Z0-9]+)[이가](\s)*(는|란|이란|가)(\s)*(무엇|뭐|뭔가|뭘까|누구|어디|언제).*$',
                # 소유격 패턴: '염성현의 학번은?', '염성현의 소속은?' 등
                r'^([가-힣a-zA-Z0-9]+)의(\s)*(은|는|이|가|란).*$',
                # 직접 질문 패턴: '염성현은 어느 학교를 다니나요?'
                r'^([가-힣a-zA-Z0-9]+)(은|는|이|가)(\s)*([가-힣a-zA-Z0-9\s]+)(인가요|인가|하나요|하나|나요|까요|을까요|일까요).*$'
            ]
            
            for pattern in patterns:
                match = re.match(pattern, question)
                if match:
                    # 고유명사 추출
                    proper_noun = match.group(1)
                    logger.info(f"고유명사 질문 패턴 감지: '{question}' -> '{proper_noun}'")
                    return proper_noun
            
            # 오류 처리가 포함된 직접 호출
            transformed = self.query_transform_chain.invoke({"question": question})
            
            # 변환된 결과가 너무 길면 원본 사용
            if len(transformed) > len(question) * 1.5:
                logger.warning(f"변환된 쿼리가 너무 길어 원본 사용: '{transformed}'")
                return question
            
            logger.info(f"쿼리 변환: '{question}' -> '{transformed}'")
            return transformed
        except Exception as e:
            # 오류 발생 시 원본 쿼리 반환
            logger.error(f"쿼리 변환 실패: {e}")
            return question
    
    def _generate_alternative_queries(self, question):
        """원래 쿼리가 실패할 경우 대체 쿼리 생성"""
        try:
            alternatives_text = self.alternative_query_chain.invoke({"question": question})
            alternatives = [q.strip() for q in alternatives_text.split(',')]
            logger.info(f"대체 쿼리 생성: {alternatives}")
            return alternatives
        except Exception as e:
            logger.error(f"대체 쿼리 생성 실패: {e}")
            # 간단한 대체 쿼리 생성
            words = question.split()
            if len(words) > 2:
                return [' '.join(words[:2]), ' '.join(words[-2:])]
            return [question]  # 실패 시 원본 반환
            
    def _extract_key_entities(self, text):
        """텍스트에서 핵심 개체(인물, 조직, 장소 등) 추출"""
        try:
            # 간단한 정규표현식 기반 개체 추출
            import re
            # 한글 이름 패턴 (2-4자)
            kr_names = re.findall(r'[가-힣]{2,4}\s*(?:씨|님|교수|박사|학생)?', text)
            # 숫자 패턴 (학번 등)
            numbers = re.findall(r'\d{4,10}', text)
            # 조직명 패턴
            orgs = re.findall(r'[가-힣]{2,}(?:대학교|학교|기업|회사|조직|부서|팀)', text)
            
            entities = kr_names + numbers + orgs
            if entities:
                logger.info(f"추출된 핵심 개체: {entities}")
            return entities
        except Exception as e:
            logger.error(f"개체 추출 실패: {e}")
            return []
    
    def _setup_rag_chain(self):
        """LCEL을 사용한 RAG 파이프라인 설정"""
        # 문서 포맷 함수
        def format_docs(docs):
            formatted = []
            for i, doc in enumerate(docs):
                source = doc.metadata.get('source', '알 수 없는 출처')
                relevance = "높음" if i < 2 else "중간"  # 검색 순서에 따른 관련성 표시
                formatted.append(f"[문서 {i+1}] (관련성: {relevance})\n{doc.page_content}\n출처: {source}")
            return "\n\n".join(formatted)
        
        # 검색 체인 설정
        retriever = self.vector_store.similarity_search
        
        # 전체 RAG 파이프라인 - 쿼리 변환 문제를 피하기 위해 단순화
        self.rag_chain = (
            lambda x: {
                "context": format_docs(retriever(self._transform_query_safe(x["question"]))),
                "question": x["question"]
            }
            | self.qa_prompt
            | self.llm
            | StrOutputParser()
        )
    
    def _enhanced_document_search(self, question, attempts=2):
        """향상된 문서 검색 - 다중 검색 전략 적용"""
        all_docs = []
        seen_contents = set()  # 중복 제거를 위한 집합
        
        # 1. 기본 검색 - 변환된 쿼리
        transformed_query = self._transform_query_safe(question)
        
        for k in [4, 3]:  # 더 많은 문서로 시작해서 필터링
            try:
                docs = self.vector_store.similarity_search(transformed_query, k=k)
                if docs:
                    # 결과 추가
                    for doc in docs:
                        if doc.page_content not in seen_contents:
                            all_docs.append(doc)
                            seen_contents.add(doc.page_content)
                    # 충분한 결과가 있으면 중단
                    if len(all_docs) >= 3:
                        logger.info(f"변환된 쿼리로 충분한 문서 찾음: {len(all_docs)}개")
                        break
            except Exception as e:
                logger.error(f"변환된 쿼리 검색 오류 (k={k}): {e}")
                continue
        
        # 핵심 개체 기반 검색 - 추출된 개체가 있는 경우에만
        entities = self._extract_key_entities(question)
        for entity in entities:
            if len(entity) < 2:  # 너무 짧은 개체는 건너뜀
                continue
            try:
                entity_docs = self.vector_store.similarity_search(entity, k=2)
                for doc in entity_docs:
                    if doc.page_content not in seen_contents:
                        all_docs.append(doc)
                        seen_contents.add(doc.page_content)
                logger.info(f"개체 '{entity}'로 {len(entity_docs)}개 추가 문서 찾음")
            except Exception as e:
                logger.error(f"개체 검색 오류 (entity={entity}): {e}")
                continue
        
        # 2. 원본 질문으로 검색 (변환된 쿼리와 다른 경우)
        if transformed_query != question and attempts > 0:
            try:
                original_docs = self.vector_store.similarity_search(question, k=2)
                for doc in original_docs:
                    if doc.page_content not in seen_contents:
                        all_docs.append(doc)
                        seen_contents.add(doc.page_content)
                logger.info(f"원본 쿼리로 {len(original_docs)}개 추가 문서 찾음")
            except Exception as e:
                logger.error(f"원본 쿼리 검색 오류: {e}")
        
        # 3. 결과가 부족한 경우 대체 쿼리 생성 및 검색
        if len(all_docs) < 2 and attempts > 0:
            alternative_queries = self._generate_alternative_queries(question)
            for alt_query in alternative_queries[:2]:  # 최대 2개의 대체 쿼리만 사용
                try:
                    alt_docs = self.vector_store.similarity_search(alt_query, k=2)
                    for doc in alt_docs:
                        if doc.page_content not in seen_contents:
                            all_docs.append(doc)
                            seen_contents.add(doc.page_content)
                    logger.info(f"대체 쿼리 '{alt_query}'로 {len(alt_docs)}개 추가 문서 찾음")
                except Exception as e:
                    logger.error(f"대체 쿼리 검색 오류 (query={alt_query}): {e}")
                    continue
        
        # 관련성에 따라 정렬 (이 예시에서는 단순히 발견된 순서 유지)
        # 실제로는 관련성 점수에 따라 정렬하는 기능 추가 가능
        
        return all_docs
    
    def _verify_answer(self, question, context, answer):
        """생성된 답변이 문서 내용과 일치하는지 검증하고 실제 사용된 출처 식별"""
        try:
            verification_input = {
                "question": question,
                "context": context,
                "answer": answer
            }
            verification_result = self.verification_prompt | self.llm | StrOutputParser()
            result = verification_result.invoke(verification_input)
            
            # 검증 결과 파싱
            corrected_answer = answer
            used_sources = []
            
            if "정확함" in result:
                logger.info("답변 검증 완료: 정확함")
            elif "부정확함" in result and "수정된 답변" in result:
                # 수정된 답변 추출
                import re
                corrected = re.search(r'3\.\s*수정된\s*답변.*?:(.*?)(?:$|4\.)', result, re.DOTALL)
                if corrected:
                    corrected_answer = corrected.group(1).strip()
                    logger.info(f"답변 검증 후 수정됨")
            
            # 사용된 출처 추출
            import re
            sources_match = re.search(r'4\.\s*사용된\s*출처.*?:\s*\[(.*?)\]', result, re.DOTALL)
            if sources_match:
                sources_text = sources_match.group(1).strip()
                # 쉼표로 구분된 출처 목록 처리
                if sources_text:
                    used_sources = [s.strip().strip('"\'') for s in sources_text.split(',')]
                    logger.info(f"식별된 사용 출처: {used_sources}")
            
            return corrected_answer, used_sources
        except Exception as e:
            logger.error(f"답변 검증 오류: {e}")
            return answer, []  # 검증 실패 시 원본 반환
    
    def query(self, question):
        """RAG 체인을 통해 쿼리 실행"""
        try:
            if not question.strip():
                return "질문을 입력해주세요."
            
            # 질문 전처리 - 양쪽 공백 제거 및 마침표 추가
            processed_question = question.strip()
            if not processed_question.endswith(("?", ".", "!", "요")):
                processed_question += "?"
            
            # 향상된 문서 검색
            docs = self._enhanced_document_search(processed_question)
            
            # 문서를 찾지 못한 경우
            if not docs:
                # 벡터 DB 상태 확인
                try:
                    collection = self.vector_store.vector_db._collection
                    collection_stats = collection.count()
                    logger.warning(f"검색 결과 없음: 벡터 DB에 {collection_stats}개 문서 있음")
                    return f"관련 문서를 찾을 수 없습니다. 현재 벡터 DB에는 {collection_stats}개의 문서가 있습니다. 다른 질문을 시도하거나, '염성현'에 관한 문서를 추가해 보세요."
                except:
                    logger.warning("검색 결과 없음: 관련 문서를 찾을 수 없습니다")
                    return "관련 문서를 찾을 수 없습니다. '염성현'에 관한 정보가 포함된 문서를 업로드했는지 확인해 주세요."
            
            # 문서 포맷팅
            context = ""
            all_sources = {}  # 출처와 문서 내용을 매핑
            
            for i, doc in enumerate(docs):
                source = doc.metadata.get('source', '알 수 없는 출처')
                relevance_score = "높음" if i < 2 else "중간"  # 간단한 관련성 점수
                context += f"[문서 {i+1}] (관련성: {relevance_score})\n{doc.page_content}\n출처: {source}\n\n"
                all_sources[source] = doc.page_content
            
            # QA 프롬프트 생성 및 실행
            final_prompt = self.qa_prompt.format(question=processed_question, context=context)
            
            # 답변 생성
            answer = self.llm.invoke(final_prompt)
            
            # 답변 검증 및 필요시 수정, 실제 사용된 출처 식별
            verified_answer, used_sources = self._verify_answer(processed_question, context, answer)
            
            # 출처 정보 처리
            if not "찾을 수 없습니다" in verified_answer and not "없습니다" in verified_answer:
                # 이미 출처가 포함되어 있는지 확인
                has_source = any(source in verified_answer for source in all_sources.keys())
                
                # 사용된 출처만 표시
                if not has_source and used_sources:
                    # 식별된 사용 출처가 있는 경우
                    sources_text = ", ".join([f"'{s}'" for s in used_sources])
                    verified_answer += f"\n\n출처: {sources_text}"
                elif not has_source and not used_sources:
                    # 사용된 출처가 식별되지 않았을 때 전통적인 방식으로 출처 추가
                    # 문서 내용과 답변 간 유사도를 기반으로 관련 출처 감지
                    import re
                    most_relevant_source = None
                    max_overlap = 0
                    
                    # 답변에서 핵심 키워드 추출
                    answer_words = re.findall(r'[가-힣a-zA-Z0-9]{2,}', verified_answer)
                    if answer_words:
                        # 각 문서와 답변 간 단어 중복 확인
                        for source, content in all_sources.items():
                            content_words = re.findall(r'[가-힣a-zA-Z0-9]{2,}', content)
                            overlap = sum(1 for word in answer_words if word in content_words)
                            if overlap > max_overlap:
                                max_overlap = overlap
                                most_relevant_source = source
                    
                    if most_relevant_source:
                        verified_answer += f"\n\n출처: '{most_relevant_source}'"
            
            return verified_answer
            
        except Exception as e:
            logger.error(f"RAG 체인 쿼리 오류: {e}")
            return "죄송합니다. 질문 처리 중 오류가 발생했습니다. 다시 시도해주세요."
    
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