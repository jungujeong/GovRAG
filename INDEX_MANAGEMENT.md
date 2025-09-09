# 인덱스 관리 가이드

Git 작업 중 인덱스 파일 손상을 방지하고 안전하게 관리하는 방법입니다.

## 🚨 문제 상황

문서를 업로드하고 인덱싱한 후 `git push` 등의 Git 작업을 수행하면 Whoosh 인덱스 파일이 손상될 수 있습니다. 이로 인해 다음과 같은 오류가 발생합니다:

```
TypeError: ord() expected a character, but string of length 0 found
ERROR: Application startup failed. Exiting.
```

## ✅ 해결책

### 1. 자동 보호 메커니즘

다음 기능들이 자동으로 작동합니다:

- **Git 저장소 보호**: `.gitignore`에 모든 인덱스 파일 제외
- **무결성 검사**: 시스템 시작 시 자동 인덱스 검증
- **자동 복구**: 손상된 인덱스 자동 감지 및 재생성
- **Git Hook**: `git push` 전 자동 백업 생성

### 2. 수동 관리 명령어

#### 백업 생성
```bash
make index-backup
```

#### 백업에서 복원
```bash
make index-restore
```

#### 인덱스 무결성 검증
```bash
make index-verify
```

#### 손상된 인덱스 수리
```bash
make index-repair
```

#### 백업 목록 확인
```bash
make index-list
```

#### 오래된 백업 정리 (최근 5개만 유지)
```bash
make index-clean
```

### 3. CLI 도구 직접 사용

더 세밀한 제어가 필요한 경우:

```bash
cd backend
python3 utils/index_manager.py --help

# 특정 백업에서 복원
python3 utils/index_manager.py restore --backup-name backup_1725876543

# 특정 개수의 백업 유지
python3 utils/index_manager.py clean --keep 10
```

## 📋 일반적인 워크플로우

### Git 작업 전 (권장)
```bash
# 1. 현재 인덱스 백업
make index-backup

# 2. Git 작업 수행
git add .
git commit -m "문서 추가"
git push

# 3. 시스템이 정상 동작하는지 확인
make run
```

### 문제 발생 시
```bash
# 1. 시스템 중지 (Ctrl+C)

# 2. 인덱스 상태 확인
make index-verify

# 3. 자동 수리 시도
make index-repair

# 4. 수리 실패 시 백업에서 복원
make index-restore

# 5. 시스템 재시작
make run
```

## 🔧 고급 설정

### 백업 보관 정책 변경

기본적으로 최근 5개 백업을 유지합니다. 변경하려면:

```bash
# 10개 백업 유지
cd backend
python3 utils/index_manager.py clean --keep 10
```

### Git Hook 비활성화

Git push 전 자동 백업을 원하지 않는 경우:

```bash
rm .git/hooks/pre-push
```

### 수동 백업 스케줄링

크론탭 등을 이용해 정기 백업 설정:

```bash
# 매일 오전 2시 백업
0 2 * * * cd /path/to/project && make index-backup
```

## 📊 모니터링

### 인덱스 상태 확인
```bash
make index-verify
```

출력 예시:
```
✅ Whoosh index integrity: PASS
✅ Whoosh functional test: PASS (150 docs)
✅ Index verification complete!
```

### 백업 상태 확인
```bash
make index-list
```

출력 예시:
```
🟢 Latest backup_1725876543 - 2024-09-09 14:32:23 (12.5MB)
🔵 Available backup_1725875123 - 2024-09-09 14:08:43 (12.1MB)
🔵 Available backup_1725873456 - 2024-09-09 13:37:36 (11.8MB)
```

## ⚠️ 주의사항

1. **백업 용량**: 문서가 많을수록 백업 크기가 증가합니다
2. **복원 시간**: 대용량 인덱스는 복원에 시간이 걸릴 수 있습니다
3. **디스크 공간**: 정기적으로 `make index-clean`으로 오래된 백업을 정리하세요
4. **Git 저장소**: 절대로 `data/` 디렉토리를 Git에 추가하지 마세요

## 🆘 문제 해결

### "No backups found" 오류
- 아직 백업이 생성되지 않았습니다
- `make index-backup`으로 백업을 먼저 생성하세요

### "Auto-repair failed" 메시지
- 백업이 없거나 백업도 손상된 경우입니다
- `make clean && make index`로 인덱스를 재생성하세요

### 성능 저하
- 백업이 너무 많이 쌓였을 수 있습니다
- `make index-clean`으로 정리하세요

이 가이드를 따르면 Git 작업으로 인한 인덱스 손상을 방지하고 안전하게 시스템을 운영할 수 있습니다.