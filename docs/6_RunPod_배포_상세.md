# RunPod Deployment Guide
**Project**: SUT Preprocessing with DeepSeek-OCR
**Date**: 2025-10-23

---

## 1. DeepSeek-OCR의 OCR 능력 ✅

**중요 발견**: DeepSeek-OCR는 **스캔 문서를 직접 처리**할 수 있습니다!

### 내장 OCR 기능
- ✅ **텍스트 레이어 없는 스캔 문서** 직접 처리 가능
- ✅ **이미지에서 텍스트 추출** (Free OCR 모드)
- ✅ **마크다운 변환** (구조 보존)
- ✅ **맞춤형 프롬프트** 지원 (항목, 키워드, 요약 추출)

### 지원 프롬프트 예시
```python
# 1. 기본 OCR
prompt = "<image>\nFree OCR. "

# 2. 마크다운 변환
prompt = "<image>\n<|grounding|>Convert the document to markdown. "

# 3. 구조화된 분석 (우리 프로젝트용)
prompt = """<image>
<|grounding|>Extract:
1. 항목 (Items): List all section headings
2. 키워드 (Keywords): 10 important technical terms
3. 자연어 요약 (Summary): 2-3 sentence summary
"""
```

**결론**: 별도 OCR 솔루션 불필요, DeepSeek-OCR만으로 충분

---

## 2. RunPod 환경 설정

### 2.1 Pod 사양 권장사항

**최소 사양**:
- GPU: NVIDIA RTX 3090 (24GB VRAM)
- CPU: 8 cores
- RAM: 32GB
- Storage: 50GB

**권장 사양**:
- GPU: NVIDIA RTX 4090 or A100 (40GB VRAM)
- CPU: 16 cores
- RAM: 64GB
- Storage: 100GB

**예상 비용** (시간당):
- RTX 3090: $0.44/hr
- RTX 4090: $0.69/hr
- A100 40GB: $1.89/hr

### 2.2 템플릿 선택
RunPod에서 다음 템플릿 선택:
- **PyTorch 2.1+** (CUDA 12.1)
- 또는 **Transformers** (HuggingFace 최적화)

---

## 3. 배포 스크립트

### 3.1 자동 설정 스크립트

프로젝트에 포함된 스크립트:
- `runpod_setup.sh` - 환경 설정 자동화
- `runpod_test.py` - 테스트 및 검증

### 3.2 설정 단계

**Step 1: RunPod Pod 시작**
```bash
# RunPod Web UI에서 Pod 생성
# Template: PyTorch 2.1+ (CUDA 12.1)
# GPU: RTX 3090 or 4090
```

**Step 2: 프로젝트 업로드**
```bash
# 방법 1: Git (권장)
cd /workspace
git clone https://github.com/your-repo/sut-preprocess.git
cd sut-preprocess

# 방법 2: 직접 업로드
# RunPod UI에서 파일 업로드 또는 rsync 사용
```

**Step 3: 자동 설정 실행**
```bash
chmod +x runpod_setup.sh
./runpod_setup.sh
```

설치 내용:
- System packages (poppler-utils, etc.)
- PyTorch with CUDA 12.1
- Transformers 4.46.3
- DeepSeek-OCR model (~12GB download)
- 프로젝트 dependencies

**Step 4: PDF 파일 업로드**
```bash
# test_samples 디렉토리에 PDF 업로드
mkdir -p test_samples
# RunPod UI 또는 scp로 파일 업로드
```

**Step 5: 테스트 실행**
```bash
python runpod_test.py
```

---

## 4. 테스트 스크립트 세부사항

`runpod_test.py`는 3가지 테스트 수행:

### Test 1: Free OCR
- 프롬프트: `"Free OCR."`
- 목적: 모든 텍스트 추출
- 출력: `test1_free_ocr.txt`

### Test 2: Markdown 변환
- 프롬프트: `"Convert the document to markdown."`
- 목적: 구조 보존하며 텍스트 추출
- 출력: `test2_markdown.md`

### Test 3: 구조화된 분석
- 프롬프트: 맞춤형 (항목, 키워드, 요약)
- 목적: 프로젝트 요구사항에 맞춘 추출
- 출력: `test3_structured.txt`

### 예상 성능
- 페이지당 처리 시간: **30-60초** (RTX 4090 기준)
- 5페이지 문서: **3-5분**

---

## 5. Claude Code on RunPod ❌

**중요**: Claude Code는 **RunPod에서 사용 불가능**합니다.

### 이유
- Claude Code는 **로컬 개발 환경 전용** 도구
- VSCode 확장 또는 CLI로만 실행
- 클라우드 VM에서 직접 실행 불가

### 대안

**옵션 1: 로컬-RunPod 하이브리드**
```
M1 Mac (Claude Code로 개발)
    ↓
Git Push
    ↓
RunPod (GPU로 실행)
    ↓
결과 다운로드
    ↓
M1 Mac (Claude Code로 분석)
```

**옵션 2: RunPod에서 수동 실행**
```bash
# RunPod SSH 접속
ssh runpod@pod-xxxxx

# 직접 Python 실행
cd /workspace/sut-preprocess
python runpod_test.py
```

**옵션 3: Jupyter Notebook (권장)**
RunPod는 Jupyter Lab 제공:
```
https://your-pod-id.runpod.io/lab
```
- 웹 브라우저에서 코드 실행
- 실시간 결과 확인
- 파일 다운로드 가능

---

## 6. 워크플로우 권장사항

### 개발 단계
1. **M1 Mac + Claude Code**:
   - 파이프라인 로직 개발
   - 테스트 스크립트 작성
   - Git commit & push

### 실행 단계
2. **RunPod GPU**:
   - Git pull로 최신 코드 받기
   - DeepSeek-OCR 실행
   - 결과 파일 생성

### 분석 단계
3. **M1 Mac + Claude Code**:
   - RunPod에서 결과 다운로드
   - Claude Code로 분석
   - 개선사항 반영

---

## 7. 파일 구조

### RunPod에서 생성될 파일
```
/workspace/sut-preprocess/
├── runpod_setup.sh           # 설정 스크립트
├── runpod_test.py             # 테스트 스크립트
├── test_samples/              # PDF 입력
│   └── TP-030-030-030.pdf
├── runpod_outputs/            # 결과 출력
│   ├── test_page_1.png
│   ├── test1_free_ocr.txt
│   ├── test2_markdown.md
│   └── test3_structured.txt
└── models/                    # DeepSeek-OCR 모델
    └── deepseek-ocr/          (~12GB)
```

---

## 8. 비용 최적화

### Pod 사용 전략
- **개발 중**: Pod 중지, 스토리지만 유지 ($0.10/GB/month)
- **실행 필요시**: Pod 시작, 작업 완료 후 즉시 중지
- **장기 작업**: Spot 인스턴스 사용 (최대 70% 할인)

### 예상 비용 (5페이지 문서 1개 처리)
```
RTX 4090 Pod: $0.69/hr
처리 시간: ~10분 (설정 포함)
비용: ~$0.12
```

### 비용 절감 팁
1. 모델 다운로드 후 스냅샷 저장 (재사용)
2. 배치 처리 (여러 문서 한 번에)
3. Spot 인스턴스 활용
4. 작업 완료 즉시 Pod 중지

---

## 9. 문제 해결

### CUDA Out of Memory
```python
# runpod_test.py에서 설정 조정
base_size = 640  # 1024 → 640
image_size = 512  # 640 → 512
```

### 모델 다운로드 실패
```bash
# 수동 다운로드
huggingface-cli download deepseek-ai/DeepSeek-OCR --cache-dir ./models/deepseek-ocr
```

### PDF 변환 오류
```bash
# Poppler 재설치
apt-get update
apt-get install --reinstall poppler-utils
```

---

## 10. 다음 단계

### RunPod 배포 후
1. ✅ 첫 번째 테스트 실행 (`runpod_test.py`)
2. ✅ 결과 검증 (OCR 품질 확인)
3. ⏳ 전체 5페이지 처리
4. ⏳ 프로젝트 파이프라인 통합
5. ⏳ 배치 처리 스크립트 작성

### M1 Mac 개발 환경
- ✅ 파이프라인 로직은 M1에서 개발 가능
- ✅ Claude Code로 코드 작성/분석
- ✅ Git으로 RunPod와 동기화
- ❌ DeepSeek-OCR 실행은 RunPod 필요

---

## 요약

| 항목 | M1 Mac | RunPod GPU |
|------|--------|------------|
| Claude Code | ✅ 사용 가능 | ❌ 불가능 |
| DeepSeek-OCR | ❌ CUDA 필요 | ✅ 실행 가능 |
| 개발/분석 | ✅ 권장 | ⚠️ 제한적 |
| OCR 처리 | ❌ 불가능 | ✅ 필수 |
| 비용 | $0 | ~$0.10/문서 |

**권장 워크플로우**: M1 Mac (개발) → RunPod (실행) → M1 Mac (분석)
