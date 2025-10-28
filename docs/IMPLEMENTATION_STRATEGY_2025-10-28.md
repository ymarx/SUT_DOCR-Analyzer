# DeepSeek-OCR 구현 전략 문서
**작성일**: 2025-10-28
**목적**: 공식 API 호환 + 프로젝트 목표 달성을 위한 2-Pass Hybrid 방식 구현

---

## 🎯 프로젝트 핵심 목표

### 1. 의미 검색 (Vector Search) 최적화
**목적**: 벡터 DB에서 "의미 검색"을 했을 때, 도표/그래프의 자연어 요약을 참조하고 원본 요소를 불러올 수 있도록 함

**요구사항**:
- ✅ 그래프/도표의 **자연어 요약** 생성
- ✅ **키워드 추출** (벡터 임베딩용)
- ✅ 원본 이미지 **참조 링크** 유지
- ✅ 주변 맥락 정보 포함

**예시**:
```json
{
  "element_id": "page_3_graph_2",
  "element_type": "graph",
  "항목": ["원전 가동률 추이", "line_chart", "2024년 1분기"],
  "키워드": ["원전", "가동률", "1분기", "2024", "추이", "성능", "안정적"],
  "자연어요약": "2024년 1분기 원전 가동률 추이 그래프. 1호기 98.5%, 2호기 97.2% 기록하며 전반적으로 안정적인 운전 성능 유지.",
  "image_path": "outputs/images/page_3_graph_2.png",
  "bbox": [550, 350, 900, 700]
}
```

### 2. 7개 요소의 내재적 내용 + 주변 정보 활용
**목적**: 각 요소(table, graph, diagram 등)의 자체 내용뿐 아니라 **주변 텍스트**도 활용하여 의미 있는 키워드/요약 생성

**7-Category Classification**:
1. `text_header`: 문서 제목, 큰 제목
2. `text_section`: 넘버링된 섹션 제목 (1., 1.1., 1.1.1.)
3. `text_paragraph`: 일반 단락 텍스트
4. `table`: 표
5. `graph`: 그래프, 차트
6. `diagram`: 순서도, 공정도
7. `complex_image`: 복잡한 이미지, 사진

**주변 정보 활용 방식**:
```python
# Example: 그래프 분석 시
context = extract_surrounding_text(
    target_element=graph_element,
    all_elements=page_elements,
    radius=0.2  # 페이지 높이의 20% 범위 내
)

prompt = f"""<image>
<|grounding|>Analyze this graph.

Context from surrounding text:
{context}  # ← 주변 단락 텍스트 포함

Extract:
1. [항목] Graph title, type, axes, legend, trends
2. [키워드] 5-10 keywords (including from context)
3. [자연어 요약] 2-3 sentence summary
"""
```

### 3. 공식 문서 방식 준수
**제약**: JSON 직접 출력, 복잡한 프롬프트는 잘 작동하지 않을 수 있음

**해결책**:
- ✅ **Pass 1**: 공식 `<|grounding|>` markdown 사용
- ✅ **Pass 2**: Element-specific 프롬프트 (간결하게)
- ❌ JSON schema 강요하지 않음
- ❌ 과도하게 복잡한 지시사항 지양

---

## 🏗️ 아키텍처 설계

### 전체 구조
```
┌─────────────────────────────────────────────────────────┐
│                    PDF Document                          │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │   PDFParser            │
         │   - pdf2image          │
         │   - DPI: 200           │
         └────────┬───────────────┘
                  │
                  ▼
         ┌────────────────────────┐
         │  Pass 1: Structure     │
         │  Detection             │
         │  ┌──────────────────┐  │
         │  │ Official Prompt  │  │
         │  │ <|grounding|>    │  │
         │  │ Markdown output  │  │
         │  └──────────────────┘  │
         │  ┌──────────────────┐  │
         │  │ MarkdownParser   │  │
         │  │ Parse refs/dets  │  │
         │  │ Extract elements │  │
         │  └──────────────────┘  │
         └────────┬───────────────┘
                  │
                  ▼ List[ElementDetection]
         ┌────────────────────────┐
         │  Pass 2: Element       │
         │  Analysis              │
         │  ┌──────────────────┐  │
         │  │ For each element │  │
         │  │ - Crop image     │  │
         │  │ - Extract context│  │
         │  │ - Detailed prompt│  │
         │  │ - Parse response │  │
         │  └──────────────────┘  │
         └────────┬───────────────┘
                  │
                  ▼ List[ElementAnalysis]
         ┌────────────────────────┐
         │  DocJSON Generation    │
         │  - Combine structure   │
         │  │  + analysis          │
         │  - Save images         │
         │  - Build DocJSON       │
         └────────┬───────────────┘
                  │
                  ▼
         ┌────────────────────────┐
         │  Output:               │
         │  - docjson.json        │
         │  - images/*.png        │
         └────────────────────────┘
```

### 2-Pass 파이프라인 상세

#### **Pass 1: Page Structure Detection**
```python
# Input
page_image: PIL.Image

# Prompt (공식 방식)
prompt = "<image>\n<|grounding|>Convert the document to markdown."

# Output (example)
"""
<|ref|>title<|/ref|><|det|>[100,50,900,120]<|/det|>
# 노열관리 기준

<|ref|>text_paragraph<|/ref|><|det|>[100,150,900,300]<|/det|>
본 기준은 노저 냉입사고 시 복구 절차를 정의한다.

<|ref|>table<|/ref|><|det|>[100,350,500,700]<|/det|>
| 항목 | 내용 |
|------|------|
| ... | ... |

<|ref|>figure<|/ref|><|det|>[550,350,900,700]<|/det|>
[Graph showing performance trends...]
"""

# Parsing
elements = MarkdownGroundingParser().parse(markdown_output)
# → List[ElementDetection]
#   - element_id: "e1", "e2", ...
#   - element_type: TEXT_HEADER, TEXT_PARAGRAPH, TABLE, GRAPH, ...
#   - bbox: BoundingBox(x1, y1, x2, y2)
#   - text_preview: "first 50 chars..."
```

#### **Pass 2: Element-Specific Analysis**
```python
# For each element detected in Pass 1
for element in elements:
    # 1. Crop element from page
    cropped_image = crop_element(page_image, element.bbox)

    # 2. Extract surrounding context
    context = extract_surrounding_context(
        element=element,
        all_elements=elements,
        markdown_text=pass1_markdown_output
    )

    # 3. Generate element-specific prompt
    prompt = get_element_prompt(element.element_type, context)

    # Example for GRAPH:
    """
    <image>
    <|grounding|>Analyze this graph element in detail.

    Context from surrounding text:
    본 기준은 노저 냉입사고 시 복구 절차를 정의한다.

    Extract the following:
    1. [항목] Graph components (title, type, axes, legend, trends)
    2. [키워드] 5-10 important keywords
    3. [자연어 요약] 2-3 sentence summary
    """

    # 4. Analyze
    response = engine.infer(cropped_image, prompt)

    # 5. Parse response (flexible)
    analysis = parse_element_response(response, element.element_type)
    # → ElementAnalysis
    #   - 항목: List[str]
    #   - 키워드: List[str]
    #   - 자연어요약: str
```

---

## 📁 파일 구조 및 역할

```
src/deepseek_ocr/
├── core/
│   ├── config.py          # Config 설정
│   ├── types.py           # Data classes (ElementDetection, ElementAnalysis, etc.)
│   └── utils.py           # 유틸리티 함수
│
├── engine/
│   ├── deepseek_engine.py      # ✅ 수정: output_path 추가
│   └── prompts.py              # ✅ 수정: 공식 프롬프트 사용
│
├── pipeline/
│   ├── pdf_parser.py           # PDF → Images
│   ├── markdown_parser.py      # 🆕 신규: Markdown grounding → Elements
│   ├── structure_analyzer.py   # ✅ 수정: Pass 1 with markdown parser
│   ├── element_analyzer.py     # ✅ 수정: Pass 2 with context extraction
│   └── text_enricher.py        # DocJSON 생성
│
└── cli/
    └── main.py            # CLI entrypoint
```

---

## 🔧 구현 단계

### Phase 1: Core Infrastructure (output_path fix)
**파일**: `deepseek_engine.py`

**변경사항**:
```python
response = self.model.infer(
    tokenizer=self.tokenizer,
    prompt=prompt,
    image_file=temp_path,
    output_path=temp_output_dir,  # ✅ REQUIRED
    base_size=self.config.base_size,
    image_size=self.config.image_size,
    crop_mode=self.config.crop_mode,
    save_results=False,
    test_compress=False,
)
```

**이유**:
- `modeling_deepseekocr.py:706` calls `os.makedirs(output_path, exist_ok=True)`
- Empty string causes `[Errno 2] No such file or directory: ''`

---

### Phase 2: Official Prompt Integration
**파일**: `prompts.py`

**변경사항**:
```python
# Pass 1: Official grounding prompt
STRUCTURE_ANALYSIS_PROMPT = "<image>\n<|grounding|>Convert the document to markdown."

# Pass 2: Element-specific prompts (기존 유지, 단순화)
GRAPH_ANALYSIS_PROMPT = """<image>
<|grounding|>Analyze this graph element in detail.

Context from surrounding text:
{context}

Extract the following:
1. [항목] Graph components: title, type, axes, legend, trends
2. [키워드] 5-10 important keywords
3. [자연어 요약] 2-3 sentence summary describing what the graph shows
"""
```

**변경 포인트**:
- ❌ JSON schema 제거
- ❌ 복잡한 output format 지시 제거
- ✅ 간결하고 명확한 지시
- ✅ `<|grounding|>` 토큰 활용

---

### Phase 3: Markdown Parser (NEW)
**파일**: `markdown_parser.py` (신규)

**기능**:
1. Parse `<|ref|>...<|/ref|><|det|>...<|/det|>` patterns
2. Extract bounding boxes (normalized 0-999 → 0-1)
3. Map official labels to 7-category types
4. Extract markdown content between refs

**클래스**:
```python
class MarkdownGroundingParser:
    def parse(self, markdown_text: str) -> List[ElementDetection]:
        """Parse grounding markdown into structured elements."""

    def _map_label(self, label: str) -> ElementType:
        """Map official label to 7-category."""

    def _extract_content(self, text: str, idx: int) -> str:
        """Extract markdown content for element."""
```

---

### Phase 4: Structure Analyzer Update
**파일**: `structure_analyzer.py`

**변경사항**:
```python
from .markdown_parser import MarkdownGroundingParser

class PageStructureAnalyzer:
    def __init__(self, engine: DeepSeekEngine):
        self.engine = engine
        self.parser = MarkdownGroundingParser()  # ✅ 추가

    def analyze(self, page_image: Image.Image, page_num: int) -> PageStructure:
        # Use official prompt
        prompt = "<image>\n<|grounding|>Convert the document to markdown."

        # Get markdown with grounding
        markdown_output = self.engine.infer(page_image, prompt)

        # Parse into elements
        elements = self.parser.parse(markdown_output)

        return PageStructure(
            page_number=page_num,
            elements=elements,
            raw_markdown=markdown_output,  # ✅ 원본 저장
        )
```

---

### Phase 5: Element Analyzer Update
**파일**: `element_analyzer.py`

**변경사항**:
```python
def analyze(
    self,
    element: ElementDetection,
    page_image: Image.Image,
    all_elements: List[ElementDetection],
    markdown_text: str  # ✅ Pass 1 markdown
) -> ElementAnalysis:
    # 1. Crop element
    cropped_image = crop_element(page_image, element.bbox)

    # 2. Extract context
    context = self._extract_context(
        element, all_elements, markdown_text  # ✅ 주변 정보 활용
    )

    # 3. Element-specific prompt
    prompt = get_element_prompt(element.element_type, context)

    # 4. Analyze
    response = self.engine.infer(cropped_image, prompt)

    # 5. Parse (flexible, no strict JSON)
    analysis = self._parse_response(response)

    return ElementAnalysis(
        element_id=element.element_id,
        항목=analysis.get("items", []),
        키워드=analysis.get("keywords", []),
        자연어요약=analysis.get("summary", ""),
    )

def _extract_context(self, element, all_elements, markdown_text) -> str:
    """Extract surrounding text context from nearby elements."""
    # Find spatially nearby elements
    # Extract their markdown content
    # Prioritize text_paragraph, text_section
    # Return concatenated context (max 500 chars)
```

---

## ✅ 성공 기준

### 1. 기능 검증
- ✅ PDF 파싱 성공 (19 페이지 인식)
- ✅ Pass 1: Element detection with bbox
- ✅ Pass 2: Detailed analysis with context
- ✅ DocJSON 생성 완료

### 2. 품질 검증
- ✅ 그래프/도표에 대한 자연어 요약 생성
- ✅ 키워드 5-10개 추출
- ✅ 주변 맥락 정보 포함
- ✅ 7-category 분류 정확도

### 3. 성능 검증
- ✅ RTX 4090: 1 PDF (19 페이지) < 5분
- ✅ 메모리 안정성 (no OOM)
- ✅ 출력 파일 구조 완성

---

## 📝 다음 단계

1. ✅ `deepseek_engine.py` 수정 (output_path)
2. ✅ `prompts.py` 수정 (공식 프롬프트)
3. 🆕 `markdown_parser.py` 구현
4. ✅ `structure_analyzer.py` 수정
5. ✅ `element_analyzer.py` 수정
6. ✅ 통합 테스트
7. ✅ RunPod 배포 및 검증

---

## 📚 참고 문서

- [DeepSeek-OCR 논문](../models/DeepSeek-OCR/DeepSeek_OCR_paper.pdf)
- [공식 GitHub](https://github.com/deepseek-ai/DeepSeek-OCR)
- [프로젝트 전체 설계](./3_전체_설계_및_전략.md)
- [공식 예제 코드](../models/DeepSeek-OCR/DeepSeek-OCR-master/DeepSeek-OCR-hf/run_dpsk_ocr.py)
