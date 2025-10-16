# Claude Code 안정적인 설치 및 관리 가이드

## 현재 설치 상태
- **버전**: 1.0.120 (Claude Code)
- **설치 경로**: `/Users/YMARX/.claude/local/claude`
- **설치 방식**: npm 기반 로컬 설치 (자동 업데이트 문제 회피)

## ✅ 기존 설정 유지 확인
**API 키 설정**: 정상 (CLAUDE_CODE_OAUTH_TOKEN 환경변수로 자동 설정됨)
- 구독자 키가 그대로 유지되어 있으며, 별도 재설정 불필요

## 🛡️ 재발 방지 설정

### 1. 백업 완료
```bash
# 설정 백업 위치
~/claude-backup-20250930/
```

### 2. 자동 업데이트 비활성화 유지
현재 로컬 설치 방식으로 자동 업데이트가 비활성화되어 있음.
npm 패키지 버전을 고정하여 예기치 않은 업데이트 방지.

### 3. 수동 업데이트 방법 (필요시에만)
```bash
# 1. 현재 설정 백업
cp -r ~/.claude ~/claude-backup-$(date +%Y%m%d)/

# 2. 버전 확인
claude --version

# 3. 업데이트가 꼭 필요한 경우에만 수행
cd ~/.claude/local
npm update @anthropic-ai/claude-code

# 4. 문제 발생시 백업에서 복구
rm -rf ~/.claude
cp -r ~/claude-backup-YYYYMMDD/.claude ~/
```

### 4. 안정성 체크리스트
- [ ] 정기 백업 (월 1회)
- [ ] 업데이트 전 릴리즈 노트 확인
- [ ] 업데이트 후 테스트 환경에서 먼저 검증
- [ ] 문제 발생시 즉시 백업 복구

## ⚠️ 주의사항
1. **자동 업데이트 명령 실행 금지**: `claude update` 명령 사용하지 말 것
2. **새로운 설치 스크립트 주의**: `curl -fsSL http://claude.ai/install.sh | bash` 사용 시 기존 설정 덮어쓰기 가능
3. **환경변수 유지**: CLAUDE_CODE_OAUTH_TOKEN이 설정되어 있는지 주기적 확인

## 📋 문제 발생시 복구 절차
1. 백업에서 ~/.claude 디렉토리 복구
2. 터미널 재시작
3. `claude --version`으로 정상 작동 확인

## 추가 보안 설정
```bash
# alias 설정으로 실수 방지
echo "alias claude-update='echo \"업데이트 전 백업 필요! 수동으로 진행하세요.\"'" >> ~/.zshrc
source ~/.zshrc
```

---
*마지막 업데이트: 2025-09-30*
*현재 안정 버전: 1.0.120*