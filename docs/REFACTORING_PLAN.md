# DeepSeek-OCR 공식 API 통합 리팩토링 계획

**작성일**: 2025-10-28
**목표**: 공식 API를 정확히 따르면서 기존 기능 100% 보존
**상태**: 계획 단계

---

## 🎯 프로젝트 핵심 기능 (보존 필수)

### 기획된 핵심 아키텍처
1. **2-Pass 파이프라인**
   - Pass 1: `<|grounding|>` 모드로 페이지 전체 구조 분석 → Bounding Box 검출
   - Pass 2: 검출된 요소별 상세 분석 (crop → 타입별 프롬프트)

2. **7-Category 요소 분류**
   - text_header, text_section, text_paragraph
   - table, graph, diagram, complex_image

3. **DocJSON 생성**
   - 한국어 철강 기술문서 특화 ([항목], [키워드], [자연어 요약])
   - 섹션 트리 구조 (numbering 기반 계층)
   - 이미지 추출 및 저장 (graph, table, diagram 등)

4. **RTX 4060 8GB 최적화**
   - float16/bfloat16 dtype
   - 메모리 관리 (@torch.no_grad(), CUDA cache clearing)
   - Lazy loading, 모델 unload

---

## 🔍 현재 문제 분석

### 1. 프롬프트 포맷 문제 (CRITICAL)

**현재 코드 (deepseek_engine.py:109):**
```python
formatted_prompt = f"<｜User｜>: {prompt}\n\n<｜Assistant｜>:"
# ❌ 전각 문자 사용 (잘못됨!)
# ❌ 수동 포맷팅
```

**공식 구현 (modeling_deepseekocr.py:710-722, 741):**
```python
conversation = [
    {
        "role": "<|User|>",  # ✅ 반각 문자
        "content": f'{prompt}',  # 이미 <image> 포함
        "images": [f'{image_file}'],
    },
    {"role": "<|Assistant|>", "content": ""},
]
prompt = format_messages(conversations=conversation, sft_format='plain', system_prompt='')
```

**영향도**:
- 🔴 CRITICAL: 모델이 프롬프트를 제대로 이해하지 못할 가능성
- 🔴 전체 Pass 1, Pass 2 추론에 영향

### 2. 이미지 전달 방식 문제

**현재:**
```python
response = self.model.infer(
    prompt=formatted_prompt,  # 잘못된 포맷
    image_file=image,         # PIL Image 객체
)
```

**공식:**
- conversation에 images 리스트 포함
- `load_pil_images(conversation)` 함수로 추출
- `dynamic_preprocess()` + `image_transform()` 전처리

**영향도**:
- 🟡 MEDIUM: 모델은 작동하지만 전처리 누락
- 이미지 품질 최적화 불가

### 3. 이미지 전처리 파이프라인 누락

**공식 구현 (modeling_deepseekocr.py:773-850):**
```python
# 1. Dynamic preprocessing (large image → crops)
if crop_mode and (image.size[0] > 640 or image.size[1] > 640):
    images_crop_raw, crop_ratio = dynamic_preprocess(image)

# 2. Global view with padding
global_view = ImageOps.pad(image, (base_size, base_size))

# 3. Normalization
image_transform = BasicImageTransform(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5))
images_list.append(image_transform(global_view).to(torch.bfloat16))

# 4. Local views (cropped patches)
for crop in images_crop_raw:
    images_crop_list.append(image_transform(crop).to(torch.bfloat16))
```

**현재 상황**:
- ❌ 위 전처리 전혀 사용하지 않음
- PIL Image를 직접 전달

**영향도**:
- 🟡 MEDIUM: 고해상도 문서 처리 시 성능 저하
- 1280×1280 이상에서 품질 저하 가능

---

## 📋 리팩토링 전략

### 원칙
1. ✅ **기능 보존**: 2-Pass, 7-Category, DocJSON 생성 로직 100% 유지
2. ✅ **점진적 수정**: 한 번에 하나씩, 테스트 후 커밋
3. ✅ **공식 API 준수**: modeling_deepseekocr.py의 infer() 사용 방식 정확히 따름
4. ✅ **하위 호환성**: 기존 Config, 프롬프트 구조 최대한 유지

### 접근 방법: **Wrapper Layer 패턴**

공식 infer() 메서드는 그대로 사용하되, 우리의 2-Pass 로직을 위한 wrapper 생성

```python
# 공식 API는 건드리지 않음
model.infer(tokenizer, prompt, image_file, ...)

# 우리가 만드는 것
class DeepSeekEngine:
    def infer(self, image, prompt):
        # 공식 포맷으로 변환
        response = self.model.infer(
            self.tokenizer,
            prompt=prompt,  # 이미 <image> 태그 포함
            image_file=image,
            base_size=self.config.base_size,
            image_size=self.config.image_size,
            crop_mode=self.config.crop_mode,
        )
        return response
```

---

## 🔧 구체적 수정 계획

### Phase 1: 프롬프트 포맷 수정 (CRITICAL)

**파일**: `src/deepseek_ocr/engine/deepseek_engine.py`

**현재 (109번 라인):**
```python
formatted_prompt = f"<｜User｜>: {prompt}\n\n<｜Assistant｜>:"
```

**수정 후:**
```python
# 프롬프트는 이미 올바른 형식 (<image>\n<|grounding|>...)
# 공식 infer()가 내부에서 format_messages() 호출
# 우리는 건드리지 않음!
```

**변경 사항**:
- ❌ 삭제: 수동 포맷팅 (109번 라인)
- ✅ 유지: 프롬프트를 그대로 전달 (prompts.py는 이미 올바름)

**테스트**:
```python
# prompts.py의 STRUCTURE_ANALYSIS_PROMPT 확인
assert prompt.startswith("<image>")
assert "<|grounding|>" in prompt
# ✅ 이미 올바른 형식!
```

### Phase 2: infer() 메서드 단순화

**파일**: `src/deepseek_ocr/engine/deepseek_engine.py`

**현재 (114-121번 라인):**
```python
response = self.model.infer(
    tokenizer=self.tokenizer,
    prompt=formatted_prompt,  # ❌ 잘못된 포맷
    image_file=image,
    base_size=self.config.base_size,
    image_size=self.config.image_size,
    crop_mode=self.config.crop_mode,
)
```

**수정 후:**
```python
response = self.model.infer(
    tokenizer=self.tokenizer,
    prompt=prompt,  # ✅ prompts.py에서 온 원본 그대로
    image_file=image,  # PIL Image 객체 (공식 API 지원)
    base_size=self.config.base_size,
    image_size=self.config.image_size,
    crop_mode=self.config.crop_mode,
)
```

**변경 사항**:
- ❌ 삭제: `formatted_prompt` 변수 생성 (109번 라인)
- ✅ 수정: `prompt=prompt` (원본 그대로 전달)

### Phase 3: 이미지 전처리 검증 (선택사항)

**현재 상황**:
- 공식 infer()가 내부에서 `dynamic_preprocess()` 자동 수행
- crop_mode=True 설정으로 활성화됨

**확인 필요**:
```python
# modeling_deepseekocr.py:773-785
if crop_mode:
    if image.size[0] > 640 or image.size[1] > 640:
        images_crop_raw, crop_ratio = dynamic_preprocess(image)
```

**우리 설정 (config.py):**
```python
crop_mode: bool = True  # ✅ 이미 활성화됨!
base_size: int = 1024   # global view 크기
image_size: int = 640   # local view 크기
```

**결론**:
- ✅ 이미 올바르게 설정됨
- 공식 infer()가 내부에서 전처리 자동 수행
- **추가 작업 불필요**

---

## ✅ 수정 전/후 비교

### Before (현재 - 오류 발생)
```python
# deepseek_engine.py:106-121
def infer(self, image, prompt):
    self._load_model()

    # ❌ 잘못된 포맷팅
    formatted_prompt = f"<｜User｜>: {prompt}\n\n<｜Assistant｜>:"

    try:
        response = self.model.infer(
            tokenizer=self.tokenizer,
            prompt=formatted_prompt,  # ❌ 전각 문자
            image_file=image,
            base_size=self.config.base_size,
            image_size=self.config.image_size,
            crop_mode=self.config.crop_mode,
        )
        return response
    finally:
        if self._device == "cuda":
            torch.cuda.empty_cache()
```

### After (수정 후 - 공식 API 준수)
```python
# deepseek_engine.py:106-119
def infer(self, image, prompt):
    """
    Generic inference using official DeepSeek-OCR API.

    Args:
        image: PIL Image
        prompt: Already formatted prompt from prompts.py
                (e.g., "<image>\n<|grounding|>...")

    Returns:
        Model response string
    """
    self._load_model()

    try:
        # Use official API - prompt is already correctly formatted
        # Official infer() handles:
        # 1. format_messages() - converts to conversation format
        # 2. load_pil_images() - extracts images
        # 3. dynamic_preprocess() - image preprocessing
        # 4. forward() - model inference
        response = self.model.infer(
            tokenizer=self.tokenizer,
            prompt=prompt,  # ✅ Original prompt from prompts.py
            image_file=image,  # PIL Image (official API accepts this)
            base_size=self.config.base_size,
            image_size=self.config.image_size,
            crop_mode=self.config.crop_mode,
        )
        return response
    finally:
        if self._device == "cuda":
            torch.cuda.empty_cache()
```

---

## 🧪 테스트 계획

### Test 1: 프롬프트 포맷 검증
```python
from src.deepseek_ocr.engine.prompts import STRUCTURE_ANALYSIS_PROMPT

# 검증: 프롬프트가 공식 포맷인가?
assert STRUCTURE_ANALYSIS_PROMPT.startswith("<image>")
assert "<|grounding|>" in STRUCTURE_ANALYSIS_PROMPT
assert "<｜User｜>" not in STRUCTURE_ANALYSIS_PROMPT  # 전각 문자 없음
print("✅ Prompt format is correct!")
```

### Test 2: Pass 1 단일 페이지 테스트
```python
from PIL import Image
from src.deepseek_ocr.engine.deepseek_engine import DeepSeekEngine
from src.deepseek_ocr.core.config import load_config

config = load_config(preset="rtx4090")
engine = DeepSeekEngine(config)

# 테스트 이미지
image = Image.open("test_page.png")

# Pass 1: 구조 분석
from src.deepseek_ocr.engine.prompts import STRUCTURE_ANALYSIS_PROMPT
response = engine.infer(image, STRUCTURE_ANALYSIS_PROMPT)

# 응답 확인
print(response)
assert "elements" in response or "bbox" in response
print("✅ Pass 1 inference works!")
```

### Test 3: Pass 2 요소 분석 테스트
```python
from src.deepseek_ocr.engine.prompts import get_element_prompt

# 테이블 요소 테스트
cropped_table = Image.open("cropped_table.png")
table_prompt = get_element_prompt("table", context="노열 관리 기준표")

response = engine.infer(cropped_table, table_prompt)
print(response)
assert "items" in response or "markdown" in response
print("✅ Pass 2 inference works!")
```

### Test 4: 전체 파이프라인 통합 테스트
```python
# RunPod에서 실행
python runpod/process.py --input test_pdfs/ --output outputs/ --preset rtx4090

# 결과 확인
# 1. outputs/test_docjson.json 생성됨
# 2. outputs/cropped_images/ 에 이미지 저장됨
# 3. 에러 없이 완료
print("✅ Full pipeline works!")
```

---

## 📊 위험도 평가

| 수정 항목 | 위험도 | 영향 범위 | 롤백 가능성 |
|----------|--------|----------|------------|
| 프롬프트 포맷 수정 | 🔴 HIGH | 전체 추론 | ✅ 쉬움 |
| infer() 단순화 | 🟡 MEDIUM | Engine만 | ✅ 쉬움 |
| 이미지 전처리 | 🟢 LOW | 없음 (이미 구현됨) | N/A |

---

## 🚀 실행 순서

1. **백업 생성**
   ```bash
   git commit -m "Backup before refactoring"
   cp src/deepseek_ocr/engine/deepseek_engine.py src/deepseek_ocr/engine/deepseek_engine.py.backup
   ```

2. **수정 1: 프롬프트 포맷 제거**
   - 109번 라인 삭제
   - 116번 라인 수정 (`formatted_prompt` → `prompt`)
   - 로컬 테스트

3. **수정 2: 주석 및 문서화**
   - docstring 업데이트
   - 공식 API 사용 명시

4. **커밋 및 푸시**
   ```bash
   git add src/deepseek_ocr/engine/deepseek_engine.py
   git commit -m "Fix prompt formatting to match official DeepSeek-OCR API"
   git push origin master
   ```

5. **RunPod 테스트**
   ```bash
   cd /workspace/SUT_DOCR-ANALYZER
   git pull origin master
   source .venv/bin/activate
   python runpod/process.py --input test_pdfs/ --output outputs/ --preset rtx4090
   ```

6. **검증**
   - Pass 1 결과 확인 (elements, bbox 검출)
   - Pass 2 결과 확인 (항목, 키워드, 요약 추출)
   - DocJSON 생성 확인
   - 이미지 저장 확인

---

## ✅ 성공 기준

### 기능 보존 체크리스트
- [ ] Pass 1: 페이지 구조 분석 (bbox 검출) 작동
- [ ] Pass 2: 요소별 상세 분석 작동
- [ ] 7-Category 분류 정확도 유지
- [ ] DocJSON 생성 (항목, 키워드, 요약)
- [ ] 이미지 추출 및 저장
- [ ] 섹션 트리 구조 생성
- [ ] RTX 4060 8GB 메모리 사용량 < 7.5GB

### 성능 개선 지표
- [ ] 추론 에러 0%
- [ ] 프롬프트 인식률 향상
- [ ] 고해상도 문서 처리 품질 향상 (1280×1280)

---

## 📝 다음 단계 (수정 후)

1. **한국어 성능 검증**
   - 한국어 텍스트 추출 정확도 테스트
   - 섹션 번호 파싱 검증 (1., 1.1., 1.1.1.)

2. **복잡도 처리 개선**
   - complex_image 분류 정확도 향상
   - 복잡한 표/그래프 처리

3. **배치 처리 최적화**
   - 다중 문서 처리 성능
   - 메모리 관리 개선

---

**작성자**: Claude (DeepSeek-OCR Expert)
**검토자**: Human (Project Owner)
**승인**: 리팩토링 실행 전 최종 검토 필요
