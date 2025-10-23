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

## 🚀 빠른 시작

### Step 1: 프로젝트 업로드

```bash
# 로컬에서 RunPod로 프로젝트 전송
rsync -avz --progress sut-preprocess-main/ \
    root@<POD_IP>:/workspace/sut-preprocess/
```

### Step 2: 환경 설정

```bash
# RunPod SSH 접속
ssh root@<POD_IP>

# 환경 설정 스크립트 실행
cd /workspace/sut-preprocess
chmod +x runpod/setup.sh
bash runpod/setup.sh
```

설정 스크립트는 자동으로 다음을 수행합니다:
- Python 가상환경 생성
- 의존성 패키지 설치
- DeepSeek-OCR 모델 다운로드 (12.7GB, 5-10분)
- 출력 디렉토리 생성

### Step 3: PDF 파일 업로드

```bash
# 로컬에서 PDF 파일 업로드
rsync -avz --progress pdfs/ \
    root@<POD_IP>:/workspace/sut-preprocess/pdfs/
```

### Step 4: 배치 처리 실행

```bash
# 가상환경 활성화
cd /workspace/sut-preprocess
source .venv/bin/activate

# 배치 처리 실행
python runpod/process.py \
    --input pdfs/ \
    --output outputs/ \
    --preset rtx4090
```

### Step 5: 결과 다운로드

```bash
# 로컬에서 결과 다운로드
rsync -avz --progress \
    root@<POD_IP>:/workspace/sut-preprocess/outputs/ \
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

**증상**: `PDF parsing failed`

**해결**:
```bash
# poppler-utils 설치 (pdf2image 의존성)
apt-get update && apt-get install -y poppler-utils
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
