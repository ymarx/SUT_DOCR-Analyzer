# Claude Code 네이티브 마이그레이션 가이드

## 📅 마이그레이션 전 체크리스트

### 1. 현재 상태 백업 ✅
```bash
# 이미 완료: ~/claude-backup-20250930/
```

### 2. 추가 백업 (선택사항)
```bash
# 마이그레이션 직전 최신 백업
cp -r ~/.claude ~/claude-backup-before-native-$(date +%Y%m%d-%H%M)/
```

## 🚀 마이그레이션 절차

### 단계 1: 현재 상태 확인
```bash
# 현재 버전 및 설치 타입 확인
claude --version
which claude
```

### 단계 2: 자동 마이그레이션 (권장)
```bash
# Claude 자체 마이그레이션 도구 사용
claude migrate-installer
```

### 단계 3: 네이티브 설치 (자동 실패시)
```bash
# macOS/Linux
curl -fsSL https://claude.ai/install.sh | bash

# Windows
irm https://claude.ai/install.ps1 | iex
```

### 단계 4: 검증
```bash
# 설치 확인
claude doctor
claude --version

# API 키 확인 (자동 유지되어야 함)
env | grep CLAUDE_CODE_OAUTH_TOKEN
```

## 🔙 롤백 절차 (문제 발생시)

### 방법 1: npm 버전으로 복귀
```bash
# 네이티브 제거
rm -rf ~/.claude/local/claude

# npm 버전 재설치
npm install -g @anthropic-ai/claude-code@1.0.120
```

### 방법 2: 백업에서 복구
```bash
# 전체 설정 복구
rm -rf ~/.claude
cp -r ~/claude-backup-20250930/.claude ~/
```

## ⚡ 새 기능 활용법

### 체크포인트 시스템
```bash
# 작업 전 체크포인트 생성
/checkpoint

# 문제 발생시 롤백
/rewind
# 또는 Esc 키 두번
```

### 보안 검토
```bash
# 코드 보안 자동 검토
/security-review
```

### 사용량 확인
```bash
# 토큰 사용량 등 확인
/usage
```

## ⚠️ 주의사항

1. **설치 충돌 방지**
   - npm과 네이티브 동시 설치 금지
   - 하나만 유지

2. **알려진 이슈**
   - 유휴 CPU 사용량 3% (모니터링 필요)
   - Node.js v22 감지 오류 (무시 가능)

3. **설정 자동 보존**
   - `~/.claude/` 내 모든 설정 자동 유지
   - API 키 환경변수 자동 보존

## 📊 기대 효과

| 항목 | npm (현재) | 네이티브 (신규) | 개선율 |
|------|-----------|----------------|--------|
| 시작 시간 | ~3초 | ~1초 | 66% ↓ |
| 메모리 사용 | 기준 | -15% | 15% ↓ |
| 대용량 파일 | 제한적 | 18,000줄+ | 대폭 개선 |
| 자동 업데이트 | 수동 | 자동 | ✅ |

## 🎯 권장사항

### 즉시 마이그레이션 추천
- 대규모 프로젝트 작업
- 성능이 중요한 경우
- 새 기능 필요시

### 현 상태 유지 추천
- 소규모 프로젝트만 작업
- 현재 안정적으로 작동 중
- 리스크 회피 우선

---
*작성일: 2025-09-30*
*현재 버전: npm 1.0.120 → 네이티브 최신*