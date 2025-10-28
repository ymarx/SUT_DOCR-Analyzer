# RunPod 배포 가이드

DeepSeek-OCR 프로젝트를 RunPod에서 실행하기 위한 가이드입니다.

---

## 📋 사전 준비

### 1. RunPod 계정 및 Pod 생성
- [RunPod.io](https://runpod.io) 가입
- GPU Pod 생성 (권장: RTX 4090 24GB)
- SSH 접속 설정

### 2. 권장 Pod 사양
| GPU | VRAM | 처리 속도 | 시간당 비용 |
|-----|------|----------|------------|
| RTX 3090 | 24GB | 60-90초/페이지 | ~$0.40 |
| RTX 4090 | 24GB | 40-60초/페이지 | ~$0.70 |
| A100 | 40GB | 30-50초/페이지 | ~$1.50 |

---

## 🚀 빠른 시작 (Web Terminal 방식 권장)

### Step 1: RunPod Pod 생성 및 접속

1. RunPod에서 GPU Pod 생성 (권장: RTX 4090 또는 A40)
2. Web Terminal 열기 (또는 SSH 접속)

### Step 2: 프로젝트 클론

```bash
# Web Terminal에서 실행
cd /workspace
git clone https://github.com/ymarx/SUT_DOCR-Analyzer.git
cd SUT_DOCR-Analyzer
```

### Step 3: 환경 설정 (자동화)

```bash
# 실행 권한 부여
chmod +x runpod/setup.sh

# 환경 설정 스크립트 실행
bash runpod/setup.sh
```

**setup.sh는 자동으로 다음을 수행합니다:**
- ✅ poppler-utils 시스템 패키지 설치
- ✅ Python 가상환경 생성 (.venv)
- ✅ PyTorch + CUDA 12.1 설치
- ✅ 모든 Python 의존성 설치 (requirements.txt)
  - hf_transfer (고속 다운로드)
  - addict, einops, easydict (DeepSeek-OCR 필수)
  - transformers, PyMuPDF, pdf2image 등
- ✅ DeepSeek-OCR 모델 다운로드 (6.2GB, 3-5분)
- ✅ 출력 디렉토리 생성

### Step 4: PDF 파일 업로드

**방법 1: Web Terminal 파일 업로드 기능 (간편)**
1. Web Terminal 상단의 "Upload" 버튼 클릭
2. `pdfs/` 디렉토리에 PDF 파일 업로드

**방법 2: rsync (대용량)**
```bash
# 로컬 터미널에서
rsync -avz --progress -e "ssh -p <PORT>" pdfs/ \
    root@<POD_IP>:/workspace/SUT_DOCR-Analyzer/pdfs/
```

### Step 5: 배치 처리 실행

```bash
# pdfs/ 디렉토리 생성 및 PDF 파일 업로드 후
mkdir -p pdfs

# 가상환경 활성화
source .venv/bin/activate

# 배치 처리 실행 (A40/RTX 4090)
python runpod/process.py \
    --input pdfs/ \
    --output outputs/ \
    --preset rtx4090

# RTX 4060 등 메모리 제한 시
python runpod/process.py \
    --input pdfs/ \
    --output outputs/ \
    --preset rtx4060
```

### Step 6: 결과 다운로드

```bash
# 로컬 터미널에서 결과 다운로드
rsync -avz --progress -e "ssh -p <PORT>" \
    root@<POD_IP>:/workspace/SUT_DOCR-Analyzer/outputs/ \
    ./outputs/
```

---

## 🎛️ 고급 사용법

### 병렬 처리 (GPU 메모리 충분시)

```bash
# 2개 문서 동시 처리 (48GB 이상 권장)
python runpod/process.py \
    --input pdfs/ \
    --output outputs/ \
    --preset rtx4090 \
    --max-workers 2
```

### Resume 모드 (중단된 작업 재개)

```bash
# 이미 처리된 파일 건너뛰기
python runpod/process.py \
    --input pdfs/ \
    --output outputs/ \
    --resume
```

### 단일 문서 처리

```bash
# CLI 사용
python -m deepseek_ocr.cli.main process \
    --pdf "TP-030-030-030 노열관리 및 보상기준.pdf" \
    --output outputs/ \
    --preset rtx4090
```

---

## 📊 성능 최적화

### RTX 4090 최적화 설정

```python
# configs/rtx4090.yaml
deepseek_ocr:
  device: "cuda"
  dtype: "bfloat16"        # RTX 4090은 bfloat16 지원
  batch_size: 1
  base_size: 1280          # 고해상도
  image_size: 1024
  max_memory:
    cuda:0: "23GB"         # 24GB 중 23GB 사용
```

### 메모리 모니터링

```bash
# GPU 사용량 실시간 모니터링
watch -n 1 nvidia-smi
```

---

## 💰 비용 계산

### 예상 처리 비용 (RTX 4090 기준)

| 문서 | 페이지 수 | 예상 시간 | 비용 ($0.70/시간) |
|------|----------|----------|------------------|
| 단일 문서 | 5 | 4-6분 | $0.05-0.07 |
| 10개 문서 | 50 | 40-60분 | $0.47-0.70 |
| 100개 문서 | 500 | 7-10시간 | $4.90-7.00 |

**절약 팁**:
- 문서 모아서 배치 처리
- 처리 완료 후 즉시 Pod 종료
- RTX 3090 사용 시 40% 비용 절감 (속도 20% 감소)

---

## 🔧 문제 해결

### 1. CUDA Out of Memory

**증상**: `RuntimeError: CUDA out of memory`

**해결**:
```bash
# float32 → float16 변경
python runpod/process.py --preset rtx4090  # dtype=bfloat16

# 또는 base_size 줄이기
python runpod/process.py --preset rtx4060  # base_size=1024
```

### 2. 모델 다운로드 실패

**증상**: `Connection timeout`

**해결**:
```bash
# 수동 다운로드
cd /workspace/sut-preprocess
source .venv/bin/activate

python << 'PYTHON'
from transformers import AutoModel, AutoTokenizer

model = AutoModel.from_pretrained(
    "deepseek-ai/DeepSeek-OCR",
    cache_dir="./models/deepseek-ocr",
    trust_remote_code=True
)
PYTHON
```

### 3. PDF 파싱 오류

**증상**: `Unable to get page count. Is poppler installed and in PATH?`

**원인**: poppler-utils 미설치 (pdf2image 의존성)

**해결**:
```bash
# poppler-utils 설치
apt-get update && apt-get install -y poppler-utils

# 설치 확인
pdftoppm -v
```

### 4. 의존성 패키지 누락

**증상**: `ImportError: No module named 'addict'` (또는 einops, easydict, hf_transfer)

**원인**: DeepSeek-OCR 필수 패키지 미설치

**해결**:
```bash
# 가상환경 활성화
source .venv/bin/activate

# 누락된 패키지 설치
pip install addict einops easydict hf_transfer

# 또는 전체 재설치
pip install -r requirements.txt
```

### 5. 모델 다운로드 관련 오류

**증상**: `ValueError: hf_transfer package is not available`

**해결**:
```bash
pip install hf_transfer

# 모델 수동 다운로드
python << 'EOF'
from transformers import AutoModel, AutoTokenizer
model = AutoModel.from_pretrained(
    "deepseek-ai/DeepSeek-OCR",
    cache_dir="./models/DeepSeek-OCR",
    trust_remote_code=True,
    torch_dtype="auto"
)
EOF
```

---

## 📁 출력 구조

```
outputs/
├── document1_docjson.json
├── document2_docjson.json
├── batch_summary.json
└── cropped_images/
    ├── graph/
    │   ├── graph_p1_e0.png
    │   └── graph_p2_e3.png
    ├── table/
    ├── diagram/
    └── complex_image/
```

---

## 🔄 워크플로우 예시

### 일괄 처리 워크플로우

```bash
# 1. RunPod Pod 시작
# 2. 프로젝트 업로드
rsync -avz sut-preprocess-main/ root@pod:/workspace/sut-preprocess/

# 3. 환경 설정
ssh root@pod
cd /workspace/sut-preprocess
bash runpod/setup.sh

# 4. PDF 업로드
# (로컬에서) rsync -avz pdfs/ root@pod:/workspace/sut-preprocess/pdfs/

# 5. 배치 처리
python runpod/process.py --input pdfs/ --output outputs/

# 6. 결과 다운로드
# (로컬에서) rsync -avz root@pod:/workspace/sut-preprocess/outputs/ ./outputs/

# 7. Pod 종료 (비용 절감)
```

---

## 📝 주의사항

1. **데이터 백업**: RunPod Pod는 종료 시 데이터가 삭제됩니다. 반드시 결과를 다운로드하세요.

2. **비용 관리**: 처리 완료 후 Pod를 즉시 종료하여 불필요한 비용을 방지하세요.

3. **Claude Code 없음**: RunPod에는 Claude Code가 설치되어 있지 않습니다. 디버깅은 로컬에서 수행하세요.

4. **GPU 선택**:
   - 소량 처리: RTX 3090 (가성비)
   - 대량 처리: RTX 4090 (속도)
   - 최대 성능: A100 (비용 높음)

---

## 📚 참고 문서

- [RunPod_Deployment_Guide.md](../docs/RunPod_Deployment_Guide.md) - 상세 배포 가이드
- [IMPLEMENTATION_STATUS.md](../docs/IMPLEMENTATION_STATUS.md) - 구현 상태
- [DeepSeek_OCR_Master_Plan.md](../docs/DeepSeek_OCR_Master_Plan.md) - 전체 전략

---

**마지막 업데이트**: 2025-10-23
