# HWP 문서 기반 RAG 챗봇 시스템

폐쇄망 환경에서 동작하는 한글(HWP) 문서 기반 RAG 챗봇 시스템입니다.

## 기능

- HWP 문서 분석 및 요약
- 문서 기반 질문-답변 제공 (RAG)
- 벡터 DB를 활용한 유사도 검색
- 완전한 폐쇄망 환경에서 작동 (외부 API 없음)
- 문서 관리 (업로드, 삭제, 요약)

## 시스템 아키텍처

```
[Windows HWP 처리 서버] <-> [메인 서버(Mac/Ubuntu)] <-> [클라이언트]
```

- Windows 서버 (IP: 192.168.0.2): HWP 파일 처리
- 메인 서버 (IP: 192.168.0.3): RAG 시스템 및 웹 인터페이스
- 클라이언트: 웹 브라우저로 접속

## 기술 스택

- Python 3.8+
- Streamlit (UI)
- LangChain (RAG 프레임워크)
- Ollama (로컬 LLM)
- ChromaDB (벡터 데이터베이스)
- FastAPI (Windows HWP 서버)
- pywin32 (HWP 문서 처리, Windows 전용)

## 설치 방법

### 1. Windows HWP 서버 설치

1. Windows 서버(192.168.0.2)에 다음 설치:
   - Python 3.8 이상
   - 한글(HWP) 프로그램
   - Git (선택사항)

2. 저장소 클론:
```bash
git clone [repository_url]
cd hwp_server
```

3. 의존성 설치:
```bash
pip install -r hwp_server/requirements.txt
```

4. 서버 실행:
```bash
cd hwp_server
python server.py
```

### 2. 메인 서버 설치

1. 메인 서버(192.168.0.3)에 다음 설치:
   - Python 3.8 이상
   - [Ollama](https://ollama.ai/) 설치 및 실행

2. 저장소 클론:
```bash
git clone [repository_url]
cd [repository_name]
```

3. 의존성 설치:
```bash
pip install -r requirements.txt
```

4. Ollama 모델 설치:
```bash
# LLM 모델 설치
ollama pull gemma3

# 임베딩 모델 설치 (다음 중 하나 이상)
ollama pull llama2  # 임베딩에 권장
ollama pull all-minilm  # 경량 임베딩 모델
```

## 서버 실행 방법

### Windows HWP 서버 실행
```bash
cd hwp_server
python server.py
```

### 메인 서버 실행
```bash
# Ollama 서버 실행
ollama serve

# 애플리케이션 실행
streamlit run app.py
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

## 환경 설정

### Windows HWP 서버 (.env)
```
HWP_SERVER_URL=http://192.168.0.2:8000
```

### 메인 서버 (.env)
```
OLLAMA_MODEL=gemma3
OLLAMA_BASE_URL=http://localhost:11434
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
TEMPERATURE=0.1
VECTOR_DB_PATH=./data/vector_db
HWP_SERVER_URL=http://192.168.0.2:8000
```

## 주요 기능 사용법

### 문서 업로드

1. 사이드바에서 "HWP 문서 업로드" 섹션 사용
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

- Windows 서버와 메인 서버 간 통신은 내부 네트워크에서만 이루어짐
- 파일 업로드 크기 제한: 100MB
- API 키 기반 인증 구현 (향후 추가 예정)

## 주의사항

- Windows 서버는 반드시 Windows 운영체제에서 실행해야 합니다 (pywin32 패키지 요구)
- 메인 서버는 Mac/Ubuntu 환경에서 실행됩니다
- 각 서버는 지정된 IP 주소에서 실행되어야 합니다 
