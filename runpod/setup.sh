#!/bin/bash
# RunPod 환경 설정 스크립트
# DeepSeek-OCR 프로젝트 초기 설정

set -e  # 에러 발생 시 중단

echo "============================================================"
echo "DeepSeek-OCR RunPod 환경 설정"
echo "============================================================"

# 1. 시스템 패키지 설치
echo -e "\n[1/7] 시스템 패키지 설치..."
apt-get update && apt-get install -y poppler-utils
echo "✅ poppler-utils 설치 완료"

# 2. 시스템 정보 확인
echo -e "\n[2/7] 시스템 정보 확인..."
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
python --version

# 3. 작업 디렉토리 설정
echo -e "\n[3/7] 작업 디렉토리 설정..."

# 스크립트가 실행되는 위치에서 프로젝트 루트 찾기
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(dirname "$SCRIPT_DIR")"

cd "$WORK_DIR"
echo "✅ 작업 디렉토리: $WORK_DIR"

# 4. Python 가상환경 생성
echo -e "\n[4/7] Python 가상환경 설정..."
if [ ! -d ".venv" ]; then
    python -m venv .venv
    echo "✅ 가상환경 생성 완료"
else
    echo "✅ 기존 가상환경 사용"
fi

source .venv/bin/activate

# 5. 의존성 설치
echo -e "\n[5/7] 의존성 패키지 설치..."
pip install --upgrade pip

# PyTorch with CUDA 12.1 support
echo "PyTorch 설치 중..."
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# vLLM 환경 변수 설정
echo "vLLM 환경 변수 설정..."
export VLLM_USE_V1=0
export CUDA_VISIBLE_DEVICES=0

# Check CUDA version for TRITON_PTXAS_PATH
CUDA_VERSION=$(nvcc --version 2>/dev/null | grep -oP 'release \K[0-9.]+' || echo "unknown")
if [[ "$CUDA_VERSION" == "11.8" ]]; then
    export TRITON_PTXAS_PATH="/usr/local/cuda-11.8/bin/ptxas"
    echo "CUDA 11.8 detected - TRITON_PTXAS_PATH set"
fi

# Install from requirements.txt (includes vllm>=0.6.0)
echo "requirements.txt에서 패키지 설치 중 (vLLM 포함)..."
pip install -r requirements.txt

echo "✅ 패키지 설치 완료 (vLLM 포함)"

# 6. DeepSeek-OCR 모델 다운로드 확인
echo -e "\n[6/7] DeepSeek-OCR 모델 확인..."
MODEL_DIR="./models/DeepSeek-OCR"

if [ -d "$MODEL_DIR" ] && [ "$(ls -A $MODEL_DIR)" ]; then
    echo "✅ 모델이 이미 다운로드되어 있습니다: $MODEL_DIR"
else
    echo "⚠️ 모델이 없습니다. 다운로드를 시작합니다..."
    python << 'PYTHON'
from transformers import AutoModel, AutoTokenizer
import time

model_name = "deepseek-ai/DeepSeek-OCR"
cache_dir = "./models/DeepSeek-OCR"

start = time.time()
print("모델 다운로드 중 (6.2GB, 약 3-5분 소요)...")

tokenizer = AutoTokenizer.from_pretrained(
    model_name,
    trust_remote_code=True,
    cache_dir=cache_dir
)

model = AutoModel.from_pretrained(
    model_name,
    trust_remote_code=True,
    cache_dir=cache_dir,
    torch_dtype="auto"
)

elapsed = time.time() - start
print(f"✅ 모델 다운로드 완료! ({elapsed/60:.1f}분 소요)")
PYTHON
fi

# 7. 출력 디렉토리 생성
echo -e "\n[7/7] 출력 디렉토리 생성..."
mkdir -p outputs/cropped_images/{graph,table,diagram,complex_image}
echo "✅ 출력 디렉토리 준비 완료"

# 설정 완료
echo -e "\n============================================================"
echo "✅ RunPod 환경 설정 완료!"
echo "============================================================"
echo "작업 디렉토리: $WORK_DIR"
echo "모델 위치: $MODEL_DIR"
echo "출력 위치: ./outputs/"
echo ""
echo "다음 명령으로 문서 처리를 시작하세요:"
echo "  python runpod/process.py --input pdfs/ --output outputs/"
echo "============================================================"
