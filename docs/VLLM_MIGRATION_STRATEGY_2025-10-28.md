# vLLM 기반 구조 전환 전략 문서
**작성일**: 2025-10-28
**목적**: HuggingFace Transformers → vLLM 기반 고속 추론 구조로 전환

---

## 🎯 전환 목표

### 1. 성능 최적화
- **추론 속도**: vLLM은 HF Transformers 대비 3-5배 빠름
- **메모리 효율**: PagedAttention으로 메모리 단편화 방지
- **배치 처리**: 동적 배치 처리로 GPU 활용률 극대화
- **확장성**: 19페이지 PDF 처리 시간 대폭 단축 (예상: 5분 → 2분 이내)

### 2. 공식 방식 준수
- **공식 vLLM 예제**: `DeepSeek-OCR-vllm/run_dpsk_ocr_pdf.py` 기반
- **검증된 구현**: 공식 레포지토리의 프로덕션 코드 활용
- **안정성**: 이미 검증된 설정과 파라미터 사용

### 3. 프로젝트 목표 유지
- ✅ 벡터 검색 최적화 (그래프/도표 자연어 요약)
- ✅ 7개 요소 분류 + 주변 정보 활용
- ✅ 키워드/자연어 요약 생성
- ✅ 2-Pass 파이프라인 유지

---

## 🏗️ 아키텍처 비교

### 현재 구조 (HF Transformers)
```
┌─────────────────────────────────────────┐
│ DeepSeekEngine (HF Transformers)        │
│ - AutoModel.from_pretrained()           │
│ - model.infer() 직접 호출               │
│ - 순차 처리 (페이지별)                  │
│ - output_path 임시 디렉토리 필요        │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│ 2-Pass Pipeline                          │
│ Pass 1: infer_structure() 19회           │
│ Pass 2: infer_element() N회              │
└─────────────────────────────────────────┘
```

### 목표 구조 (vLLM)
```
┌─────────────────────────────────────────┐
│ DeepSeekVLLMEngine (vLLM)               │
│ - LLM() 초기화 (1회)                    │
│ - llm.generate() 배치 처리              │
│ - 병렬 처리 (MAX_CONCURRENCY)           │
│ - PagedAttention 메모리 최적화          │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│ 2-Pass Pipeline (vLLM 최적화)           │
│ Pass 1: 배치 처리 (19 페이지 동시)      │
│ Pass 2: 배치 처리 (N 요소 동시)         │
└─────────────────────────────────────────┘
```

---

## 🔍 주요 차이점 분석

### HF Transformers vs vLLM API

| 항목 | HF Transformers | vLLM |
|------|-----------------|------|
| **모델 로딩** | `AutoModel.from_pretrained()` | `LLM(model=..., hf_overrides=...)` |
| **추론 호출** | `model.infer(tokenizer, prompt, image_file, output_path, ...)` | `llm.generate(batch_inputs, sampling_params)` |
| **이미지 전처리** | 내부 자동 처리 | 명시적 `DeepseekOCRProcessor()` 호출 |
| **배치 처리** | 순차 처리 (루프) | 동적 배치 처리 |
| **output_path** | 필수 (mkdir 호출) | 선택적 (후처리용) |
| **프롬프트 형식** | 문자열 직접 전달 | `{"prompt": ..., "multi_modal_data": ...}` dict |

### 핵심 변경 사항

#### 1. 모델 초기화
**HF Transformers**:
```python
self.model = AutoModel.from_pretrained(
    model_name,
    cache_dir=cache_dir,
    torch_dtype=torch.float16,
    device_map={"": 0},
    trust_remote_code=True,
)
```

**vLLM**:
```python
from vllm.model_executor.models.registry import ModelRegistry
from deepseek_ocr import DeepseekOCRForCausalLM

ModelRegistry.register_model("DeepseekOCRForCausalLM", DeepseekOCRForCausalLM)

llm = LLM(
    model="deepseek-ai/DeepSeek-OCR",
    hf_overrides={"architectures": ["DeepseekOCRForCausalLM"]},
    block_size=256,
    enforce_eager=False,
    trust_remote_code=True,
    max_model_len=8192,
    swap_space=0,
    max_num_seqs=MAX_CONCURRENCY,  # 동시 처리 수
    tensor_parallel_size=1,
    gpu_memory_utilization=0.9,
    disable_mm_preprocessor_cache=True
)
```

#### 2. 이미지 전처리
**vLLM 전용 전처리 필요**:
```python
from process.image_process import DeepseekOCRProcessor

processor = DeepseekOCRProcessor()
multi_modal_data = {
    "image": processor.tokenize_with_images(
        images=[image],
        bos=True,
        eos=True,
        cropping=CROP_MODE
    )
}
```

#### 3. 추론 호출
**HF Transformers**:
```python
response = self.model.infer(
    tokenizer=self.tokenizer,
    prompt="<image>\n<|grounding|>...",
    image_file="/tmp/temp.png",
    output_path="/tmp/output",
    base_size=1024,
    image_size=640,
    crop_mode=True,
    save_results=False,
)
```

**vLLM**:
```python
batch_inputs = [
    {
        "prompt": "<image>\n<|grounding|>...",
        "multi_modal_data": {"image": processed_image_data}
    }
    for processed_image_data in preprocessed_images
]

outputs = llm.generate(batch_inputs, sampling_params)
for output in outputs:
    response = output.outputs[0].text
```

#### 4. 샘플링 파라미터
```python
from vllm import SamplingParams
from process.ngram_norepeat import NoRepeatNGramLogitsProcessor

logits_processors = [
    NoRepeatNGramLogitsProcessor(
        ngram_size=20,
        window_size=50,
        whitelist_token_ids={128821, 128822}  # <td>,</td>
    )
]

sampling_params = SamplingParams(
    temperature=0.0,  # Greedy decoding
    max_tokens=8192,
    logits_processors=logits_processors,
    skip_special_tokens=False,
    include_stop_str_in_output=True,
)
```

---

## 📁 파일 구조 변경

### 신규 파일
```
src/deepseek_ocr/
├── engine/
│   ├── deepseek_vllm_engine.py   # 🆕 vLLM 엔진 (기존 deepseek_engine.py 대체)
│   ├── image_processor.py        # 🆕 이미지 전처리 (공식 코드 이식)
│   ├── logits_processor.py       # 🆕 NoRepeatNGramLogitsProcessor
│   └── prompts.py                # ✅ 기존 유지 (공식 프롬프트 사용)
│
├── pipeline/
│   ├── pdf_parser.py             # ✅ 기존 유지
│   ├── markdown_parser.py        # 🆕 신규 (markdown grounding 파싱)
│   ├── structure_analyzer_vllm.py # 🆕 vLLM 배치 처리 최적화
│   ├── element_analyzer_vllm.py   # 🆕 vLLM 배치 처리 최적화
│   └── text_enricher.py          # ✅ 기존 유지
│
└── core/
    ├── config.py                  # ✅ 수정 (vLLM 설정 추가)
    └── types.py                   # ✅ 기존 유지
```

### 설정 파일 업데이트
```python
# src/deepseek_ocr/core/config.py

@dataclass
class Config:
    # vLLM 전용 설정
    engine_type: str = "vllm"  # "vllm" or "hf"

    # vLLM 파라미터
    max_num_seqs: int = 100  # 동시 처리 시퀀스 수 (RTX 4090: 100, RTX 4060: 10)
    gpu_memory_utilization: float = 0.9  # GPU 메모리 활용률
    block_size: int = 256
    tensor_parallel_size: int = 1

    # 전처리 워커 수
    num_workers: int = 64  # 이미지 전처리 병렬 워커

    # 기존 설정 유지
    model_name: str = "deepseek-ai/DeepSeek-OCR"
    device: str = "cuda"
    dtype: str = "bfloat16"  # RTX 4090
    base_size: int = 1024
    image_size: int = 640
    crop_mode: bool = True
```

---

## 🔧 구현 단계

### Phase 1: 핵심 인프라 (vLLM 엔진)
**목표**: vLLM 기반 추론 엔진 구현

**작업**:
1. ✅ `src/deepseek_ocr/engine/image_processor.py` 생성
   - 공식 `process/image_process.py` 코드 이식
   - `DeepseekOCRProcessor` 클래스 구현

2. ✅ `src/deepseek_ocr/engine/logits_processor.py` 생성
   - 공식 `process/ngram_norepeat.py` 코드 이식
   - `NoRepeatNGramLogitsProcessor` 구현

3. ✅ `src/deepseek_ocr/engine/deepseek_vllm_engine.py` 생성
   - `DeepSeekVLLMEngine` 클래스 구현
   - 모델 초기화 (LLM)
   - 배치 추론 메서드
   - 메모리 관리

**검증**:
```python
# 단일 이미지 테스트
engine = DeepSeekVLLMEngine(config)
result = engine.infer(image, prompt)
print(result)
```

### Phase 2: 배치 처리 파이프라인
**목표**: 2-Pass 파이프라인의 vLLM 배치 처리 최적화

**작업**:
1. ✅ `src/deepseek_ocr/pipeline/structure_analyzer_vllm.py`
   - Pass 1 배치 처리 (전체 페이지 동시 처리)
   - 병렬 이미지 전처리 (ThreadPoolExecutor)
   - Markdown 파싱

2. ✅ `src/deepseek_ocr/pipeline/element_analyzer_vllm.py`
   - Pass 2 배치 처리 (전체 요소 동시 처리)
   - 요소별 크롭 + 전처리 병렬화
   - 컨텍스트 추출 최적화

**검증**:
```python
# 19 페이지 PDF 테스트
analyzer = PageStructureAnalyzerVLLM(engine)
structures = analyzer.analyze_batch(page_images)  # 19 페이지 배치 처리
```

### Phase 3: Markdown Parser (공식 방식)
**목표**: `<|ref|>...<|/ref|><|det|>...<|/det|>` 파싱

**작업**:
1. ✅ `src/deepseek_ocr/pipeline/markdown_parser.py` 생성
   - 정규식 기반 ref/det 추출 (공식 코드 참조)
   - 좌표 정규화 (0-999 → 0-1)
   - 7-Category 매핑

**검증**:
```python
# 공식 예제 출력 파싱
markdown = "<|ref|>table<|/ref|><|det|>[100,200,800,600]<|/det|>\n| A | B |\n"
elements = MarkdownParser().parse(markdown)
```

### Phase 4: 설정 및 통합
**목표**: 전체 파이프라인 통합 및 설정 업데이트

**작업**:
1. ✅ `src/deepseek_ocr/core/config.py` 업데이트
   - vLLM 전용 설정 추가
   - RTX 4090 / RTX 4060 프리셋

2. ✅ `src/deepseek_ocr/cli/main.py` 업데이트
   - vLLM 엔진 사용
   - 진행 상황 표시 (tqdm)

3. ✅ `runpod/process.py` 업데이트
   - vLLM 엔진으로 전환

**검증**:
```bash
python runpod/process.py --input pdfs/ --output outputs/ --preset rtx4090
```

### Phase 5: 의존성 및 환경 설정
**목표**: vLLM 의존성 추가 및 환경 구성

**작업**:
1. ✅ `requirements.txt` 업데이트
   ```
   vllm>=0.6.0
   # 기존 transformers는 유지 (vLLM이 내부적으로 사용)
   ```

2. ✅ `runpod/setup.sh` 업데이트
   - vLLM 설치
   - CUDA 환경 변수 설정

**검증**:
```bash
python -c "import vllm; print(vllm.__version__)"
```

---

## 🎯 성능 최적화 전략

### 1. 배치 처리 최적화
```python
# Pass 1: 전체 페이지 배치 처리
def analyze_batch(self, page_images: List[Image.Image]) -> List[PageStructure]:
    # 1. 병렬 전처리
    with ThreadPoolExecutor(max_workers=64) as executor:
        batch_inputs = list(executor.map(self._preprocess_image, page_images))

    # 2. vLLM 배치 추론 (1회 호출로 전체 처리)
    outputs = self.engine.llm.generate(batch_inputs, sampling_params)

    # 3. 병렬 파싱
    with ThreadPoolExecutor(max_workers=32) as executor:
        structures = list(executor.map(self._parse_output, outputs, page_images))

    return structures
```

### 2. 메모리 최적화
- **PagedAttention**: vLLM의 핵심 메모리 최적화
- **동적 배치**: `max_num_seqs`로 메모리 압력 조절
- **GPU 메모리 활용률**: RTX 4090 0.9, RTX 4060 0.75

### 3. GPU 설정
```python
# RTX 4090 (24GB)
max_num_seqs = 100  # 높은 병렬성
gpu_memory_utilization = 0.9

# RTX 4060 (8GB)
max_num_seqs = 10   # 제한된 병렬성
gpu_memory_utilization = 0.75
```

---

## ✅ 성공 기준

### 1. 성능 목표
- **처리 속도**: 19 페이지 PDF < 2분 (RTX 4090)
- **메모리 안정성**: OOM 없이 완료
- **처리량**: HF Transformers 대비 3-5배 향상

### 2. 기능 검증
- ✅ Pass 1: 배치 구조 분석 (19 페이지 동시)
- ✅ Pass 2: 배치 요소 분석 (N 요소 동시)
- ✅ Markdown 파싱 정확도
- ✅ 7-Category 분류
- ✅ 키워드/요약 생성

### 3. 품질 검증
- ✅ 공식 프롬프트 사용
- ✅ `<|ref|>...<|/ref|>` 파싱 정확도
- ✅ 주변 컨텍스트 추출
- ✅ DocJSON 출력 완성도

---

## 🚀 RunPod 배포 계획

### 1. 환경 설정
```bash
# vLLM 설치
pip install vllm>=0.6.0

# CUDA 환경 변수
export VLLM_USE_V1=0
export CUDA_VISIBLE_DEVICES=0
```

### 2. 테스트 시나리오
```bash
# 1단계: 단일 이미지 테스트
python test_vllm_engine.py

# 2단계: 3 페이지 PDF 테스트
python runpod/process.py --input pdfs/test_3pages.pdf --output outputs/

# 3단계: 전체 19 페이지 PDF 테스트
python runpod/process.py --input pdfs/ --output outputs/ --preset rtx4090
```

### 3. 성능 모니터링
```bash
# GPU 메모리 모니터링
watch -n 1 nvidia-smi

# 처리 속도 측정
time python runpod/process.py --input pdfs/ --output outputs/
```

---

## 📝 다음 단계

1. ✅ Phase 1: vLLM 엔진 구현
   - image_processor.py
   - logits_processor.py
   - deepseek_vllm_engine.py

2. ✅ Phase 2: 배치 파이프라인
   - structure_analyzer_vllm.py
   - element_analyzer_vllm.py

3. ✅ Phase 3: Markdown 파서
   - markdown_parser.py

4. ✅ Phase 4: 설정 및 통합
   - config.py 업데이트
   - main.py 업데이트

5. ✅ Phase 5: 의존성
   - requirements.txt
   - setup.sh

6. ✅ 테스트 및 검증
7. ✅ RunPod 배포

---

## 📚 참고 자료

- [vLLM 공식 문서](https://docs.vllm.ai/)
- [DeepSeek-OCR vLLM 예제](../models/DeepSeek-OCR/DeepSeek-OCR-master/DeepSeek-OCR-vllm/)
- [이전 HF Transformers 전략](./IMPLEMENTATION_STRATEGY_2025-10-28.md)
