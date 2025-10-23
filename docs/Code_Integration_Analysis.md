# DeepSeek-OCR 통합 분석 및 수정 계획

**날짜**: 2025-10-23
**분석자**: Claude

---

## 🔍 현재 상태 분석

### 1. PDF 파싱 (✅ 완료)
**파일**: `src/mypkg/components/parser/pdf_parser.py`

**현재 동작**:
- PDF → 페이지 이미지 변환 (pdf2image)
- 텍스트 레이어 추출 (PyMuPDF)
- ✅ **DeepSeek-OCR과 호환**

**문제점**: 없음

---

### 2. 요소 추출 (⚠️ Placeholder)
**파일**: `src/mypkg/components/extractor/element_extractor.py`

**현재 동작**:
- 전체 페이지를 하나의 요소로 반환 (`_extract_full_page_element`)
- `ElementType.UNKNOWN` 설정
- ✅ **DeepSeek-OCR 직접 OCR 방식과 호환**

**문제점**:
- ❌ **실제로 DeepSeek-OCR이 요소를 추출하지 않음**
- `_extract_layout_based_elements()`는 구현되지 않음 (TODO 상태)
- 주석: "향후 레이아웃 분석 모델 또는 DeepSeek-OCR과 통합 필요"

**수정 필요**:
1. DeepSeek-OCR은 **레이아웃 분석 기능이 없음** → 별도 레이아웃 모델 필요
2. 현재 방식 (전체 페이지 → DeepSeek-OCR OCR) 유지가 적절
3. **문제 없음**: 전체 페이지를 DeepSeek-OCR에 전달하여 OCR 수행

---

### 3. 분류기 (❌ 구현 불완전)
**파일**: `src/mypkg/components/classifier/deepseek_classifier.py`

**현재 동작**:
- `_classify_with_deepseek()` → Placeholder (TODO)
- 휴리스틱 기반 임시 분류 (aspect ratio)
- ❌ **실제 DeepSeek-OCR 호출 없음**

**문제점**:
```python
# Line 200: TODO: 실제 DeepSeek-OCR API 호출 구현
# 현재는 placeholder로 기본값 반환
logger.warning("DeepSeek-OCR classification not fully implemented yet")
```

**수정 필요**:
1. `VLMAnalyzer.classify_element()` 메서드 활용
2. DeepSeek-OCR의 실제 추론 수행
3. JSON 파싱 및 결과 반환

---

### 4. 분석기 (❌ 구현 불완전)
**파일들**:
- `src/mypkg/components/analyzer/table_analyzer.py`
- `src/mypkg/components/analyzer/graph_analyzer.py`
- `src/mypkg/components/analyzer/diagram_analyzer.py`

**현재 동작**:
- 모든 분석기: Placeholder 반환
- ❌ **실제 DeepSeek-OCR 호출 없음**

**문제점**:
```python
# Line 86-93: TODO: DeepSeek-OCR API 호출
# 현재는 placeholder 반환
```

**수정 필요**:
1. `VLMAnalyzer.analyze_element()` 메서드 활용
2. [항목], [키워드], [자연어 요약] 추출
3. 타입별 맞춤 프롬프트 적용

---

### 5. VLM Analyzer (✅ 구현 완료, ⚠️ 통합 필요)
**파일**: `src/mypkg/components/vlm_analyzer.py`

**현재 동작**:
- ✅ GPU/CPU 자동 선택
- ✅ 분류: `classify_element()`
- ✅ 분석: `analyze_element()`
- ✅ 배치 처리: `batch_analyze()`

**문제점**:
- ❌ **다른 컴포넌트와 통합되지 않음**
- `DeepSeekClassifier`와 `*Analyzer`가 VLMAnalyzer를 사용하지 않음

---

## 🔧 통합 계획

### Phase 1: 분류기 통합 ✅
**목표**: `DeepSeekClassifier`가 `VLMAnalyzer`를 사용하도록 수정

**수정 파일**: `src/mypkg/components/classifier/deepseek_classifier.py`

**변경 사항**:
```python
from ..vlm_analyzer import VLMAnalyzer

class DeepSeekClassifier:
    def __init__(self, ...):
        self.vlm_analyzer = VLMAnalyzer(
            device=self.device,
            dtype="bfloat16" if self.device == "cuda" else "float32"
        )

    def _classify_with_deepseek(self, image: Image.Image):
        # VLMAnalyzer 사용
        result = self.vlm_analyzer.classify_element(
            image=image,
            page_number=0  # 단일 요소 분류시
        )

        # ElementType으로 변환
        element_type = self._map_to_element_type(result['type'])

        return ClassificationResult(
            element_type=element_type,
            confidence=result['confidence'],
            reasoning=f"Classified by DeepSeek-OCR"
        )
```

---

### Phase 2: 분석기 통합 ✅
**목표**: 모든 `*Analyzer`가 `VLMAnalyzer`를 사용하도록 수정

**수정 파일들**:
- `table_analyzer.py`
- `graph_analyzer.py`
- `diagram_analyzer.py`

**변경 사항**:
```python
from ..vlm_analyzer import VLMAnalyzer

class TableAnalyzer(BaseAnalyzer):
    def __init__(self, ...):
        self.vlm_analyzer = VLMAnalyzer(
            device="cuda" if torch.cuda.is_available() else "cpu"
        )

    def analyze(self, image, text_context=""):
        # VLMAnalyzer 사용
        vlm_result = self.vlm_analyzer.analyze_element(
            image=image,
            element_type="table",
            page_number=0
        )

        # AnalysisResult로 변환
        return AnalysisResult(
            category="table",
            items=vlm_result['항목'],
            keywords=vlm_result['키워드'],
            summary=vlm_result['자연어_요약'],
            confidence=1.0,
            metadata={"raw_output": vlm_result.get('raw_output', '')}
        )
```

---

### Phase 3: 파이프라인 구축 ✅
**목표**: 전체 실행 파이프라인 생성

**새 파일**: `src/mypkg/pipelines/deepseek_pdf_pipeline.py`

**파이프라인 단계**:
```python
class DeepSeekPDFPipeline:
    def __init__(self):
        self.pdf_parser = PDFParser(dpi=200)
        self.element_extractor = ElementExtractor()
        self.vlm_analyzer = VLMAnalyzer(device="auto")
        self.text_enricher = TextEnricher()

    def process(self, pdf_path: Path, output_dir: Path):
        # 1. PDF 파싱
        pages = self.pdf_parser.parse(pdf_path)

        # 2. 요소 추출 (전체 페이지)
        all_elements = []
        for page in pages:
            elements = self.element_extractor.extract(
                page.image, page.page_number, page.text_layer
            )
            all_elements.extend(elements)

        # 3. VLM 분석 (분류 + 분석)
        results = self.vlm_analyzer.batch_analyze(
            [{"image": elem.image, "type": "unknown", "page": elem.page_number}
             for elem in all_elements]
        )

        # 4. DocJSON 생성
        doc_json = self.text_enricher.enrich(all_elements, results)

        # 5. 결과 저장
        self._save_results(doc_json, output_dir)
```

---

### Phase 4: RunPod 출력 저장 ✅
**목표**: RunPod에서 결과를 올바르게 저장

**고려사항**:
1. ✅ 절대 경로 사용: `/workspace/sut-preprocess/outputs/`
2. ✅ 권한 확인: `mkdir -p` 사용
3. ✅ 결과 형식:
   - DocJSON (JSON)
   - Markdown 요약 (MD)
   - 이미지 (PNG)
   - 로그 (TXT)

**RunPod 출력 구조**:
```
/workspace/sut-preprocess/
├── outputs/
│   ├── TP-030-030-030/
│   │   ├── docjson.json         # DocJSON 형식
│   │   ├── summary.md            # 마크다운 요약
│   │   ├── pages/                # 페이지별 이미지
│   │   │   ├── page_001.png
│   │   │   ├── page_002.png
│   │   │   └── ...
│   │   ├── elements/             # 추출된 요소 이미지
│   │   │   ├── page_1_table_1.png
│   │   │   ├── page_2_graph_1.png
│   │   │   └── ...
│   │   └── logs/
│   │       ├── processing.log
│   │       └── performance.json
```

---

## ✅ 실행 순서 검증

### [문서5] 원래 계획과 비교

**원래 계획**:
1. PDF 파싱 → 이미지 변환
2. 요소 추출 → 레이아웃 분석
3. 분류 → DeepSeek-OCR
4. 분석 → DeepSeek-OCR (항목, 키워드, 요약)
5. 텍스트 통합 → DocJSON

**현재 구현 상태**:
1. ✅ PDF 파싱 - 구현 완료
2. ⚠️ 요소 추출 - Placeholder (전체 페이지)
3. ❌ 분류 - TODO 상태
4. ❌ 분석 - TODO 상태
5. ⏳ 텍스트 통합 - 구현 필요

**수정 후 실행 순서**:
1. ✅ PDF 파싱 → PDFParser
2. ✅ 전체 페이지 추출 → ElementExtractor (전체 페이지를 하나의 요소로)
3. ✅ DeepSeek-OCR 직접 처리 → VLMAnalyzer.batch_analyze()
   - 분류 자동 수행
   - 분석 자동 수행 (항목, 키워드, 요약)
4. ✅ DocJSON 생성 → TextEnricher
5. ✅ 결과 저장 → Pipeline._save_results()

---

## 🚨 주요 발견 사항

### 1. DeepSeek-OCR은 레이아웃 분석을 하지 않음
- **결론**: 전체 페이지를 DeepSeek-OCR에 전달하여 OCR 수행
- 레이아웃 분석 필요시 별도 모델 (LayoutLMv3) 추가 필요
- 현재 구조 (전체 페이지 → DeepSeek-OCR)가 적절함

### 2. 분류기와 분석기가 VLMAnalyzer를 사용하지 않음
- **문제**: 각 컴포넌트가 독립적으로 구현되어 중복 코드
- **해결**: VLMAnalyzer를 공통 인터페이스로 사용

### 3. RunPod 출력 저장 경로 확인 필요
- `/workspace/` 디렉토리 사용 (RunPod 표준)
- 절대 경로 사용하여 경로 혼동 방지

---

## 📋 수정 체크리스트

### 즉시 수정 필요
- [ ] `DeepSeekClassifier._classify_with_deepseek()` - VLMAnalyzer 통합
- [ ] `TableAnalyzer.analyze()` - VLMAnalyzer 통합
- [ ] `GraphAnalyzer.analyze()` - VLMAnalyzer 통합
- [ ] `DiagramAnalyzer.analyze()` - VLMAnalyzer 통합
- [ ] `DeepSeekPDFPipeline` 생성 - 전체 파이프라인
- [ ] RunPod 테스트 스크립트에 출력 저장 로직 추가

### 선택적 개선
- [ ] LayoutLMv3 통합 (요소별 bounding box 검출)
- [ ] 배치 처리 최적화
- [ ] 캐싱 메커니즘
- [ ] 오류 복구 로직

---

## 🎯 다음 단계

1. ✅ 분류기 통합 (DeepSeekClassifier)
2. ✅ 분석기 통합 (Table/Graph/DiagramAnalyzer)
3. ✅ 파이프라인 구축 (DeepSeekPDFPipeline)
4. ✅ RunPod 테스트 스크립트 업데이트
5. ⏳ RunPod에서 전체 파이프라인 테스트

---

**결론**:
현재 코드는 **구조는 올바르지만 실제 DeepSeek-OCR 호출이 구현되지 않은 상태**입니다.
`VLMAnalyzer`는 완성되었으나, 다른 컴포넌트들이 이를 활용하지 않고 있습니다.
위의 통합 작업을 통해 전체 파이프라인이 정상 작동하도록 수정이 필요합니다.
