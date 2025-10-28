# DeepSeek-OCR 의존성 가이드

이 문서는 프로젝트 설치 중 발견된 모든 의존성 문제와 해결책을 정리합니다.

## 설치 문제 이력

### 1. hf_transfer (HuggingFace 고속 다운로드)
**문제**: `ValueError: Fast download using 'hf_transfer' is enabled but package not available`
**원인**: RunPod 환경에서 `HF_HUB_ENABLE_HF_TRANSFER=1` 설정되어 있으나 패키지 미설치
**해결**: `pip install hf_transfer>=0.1.9`

### 2. addict (딕셔너리 유틸리티)
**문제**: `ImportError: This modeling file requires the following packages: addict`
**원인**: DeepSeek-OCR의 modeling_deepseekocr.py에서 필요
**해결**: `pip install addict>=2.4.0`

### 3. einops (텐서 연산)
**문제**: `ImportError: No module named 'einops'`
**원인**: DeepEncoder (Vision Encoder) 구성에 필요
**해결**: `pip install einops>=0.8.0`

### 4. easydict (딕셔너리 유틸리티)
**문제**: `ImportError: No module named 'easydict'`
**원인**: DeepEncoder 설정 파일에서 사용
**해결**: `pip install easydict>=1.13`

### 5. poppler-utils (PDF 변환 도구)
**문제**: `Unable to get page count. Is poppler installed and in PATH?`
**원인**: pdf2image가 PDF를 이미지로 변환할 때 시스템 도구 필요
**해결**: `apt-get install -y poppler-utils` (Ubuntu/Debian)

## 시스템 요구사항

### 운영체제
- Ubuntu 22.04+ (RunPod 기본 이미지)
- Debian 기반 Linux 배포판

### GPU
- **최소**: NVIDIA RTX 4060 (8GB VRAM)
  - FP16 최적화 필요
  - 단일 문서 처리만 가능

- **권장**: NVIDIA RTX 4090 (24GB VRAM) 또는 A40 (48GB VRAM)
  - 병렬 처리 가능
  - 배치 크기 증가 가능

### Python
- Python 3.10+ (3.12 테스트 완료)

## 의존성 설치 방법

### 방법 1: requirements.txt (권장)
```bash
# PyTorch with CUDA 12.1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 나머지 패키지
pip install -r requirements.txt

# 시스템 패키지 (Ubuntu/Debian)
sudo apt-get update && sudo apt-get install -y poppler-utils
```

### 방법 2: conda environment
```bash
# Conda 환경 생성
conda env create -f environment.yml

# 환경 활성화
conda activate deepseek-ocr

# 시스템 패키지는 별도 설치 필요
sudo apt-get install -y poppler-utils
```

### 방법 3: RunPod 자동 설정
```bash
# setup.sh 실행 (모든 의존성 자동 설치)
bash runpod/setup.sh
```

## 패키지 버전 정보

### 핵심 패키지
| 패키지 | 버전 | 용도 |
|--------|------|------|
| torch | >=2.0.0 | 딥러닝 프레임워크 |
| transformers | 4.47.1 | HuggingFace 모델 로드 |
| PyMuPDF | >=1.24.0 | PDF 텍스트 추출 |
| pdf2image | >=1.17.0 | PDF → 이미지 변환 |
| Pillow | >=10.0.0 | 이미지 처리 |

### DeepSeek-OCR 전용
| 패키지 | 버전 | 용도 |
|--------|------|------|
| addict | >=2.4.0 | 모델 설정 관리 |
| einops | >=0.8.0 | 텐서 재배열 연산 |
| easydict | >=1.13 | Vision Encoder 설정 |
| hf_transfer | >=0.1.9 | 모델 고속 다운로드 |

### 시스템 패키지
| 패키지 | 용도 |
|--------|------|
| poppler-utils | PDF → 이미지 변환 (pdf2image 백엔드) |

## 모델 다운로드

### DeepSeek-OCR 모델
- **모델 ID**: `deepseek-ai/DeepSeek-OCR`
- **크기**: 6.2GB (BF16)
- **다운로드 시간**: 3-5분 (고속 네트워크 기준)
- **저장 위치**: `./models/DeepSeek-OCR`

### 자동 다운로드
setup.sh 실행 시 자동으로 다운로드됩니다:
```python
from transformers import AutoModel, AutoTokenizer

model_name = "deepseek-ai/DeepSeek-OCR"
cache_dir = "./models/DeepSeek-OCR"

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
```

## 가상환경 관리

### venv (권장)
```bash
# 생성
python -m venv .venv

# 활성화
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 비활성화
deactivate
```

### conda
```bash
# 생성
conda env create -f environment.yml

# 활성화
conda activate deepseek-ocr

# 비활성화
conda deactivate

# 삭제
conda env remove -n deepseek-ocr
```

## 트러블슈팅

### CUDA 버전 불일치
**증상**: `RuntimeError: CUDA error: no kernel image is available for execution`
**해결**: PyTorch CUDA 버전과 시스템 CUDA 버전 확인
```bash
# 시스템 CUDA 확인
nvcc --version
nvidia-smi

# PyTorch CUDA 버전 확인
python -c "import torch; print(torch.version.cuda)"
```

### Out of Memory (OOM)
**증상**: `RuntimeError: CUDA out of memory`
**해결**:
1. 프리셋 변경: `--preset rtx4060` (메모리 절약 모드)
2. 배치 크기 감소: `--max-workers 1`
3. 모델 정밀도 변경: FP16/BF16 사용

### PDF 파싱 실패
**증상**: `Unable to get page count. Is poppler installed and in PATH?`
**해결**:
```bash
# poppler 설치 확인
pdftoppm -v

# 미설치 시
sudo apt-get install -y poppler-utils  # Ubuntu/Debian
brew install poppler                    # macOS
```

### 모델 다운로드 느림
**증상**: 모델 다운로드가 매우 느림 (>10분)
**해결**:
```bash
# hf_transfer 설치 및 활성화
pip install hf_transfer
export HF_HUB_ENABLE_HF_TRANSFER=1
```

## 추가 리소스

- [DeepSeek-OCR GitHub](https://github.com/deepseek-ai/DeepSeek-OCR)
- [HuggingFace Model Card](https://huggingface.co/deepseek-ai/DeepSeek-OCR)
- [PyTorch Installation Guide](https://pytorch.org/get-started/locally/)
- [RunPod Documentation](https://docs.runpod.io/)
