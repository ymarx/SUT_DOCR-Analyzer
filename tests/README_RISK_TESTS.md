# vLLM Migration Risk Validation Tests

vLLM nightly 마이그레이션 **전에** 반드시 실행해야 할 리스크 검증 테스트입니다.

## 🎯 목적

공식 DeepSeek-OCR vLLM이 우리의 2-Pass Pipeline과 호환되는지 검증:

1. **Label 호환성**: 공식 vLLM이 어떤 label을 사용하는지 확인
2. **Figure 분류**: `figure` label이 graph/diagram/image 중 무엇인지 판별
3. **Context 품질**: Pass 2에 필요한 문맥이 충분한지 확인

---

## 📋 테스트 목록

### Test 1: Label Detection (`test_label_detection.py`)

**검증 대상**:
- 공식 vLLM이 사용하는 모든 label 수집
- 우리 `LABEL_MAPPING`에 없는 unknown label 발견

**리스크**:
- 🔴 **높음**: Unknown label 발견 시 매핑 불가 → `COMPLEX_IMAGE`로 잘못 분류

**기대 결과**:
```
✅ All labels are already mapped
```

**문제 발견 시**:
```
⚠️ UNKNOWN Labels:
  • caption: 5 occurrences ← NEEDS MAPPING!
```

---

### Test 2: Figure Classification (`test_figure_classification.py`)

**검증 대상**:
- `figure` label이 실제로 graph, diagram, complex_image 중 무엇인지 판별
- 각 프롬프트(GRAPH/DIAGRAM/COMPLEX_IMAGE)로 테스트하여 최적 분류 결정

**리스크**:
- 🟡 **중간**: 잘못된 분류 → Pass 2에서 부적절한 프롬프트 사용 → 품질 저하

**기대 결과**:
```
🎯 Recommended classification: GRAPH
⭐ For label 'figure', use: ElementType.GRAPH
```

**문제 발견 시**:
- `LABEL_MAPPING` 업데이트 필요
- 또는 범용 `FIGURE` 프롬프트 생성 고려

---

### Test 3: Text Preview Quality (`test_text_preview.py`)

**검증 대상**:
- Pass 1의 `text_preview` 추출 품질
- Pass 2 문맥 생성 품질 (주변 요소 기반)

**리스크**:
- 🟡 **중간**: text_preview 부족 → Pass 2 문맥 부족 → 분석 품질 저하

**기대 결과**:
```
✅ Text preview coverage: GOOD (≥70%)
✅ Average preview length: GOOD (≥30 chars)
✅ Average context length: GOOD (≥100 chars)
```

**문제 발견 시**:
```
⚠️ Average preview length: LOW (<15 chars)
💡 Recommendations:
  • Consider increasing text_preview length (currently ~50 chars max)
```

---

## 🚀 사용 방법

### 방법 1: 통합 테스트 (권장)

```bash
# 이미지로 테스트
./tests/run_risk_tests.sh rtx4090 path/to/sample.jpg

# PDF로 테스트
./tests/run_risk_tests.sh rtx4090 "" path/to/document.pdf 1
```

### 방법 2: 개별 테스트

#### Test 1: Label Detection
```bash
# 이미지
python tests/test_label_detection.py --image sample.jpg --preset rtx4090

# PDF
python tests/test_label_detection.py --pdf document.pdf --page 1 --preset rtx4090
```

#### Test 2: Figure Classification
```bash
# 이미지의 첫 번째 figure 요소 테스트
python tests/test_figure_classification.py --image chart.jpg --element 0 --preset rtx4090

# 다른 figure 요소 테스트
python tests/test_figure_classification.py --image diagram.jpg --element 1 --preset rtx4090
```

#### Test 3: Text Preview Quality
```bash
# 이미지
python tests/test_text_preview.py --image sample.jpg --preset rtx4090

# PDF
python tests/test_text_preview.py --pdf document.pdf --page 1 --preset rtx4090
```

---

## 📊 결과 해석

### ✅ 모든 테스트 통과

```
✅ All labels are known (no mapping updates needed)
✅ Text preview coverage: GOOD (≥70%)
✅ Average context length: GOOD (≥100 chars)
```

**➡️ 안전하게 vLLM nightly 마이그레이션 진행 가능**

---

### ⚠️ Unknown Label 발견

**Test 1 출력**:
```
⚠️ UNKNOWN Labels:
  • caption: 5 ← NEEDS MAPPING!
  • equation: 2 ← NEEDS MAPPING!
```

**대응**:
1. `src/deepseek_ocr/pipeline/markdown_parser.py` 열기
2. `LABEL_MAPPING` 딕셔너리에 추가:
   ```python
   LABEL_MAPPING = {
       # ... 기존 매핑
       "caption": ElementType.TEXT_PARAGRAPH,  # 또는 적절한 타입
       "equation": ElementType.COMPLEX_IMAGE,  # 수식은 이미지로 처리
   }
   ```
3. 다시 테스트 실행하여 확인

---

### ⚠️ Figure 분류 애매함

**Test 2 출력**:
```
🎯 Recommended classification: DIAGRAM
⭐ For label 'figure', use: ElementType.DIAGRAM
```

**대응 옵션**:

**Option A**: `LABEL_MAPPING` 업데이트 (간단)
```python
"figure": ElementType.DIAGRAM,  # 테스트 결과에 따름
```

**Option B**: Figure별로 다르게 분류 (정확)
- Pass 2에서 3가지 프롬프트 모두 시도
- 가장 성공적인 프롬프트 선택
- 구현 복잡도 높음

**Option C**: 범용 FIGURE 프롬프트 생성 (절충)
```python
FIGURE_PROMPT = """<image>
Analyze this figure (could be graph, diagram, or other visual).
...
"""
```

---

### ⚠️ Text Preview 품질 부족

**Test 3 출력**:
```
⚠️ Average preview length: MODERATE (15-30 chars)
❌ Average context length: LOW (<50 chars)
```

**대응**:
1. `src/deepseek_ocr/pipeline/markdown_parser.py` 열기
2. `_extract_text_preview()` 메서드 수정:
   ```python
   # 현재: 50자
   text_preview = content[:50]

   # 수정: 200자
   text_preview = content[:200]
   ```
3. `src/deepseek_ocr/pipeline/element_analyzer_vllm.py` 열기
4. `_build_context()` 메서드 수정:
   ```python
   # 현재: max_chars = 500
   max_chars = 500

   # 수정: max_chars = 1000
   max_chars = 1000
   ```

---

## 🔧 RunPod에서 실행

### 1. 환경 준비

```bash
cd /workspace/SUT_DOCR-ANALYZER
source .venv/bin/activate
```

### 2. 테스트 이미지/PDF 준비

```bash
# 샘플 PDF 확인
ls pdfs/

# 또는 wget으로 다운로드
wget https://example.com/sample.pdf -O test.pdf
```

### 3. 테스트 실행

```bash
# 통합 테스트
./tests/run_risk_tests.sh rtx4090 "" pdfs/sample.pdf 1

# 또는 개별 테스트
python tests/test_label_detection.py --pdf pdfs/sample.pdf --page 1 --preset rtx4090
```

---

## 📋 다음 단계

### ✅ 모든 테스트 통과 시

1. 테스트 결과 저장:
   ```bash
   ./tests/run_risk_tests.sh rtx4090 "" pdfs/sample.pdf 1 > test_results.txt 2>&1
   ```

2. vLLM nightly 마이그레이션 진행:
   - requirements.txt 업데이트
   - setup.sh 수정
   - vllm_model/deepseek_ocr_model.py 교체
   - deepseek_vllm_engine.py 수정

3. 마이그레이션 후 재테스트:
   ```bash
   ./tests/run_risk_tests.sh rtx4090 "" pdfs/sample.pdf 1
   ```

### ⚠️ 문제 발견 시

1. 위 "대응" 섹션 참조하여 수정
2. 재테스트
3. 모든 테스트 통과할 때까지 반복
4. 마이그레이션 진행

---

## 💡 팁

### 다양한 문서로 테스트

```bash
# 테이블이 많은 문서
./tests/run_risk_tests.sh rtx4090 "" tables_heavy.pdf 1

# 그래프가 많은 문서
./tests/run_risk_tests.sh rtx4090 "" graphs_heavy.pdf 1

# 복잡한 다이어그램
./tests/run_risk_tests.sh rtx4090 "" diagrams.pdf 1
```

### 여러 페이지 테스트

```bash
# 1페이지
python tests/test_label_detection.py --pdf doc.pdf --page 1 --preset rtx4090

# 5페이지
python tests/test_label_detection.py --pdf doc.pdf --page 5 --preset rtx4090

# 10페이지
python tests/test_label_detection.py --pdf doc.pdf --page 10 --preset rtx4090
```

---

## 🐛 문제 해결

### "No module named 'deepseek_ocr'"

```bash
# 프로젝트 루트에서 실행하세요
cd /path/to/SUT_DOCR-Analyzer
python tests/test_label_detection.py ...
```

### "CUDA out of memory"

```bash
# RTX 4060으로 변경
./tests/run_risk_tests.sh rtx4060 ...
```

### "vLLM model loading failed"

```bash
# vLLM 설치 확인
pip show vllm

# 재설치
pip install -r requirements.txt
```

---

## 📞 문의

테스트 결과에 대한 질문이나 문제가 있으면 이슈를 등록해주세요.
