# DeepSeek-OCR Document Processing Pipeline

**철강 기술 문서 전처리 시스템 - DeepSeek-OCR 전용**

---

## 🎯 개요

스캔된 철강 기술 문서(SUT)를 **DeepSeek-OCR 단일 모델**로 구조화된 DocJSON으로 변환하는 시스템입니다.

### ✨ 주요 특징

- **단일 모델**: DeepSeek-OCR만 사용 (별도 OCR/레이아웃 모델 불필요)
- **2-Pass 파이프라인**: 구조 분석 → 요소별 상세 분석
- **7-카테고리 분류**: text_header, text_section, text_paragraph, table, graph, diagram, complex_image
- **RAG 최적화**: [항목], [키워드], [자연어 요약] 자동 추출
- **RTX 4060 최적화**: float16 + 메모리 관리

---

## 🚀 빠른 시작

### 1. 저장소 클론

```bash
git clone <repository-url>
cd SUT_DOCR-Analyzer
```

### 2. 환경 설정

```bash
# .env 파일 생성
cp .env.example .env

# 사용 환경에 맞게 수정
# - M1/M2/M3 Mac: DEEPSEEK_DEVICE=mps, DEEPSEEK_DTYPE=float32
# - NVIDIA GPU (Linux/Windows): DEEPSEEK_DEVICE=cuda, DEEPSEEK_DTYPE=float16
# - CPU only: DEEPSEEK_DEVICE=cpu, DEEPSEEK_DTYPE=float32
```

### 3. 가상환경 및 의존성 설치

#### macOS (Apple Silicon)

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate

# 또는 자동 설치 스크립트 사용
chmod +x install_deepseek_macos.sh
./install_deepseek_macos.sh
```

#### Linux/Windows (NVIDIA GPU)

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# PyTorch 설치 (CUDA 12.1)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 프로젝트 의존성
pip install -r requirements.txt

# DeepSeek-OCR 의존성
pip install -r models/DeepSeek-OCR/requirements.txt
```

### 4. DeepSeek-OCR 모델 다운로드

모델은 첫 실행 시 자동으로 HuggingFace에서 다운로드됩니다 (~12.7GB).

수동 다운로드를 원하는 경우:

```bash
# HuggingFace CLI 사용
pip install huggingface_hub
huggingface-cli download deepseek-ai/DeepSeek-OCR --local-dir ./models/DeepSeek-OCR
```

### 5. 문서 처리

```bash
# 기본 (RTX 4060)
python -m deepseek_ocr.cli.main process \
    --pdf "document.pdf" \
    --output outputs/ \
    --preset rtx4060

# RTX 4090
python -m deepseek_ocr.cli.main process --preset rtx4090 --pdf "document.pdf"

# 간단한 예제
python example_usage.py --pdf "document.pdf"
```

---

## 📁 출력

```
outputs/
├── document_docjson.json
└── cropped_images/
    ├── graph/*.png
    ├── table/*.png
    ├── diagram/*.png
    └── complex_image/*.png
```

---

## 📊 성능

| GPU | 페이지당 | 5페이지 문서 | VRAM |
|-----|---------|------------|------|
| RTX 4060 | 90-120초 | 8-10분 | ~7.5GB |
| RTX 4090 | 40-60초 | 4-6분 | ~10GB |

---

## ☁️ RunPod 배포

```bash
# 설정
bash runpod/setup.sh

# 배치 처리
python runpod/process.py --input pdfs/ --output outputs/
```

상세: [runpod/README.md](runpod/README.md)

---

## 📚 문서

- [IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) - 구현 상태
- [DeepSeek_OCR_Master_Plan.md](docs/DeepSeek_OCR_Master_Plan.md) - 전체 설계
- [RunPod_Deployment_Guide.md](docs/RunPod_Deployment_Guide.md) - 배포 가이드

---

**상태**: Phase 1-4 완료 (70%)  
**업데이트**: 2025-10-23
