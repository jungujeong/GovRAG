# 한국어 RAG 성능 개선을 위한 모델 가이드

## 🚀 권장 모델 변경 순서

### 1단계: 더 우수한 한국어 모델 설치

```bash
# 1순위: EEVE (한국어 특화) - 강력 추천
ollama pull bnksys/yanolja-eeve-korean-instruct-10.8b

# 2순위: Solar (업스테이지 한국어 특화)
ollama pull solar:10.7b

# 3순위: Qwen2 (우수한 다국어 성능)
ollama pull qwen2:7b

# 4순위: Llama 3.1 (일반적으로 우수)
ollama pull llama3.1:8b
```

### 2단계: .env 파일 수정

```bash
# .env 파일에서 다음 라인 수정:
OLLAMA_MODEL=bnksys/yanolja-eeve-korean-instruct-10.8b

# 또는 다른 모델 선택:
# OLLAMA_MODEL=solar:10.7b
# OLLAMA_MODEL=qwen2:7b  
# OLLAMA_MODEL=llama3.1:8b
```

### 3단계: RAG 최적화 설정

```bash
# 한국어 특성에 맞는 추가 설정
TEMPERATURE=0.2              # 더 일관된 답변
CHUNK_SIZE=800              # 한국어에 최적화된 청크 크기
CHUNK_OVERLAP=150           # 문맥 보존 개선
```

## 📊 모델별 한국어 성능 비교

| 모델 | 한국어 성능 | 메모리 사용량 | 속도 | 추천도 |
|------|-------------|---------------|------|--------|
| **EEVE-Korean-10.8B** | ⭐⭐⭐⭐⭐ | 높음 | 보통 | 🥇 최고 |
| **Solar-10.7B** | ⭐⭐⭐⭐⭐ | 높음 | 보통 | 🥈 매우좋음 |
| **Qwen2-7B** | ⭐⭐⭐⭐ | 보통 | 빠름 | 🥉 좋음 |
| **Llama3.1-8B** | ⭐⭐⭐ | 보통 | 빠름 | 👍 무난 |
| **Gemma3** | ⭐⭐ | 낮음 | 빠름 | ❌ 제한적 |

## 🛠️ 즉시 적용 방법

1. **터미널에서 모델 설치:**
   ```bash
   ollama pull bnksys/yanolja-eeve-korean-instruct-10.8b
   ```

2. **.env 파일 수정:**
   ```bash
   OLLAMA_MODEL=bnksys/yanolja-eeve-korean-instruct-10.8b
   ```

3. **애플리케이션 재시작:**
   ```bash
   streamlit run app.py
   ```

## 🎯 EEVE 모델의 특별한 장점

### 한국어 특화 훈련
- 대규모 한국어 코퍼스로 훈련
- 한국어 문법과 어순에 최적화
- 한국 문화와 맥락 이해 능력

### Instruction Following 최적화
- 지시사항 이해 및 수행 능력 탁월
- RAG 시스템의 프롬프트에 정확한 반응
- 문서 기반 질의응답에 특화

### 공문서 및 전문용어 처리
- 정부 문서, 법률 문서 이해 능력
- 전문 용어와 약어 정확한 처리
- 격식체와 존댓말 자연스러운 생성

## 💡 추가 개선사항

### 프롬프트 최적화
- 한국어 문맥에 특화된 지시문 사용
- 더 구체적인 답변 가이드라인 제시

### 검색 성능 개선  
- BM25 + 벡터 검색 하이브리드 방식 활용
- 한국어 토크나이저 최적화

### 문서 처리 개선
- 한국어 문서 특성에 맞는 청킹 전략
- 문장 단위 분할 개선

## ⚠️ 시스템 요구사항

### 메모리 요구사항
- **최소**: 16GB RAM
- **권장**: 32GB RAM 이상
- **GPU**: 선택사항 (CPU로도 동작)

### 성능 최적화 팁
```bash
# Ollama 서버 시작 시 메모리 설정
OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 ollama serve
``` 