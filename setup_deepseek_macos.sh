#!/bin/bash
# DeepSeek-OCR 환경 설정 - macOS (CPU 모드)

set -e

echo "🍎 DeepSeek-OCR macOS 환경 설정 시작"
echo "================================================"

# 현재 디렉터리 확인
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "📁 프로젝트 경로: $PROJECT_ROOT"

# uv 설치 확인
if ! command -v uv &> /dev/null; then
    echo "📦 uv 설치 중..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
else
    echo "✅ uv 이미 설치됨: $(uv --version)"
fi

# Python 3.12.9 설치
echo ""
echo "🐍 Python 3.12.9 설치..."
uv python install 3.12.9

# 가상환경 생성
echo ""
echo "📦 가상환경 생성 (.venv)..."
uv venv --python 3.12.9

# 활성화 안내
echo ""
echo "✅ 가상환경 생성 완료!"
echo ""
echo "다음 명령으로 활성화하세요:"
echo "  source .venv/bin/activate"
echo ""
echo "활성화 후 다음 명령 실행:"
echo "  ./install_deepseek_macos.sh"
