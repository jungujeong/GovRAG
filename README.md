# HWP 문서 기반 RAG 챗봇 시스템

폐쇄망 환경에서 동작하는 한글(HWP) 문서 기반 RAG 챗봇 시스템입니다.

## 주요 기능

- HWP 문서 분석 및 요약 (Linux/Mac OS 지원)
- 문서 기반 질의응답
- 임베딩 모델 선택 가능
- 문서 관리(업로드, 삭제)

## 시스템 구성

**단일 서버 구성**
```
[메인 서버(Mac/Ubuntu/Windows)] <-> [클라이언트]
```

## 시스템 아키텍처

- RAG 시스템 및 웹 인터페이스
- hwplib (Java 기반)을 사용한 HWP 파일 처리
- Ollama 기반 로컬 언어 모델

## 기술 스택

- Python 3.8+
- Streamlit (UI)
- LangChain (RAG 프레임워크)
- Ollama (로컬 LLM)
- ChromaDB (벡터 데이터베이스)
- hwplib (Java 기반 HWP 처리)
- JPype (Python-Java 연동)

## 설치 방법

### 시스템 요구사항

1. 다음 환경이 필요합니다:
   - Python 3.8 이상
   - [Ollama](https://ollama.ai/) 설치 및 실행
   - Java 8 이상 (HWP 파일 처리용)

2. 저장소 클론:
```bash
git clone [repository_url]
cd [repository_name]
```

3. 의존성 설치:
```bash
pip install -r requirements.txt
```

4. Java 설치
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install openjdk-11-jdk

# CentOS/RHEL
sudo yum install java-11-openjdk-devel

# macOS (Homebrew)
brew install openjdk@11
```

5. Ollama 모델 설치:
```bash
# LLM 모델 설치
ollama pull gemma3

# 임베딩 모델 설치 (다음 중 하나 이상)
ollama pull nomic-embed-text  # 권장 임베딩 모델
ollama pull llama2  # 대체 임베딩 모델
```

## 서버 실행 방법

```bash
# Ollama 서버 실행
ollama serve

# 애플리케이션 실행
streamlit run app.py
# 또는 외부 접속을 허용하는 경우
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

## 환경 설정 (.env)

```
# LLM 모델 선택
OLLAMA_MODEL=gemma3

# 임베딩 모델 선택
EMBEDDING_MODELS=nomic-embed-text

# 기타 설정
OLLAMA_BASE_URL=http://localhost:11434
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
TEMPERATURE=0.1
VECTOR_DB_PATH=./data/vector_db

# 자바 환경 설정 (필요시)
# JAVA_HOME=/path/to/your/java
```

## 주요 기능 사용법

### 문서 업로드

1. 사이드바에서 "HWP/PDF 문서 업로드" 섹션 사용
2. 파일 선택(최대 100개) 후 "처리하기" 버튼 클릭
3. 업로드된 문서는 자동으로 벡터 DB에 저장됨

### 문서 관리

- "문서 관리" 섹션에서 업로드된 문서 목록 확인
- 문서 삭제 버튼으로 개별 문서 삭제 가능

### 문서 요약

- "문서 요약" 섹션에서 문서 선택 후 요약 버튼 클릭
- 한글 기준 5~7문장으로 요약됨

### 질문-답변

메인 화면의 채팅 인터페이스에서 질문 입력 시 문서 기반 답변 제공

## 보안 고려사항

- 파일 업로드 크기 제한: 기본 1MB (MAX_FILE_SIZE 환경 변수로 조정 가능)
- 필요시 API 키 기반 인증 구현 (향후 추가 예정)

## HWP 파일 처리 상세

### 텍스트 추출 동작 방식
1. hwplib(Java 기반)를 JPype로 호출하여 HWP 텍스트 추출
2. 최신 한글(XML 기반 HWPX)과 레거시 한글(OLE2 바이너리) 형식 모두 지원
3. 복잡한 한글 파일의 경우 대체 추출 방식 자동 적용

### 지원되는 HWP 파일 형식
- 한글 97 ~ 최신 버전 (2022+)
- 바이너리 형식 (.hwp)
- XML 기반 형식 (.hwp 또는 .hwpx)
