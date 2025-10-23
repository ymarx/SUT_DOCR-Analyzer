#!/bin/bash
# DeepSeek-OCR 의존성 설치 - macOS (CPU 모드)
# 주의: 가상환경 활성화 후 실행 (source .venv/bin/activate)

set -e

echo "🚀 DeepSeek-OCR 의존성 설치 (macOS CPU 모드)"
echo "================================================"

# 가상환경 확인
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "❌ 가상환경이 활성화되지 않았습니다!"
    echo "다음 명령을 먼저 실행하세요:"
    echo "  source .venv/bin/activate"
    exit 1
fi

echo "✅ 가상환경: $VIRTUAL_ENV"

# Python 버전 확인
PYTHON_VERSION=$(python --version | awk '{print $2}')
echo "🐍 Python 버전: $PYTHON_VERSION"

# 1. 기본 의존성 + DeepSeek CPU 패키지 설치
echo ""
echo "📦 1/5: 기본 의존성 설치..."
uv pip install -e ".[deepseek-cpu,dev]"

# 2. numpy 버전 다운그레이드 (PyTorch 호환성)
echo ""
echo "🔧 2/5: numpy 호환성 수정..."
uv pip install "numpy<2"

# 3. 디렉터리 생성
echo ""
echo "📁 3/5: 테스트 디렉터리 생성..."
mkdir -p deepseek_test/{test_samples,outputs,notebooks,benchmarks/results}
mkdir -p deepseek_test/outputs/cropped_images/{graph,table,diagram,complex_image}
mkdir -p configs
mkdir -p models/deepseek-ocr

# 4. 설정 파일 생성
echo ""
echo "⚙️ 4/5: 설정 파일 생성..."

# .env 파일
cat > .env << 'ENV'
# DeepSeek-OCR 환경 변수 (macOS CPU 모드)
DEEPSEEK_DEVICE=cpu
DEEPSEEK_DTYPE=float32
DEEPSEEK_BATCH_SIZE=1
DEEPSEEK_MODEL_CACHE=./models/deepseek-ocr
ENV

# deepseek_config.yaml
cat > configs/deepseek_config.yaml << 'YAML'
# DeepSeek-OCR 설정
model:
  name: "deepseek-ai/DeepSeek-OCR"
  cache_dir: "./models/deepseek-ocr"
  device: "cpu"  # macOS는 CPU 전용
  torch_dtype: "float32"  # CPU는 float32 사용

inference:
  # 해상도 모드
  resolution_modes:
    tiny: {base_size: 512, vision_tokens: 64}
    small: {base_size: 640, vision_tokens: 100}
    base: {base_size: 1024, vision_tokens: 256}
    large: {base_size: 1280, vision_tokens: 400}
    gundam: {base_size: 0, crop_mode: true, vision_tokens: 800}

  # 기본 설정
  default_mode: "small"  # macOS는 small 권장 (빠른 처리)
  batch_size: 1
  max_new_tokens: 512

# macOS 최적화
optimization:
  use_flash_attention: false  # CPU는 flash attention 미지원
  use_4bit_quantization: false
  gradient_checkpointing: false
YAML

# pipeline_config.yaml
cat > configs/pipeline_config.yaml << 'YAML'
# PDF 파싱 파이프라인 설정
pdf:
  dpi: 300  # PDF → 이미지 DPI
  image_format: "PNG"

classification:
  # 분류 카테고리
  categories:
    - text_header
    - text_section
    - text_paragraph
    - graph
    - table
    - diagram
    - complex_image

  # 분류 임계값
  confidence_threshold: 0.7

analysis:
  # 그래프 분석
  graph:
    extract_axes: true
    extract_legend: true
    extract_trend: true
    crop_and_save: true

  # 도표 분석
  table:
    extract_header: true
    extract_cells: true
    markdown_export: true
    crop_and_save: true

  # 다이어그램 분석
  diagram:
    extract_components: true
    extract_relationships: true
    mermaid_export: true
    max_components: 10
    crop_and_save: true

enrichment:
  # 컨텍스트 윈도우
  context_window: 2

  # 키워드 추출
  max_keywords: 10
  keyword_method: "tfidf"
YAML

echo "✅ 설정 파일 생성 완료"

# 5. DeepSeek 모델 다운로드 (선택)
echo ""
echo "📥 5/5: DeepSeek-OCR 모델 다운로드 (약 7GB, 5-10분 소요)"
read -p "모델을 지금 다운로드하시겠습니까? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "다운로드 중... (잠시 기다려주세요)"
    python << 'PYTHON'
from transformers import AutoModel, AutoTokenizer
import os

cache_dir = "./models/deepseek-ocr"
model_name = "deepseek-ai/DeepSeek-OCR"

print(f"모델 다운로드: {model_name}")
print(f"저장 위치: {cache_dir}")

try:
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
        cache_dir=cache_dir
    )
    print("✅ Tokenizer 다운로드 완료")

    model = AutoModel.from_pretrained(
        model_name,
        trust_remote_code=True,
        cache_dir=cache_dir
    )
    print("✅ Model 다운로드 완료")

    print(f"\n모델 크기: {os.popen(f'du -sh {cache_dir}').read().strip()}")

except Exception as e:
    print(f"❌ 다운로드 실패: {e}")
    print("나중에 다시 시도할 수 있습니다.")
PYTHON
else
    echo "⏭️ 모델 다운로드 생략 (나중에 자동 다운로드됨)"
fi

# 완료 메시지
echo ""
echo "================================================"
echo "✅ DeepSeek-OCR 환경 설정 완료!"
echo "================================================"
echo ""
echo "📝 설치된 패키지 확인:"
python -c "
import torch
import transformers
print(f'  - PyTorch: {torch.__version__}')
print(f'  - Transformers: {transformers.__version__}')
print(f'  - CUDA 사용 가능: {torch.cuda.is_available()}')
"

echo ""
echo "🎯 다음 단계:"
echo "  1. 기본 테스트: python -c 'import torch; print(torch.__version__)'"
echo "  2. PDF 샘플 테스트: python deepseek_test/notebooks/01_basic_test.py"
echo "  3. Jupyter 노트북: jupyter notebook deepseek_test/notebooks/"
echo ""
echo "📚 문서:"
echo "  - [문서5] DeepSeek-OCR 테스트 프로젝트 설계.md"
echo "  - configs/deepseek_config.yaml"
echo "  - configs/pipeline_config.yaml"
