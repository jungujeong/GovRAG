# Windows 설치 및 사용 가이드

Windows 환경에서 RAG 시스템을 설치하고 사용하는 방법입니다.

## 🔧 사전 요구사항

### 필수 프로그램
1. **Python 3.8+** - [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. **Node.js 18+** - [https://nodejs.org/](https://nodejs.org/)

### 선택 프로그램
1. **Tesseract OCR** - [https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
   - 한국어 언어팩 포함 설치 필요
2. **Git** - [https://git-scm.com/download/win](https://git-scm.com/download/win)

## 🚀 설치 방법

### 방법 1: 자동 설치 (권장)
```cmd
# Python 설치 스크립트 사용
python install.py
```

### 방법 2: 배치 파일 사용
```cmd
# 배치 스크립트 사용
scripts\install.bat
```

### 방법 3: PowerShell 사용
```powershell
# PowerShell 스크립트 사용
scripts\install.ps1
```

### 방법 4: 수동 설치
```cmd
# 1. Python 패키지 설치
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 2. 프론트엔드 패키지 설치
cd frontend
npm install
cd ..

# 3. 프로젝트 구조 설정
scripts\setup.bat
```

## 🏃‍♂️ 실행 방법

### 방법 1: Python 런처 (권장)
```cmd
python run.py
```

### 방법 2: 배치 파일
```cmd
scripts\run.bat
```

### 방법 3: PowerShell
```powershell
scripts\run.ps1
```

### 방법 4: 수동 실행
```cmd
# 터미널 1: 백엔드 시작
cd backend
set PYTHONPATH=.
python -m uvicorn main:app --reload --port 8000

# 터미널 2: 프론트엔드 시작
cd frontend
npm run dev
```

## 📋 주요 명령어

### 문서 인덱싱
```cmd
# 방법 1
scripts\index.bat

# 방법 2
cd backend
python -c "import asyncio; from processors.indexer import index_all_documents; asyncio.run(index_all_documents())"
```

### 인덱스 관리
```cmd
# 백업 생성
scripts\index-backup.bat

# 백업에서 복원
scripts\index-restore.bat

# 무결성 검증
scripts\index-verify.bat

# 손상된 인덱스 수리
scripts\index-repair.bat

# 백업 목록 확인
scripts\index-list.bat

# 오래된 백업 정리
scripts\index-clean.bat
```

### 시스템 정리
```cmd
scripts\clean.bat
```

## 🛠️ Windows 특화 설정

### PowerShell 실행 정책 설정
PowerShell 스크립트를 사용하려면 실행 정책을 변경해야 할 수 있습니다:

```powershell
# 관리자 권한으로 PowerShell 실행 후
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 환경 변수 설정
시스템 환경 변수에 다음을 추가하면 편리합니다:

1. **Python 경로**: Python 설치 디렉토리
2. **Node.js 경로**: Node.js 설치 디렉토리  
3. **Tesseract 경로**: Tesseract 설치 디렉토리

### 방화벽 설정
Windows Defender 방화벽에서 다음 포트를 허용해야 할 수 있습니다:
- **포트 8000**: 백엔드 서버
- **포트 5173**: 프론트엔드 개발 서버

## 🐛 문제 해결

### "python이 인식되지 않습니다" 오류
```cmd
# Python 경로를 환경변수에 추가하거나 전체 경로 사용
C:\Python312\python.exe install.py
```

### "npm이 인식되지 않습니다" 오류
- Node.js를 재설치하거나 환경변수에 추가
- 시스템 재부팅 후 다시 시도

### 포트 충돌 오류
```cmd
# 8000번 포트 사용 중인 프로세스 확인
netstat -ano | findstr :8000

# 프로세스 종료 (PID 확인 후)
taskkill /PID <PID번호> /F
```

### Tesseract 관련 오류
1. Tesseract 재설치 (한국어 팩 포함)
2. 환경변수에 Tesseract 경로 추가
3. 시스템 재부팅

### 모듈 Import 오류
```cmd
# pip 업그레이드 후 재설치
python -m pip install --upgrade pip
python -m pip install -r requirements.txt --force-reinstall
```

### Git 관련 오류 (선택사항)
- Git for Windows 설치: [https://git-scm.com/download/win](https://git-scm.com/download/win)
- Git Bash 사용 권장

## 📊 성능 최적화

### Windows에서 더 나은 성능을 위해:

1. **Windows Terminal 사용** (Windows 11/10)
2. **WSL2 고려** (Linux 하위 시스템)
3. **SSD 사용** (인덱싱 속도 향상)
4. **충분한 RAM** (8GB 이상 권장)
5. **바이러스 검사 제외** (프로젝트 폴더를 실시간 검사에서 제외)

## 🆘 추가 도움말

### 로그 확인
```cmd
# 백엔드 로그
type logs\backend.log

# 시스템 로그
type logs\system.log
```

### 완전 초기화
```cmd
# 모든 생성된 파일 삭제
scripts\clean.bat

# 종속성 재설치
python install.py
```

### 지원 요청
문제가 지속되면 다음 정보와 함께 도움을 요청하세요:
- Windows 버전
- Python 버전 (`python --version`)
- Node.js 버전 (`node --version`)
- 오류 메시지 전문
- 수행한 단계

이 가이드를 따르면 Windows 환경에서 안정적으로 RAG 시스템을 사용할 수 있습니다.