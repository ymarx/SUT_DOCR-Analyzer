# Layout Assembler (레이아웃 어셈블러)

## 개요 (Overview)
이 모듈은 문서의 다양한 콘텐츠 블록(문단, 리스트, 테이블, 다이어그램)을 섹션(Section) 구조에 할당하고, DocJson 형식에 맞는 콘텐츠 블록을 생성하는 역할을 합니다. 주로 분석된 개별 구성 요소들을 통합하여 문서의 논리적인 레이아웃을 재구성하는 데 사용됩니다.

## 주요 함수/클래스 (Key Functions/Classes)

### `assign_blocks_to_sections(sections: List[Section], blocks: List[ContentBlock]) -> None`
- **목적**: 주어진 `ContentBlock` 리스트를 `Section` 구조에 따라 적절한 섹션에 할당합니다.
- **로직**:
    - 재귀적으로 섹션 트리를 탐색하며, 각 섹션의 `span` (문서 인덱스 범위) 내에 포함되는 블록들을 찾습니다.
    - 자식 섹션에 할당된 블록들은 부모 섹션의 할당 후보에서 제외됩니다.
    - 최종적으로 각 섹션에 할당된 블록들은 `doc_index`를 기준으로 정렬됩니다.
- **`sections`**: 문서의 섹션 구조를 나타내는 `Section` 객체 리스트.
- **`blocks`**: 할당될 `ContentBlock` 객체 리스트.

### `build_paragraph_blocks(paragraphs: List[Dict[str, Any]], skip_docidx: set, heading_idx: set) -> List[ContentBlock]`
- **목적**: 원본 문단 데이터에서 `ContentBlock` 형태의 문단 블록을 생성합니다.
- **로직**:
    - `doc_index`를 기준으로 문단을 정렬합니다.
    - `skip_docidx` (건너뛸 문서 인덱스) 또는 `heading_idx` (헤딩으로 분류된 문서 인덱스)에 포함된 문단은 제외합니다.
    - 텍스트가 비어있는 문단도 제외합니다.
    - 각 문단을 `ContentBlock` 객체로 변환하고 `id`, `type`, `doc_index`, `text` 등의 필드를 채웁니다.
- **`paragraphs`**: 원본 문단 데이터 딕셔너리 리스트.
- **`skip_docidx`**: 리스트 또는 테이블 등으로 이미 처리되어 건너뛸 `doc_index` 집합.
- **`heading_idx`**: 헤딩으로 분류된 문단의 `doc_index` 집합.

### `build_diagram_blocks(diagrams: List[Dict[str, Any]] | None) -> List[ContentBlock]`
- **목적**: 분석된 다이어그램 데이터에서 `ContentBlock` 형태의 다이어그램 블록을 생성합니다.
- **로직**:
    - 주어진 `diagrams` 리스트의 각 다이어그램을 `ContentBlock` 객체로 변환합니다.
    - `id`, `type` ("diagram"), `doc_index`, `diagram` (원본 다이어그램 데이터) 등의 필드를 채웁니다.
- **`diagrams`**: 분석된 다이어그램 데이터 딕셔너리 리스트.

## 사용된 주요 필드 (Key Fields Used)

- **`sections`**: 문서의 계층적 섹션 구조를 나타내는 `Section` 객체 리스트.
    - **`span`**: 섹션이 커버하는 문서 인덱스 범위 `(start_doc_index, end_doc_index)`.
    - **`subsections`**: 자식 섹션 리스트.
    - **`blocks`**: 해당 섹션에 할당된 `ContentBlock` 리스트.
    - **`block_ids`**: 해당 섹션에 할당된 블록들의 ID 리스트.
- **`blocks`**: `assign_blocks_to_sections` 함수에 입력되는 모든 `ContentBlock` 리스트.
- **`ContentBlock`**: 문서의 단일 콘텐츠 블록을 나타내는 객체.
    - **`id`**: 블록의 고유 식별자 (예: "p1", "list_0", "table_0", "diagram_0").
    - **`type`**: 블록의 유형 (예: "paragraph", "list", "table", "diagram").
    - **`doc_index`**: 블록이 시작되는 문서 인덱스.
    - **`text`**: 블록의 텍스트 내용 (문단 블록의 경우).
    - **`level`**: 블록의 계층적 레벨 (리스트 블록의 경우).
    - **`page`**: 블록이 위치한 페이지 번호.
    - **`bbox`**: 블록의 바운딩 박스 정보.
    - **`semantic`**: 블록의 의미론적 정보.
    - **`table`**: 테이블 블록의 경우, 테이블 데이터.
    - **`list_data`**: 리스트 블록의 경우, 리스트 데이터.
    - **`diagram`**: 다이어그램 블록의 경우, 다이어그램 데이터.
- **`paragraphs`**: `build_paragraph_blocks` 함수에 입력되는 원본 문단 데이터 딕셔너리 리스트.
- **`skip_docidx`**: `build_paragraph_blocks`에서 건너뛸 `doc_index` 집합.
- **`heading_idx`**: `build_paragraph_blocks`에서 헤딩으로 분류된 `doc_index` 집합.
- **`diagrams`**: `build_diagram_blocks` 함수에 입력되는 분석된 다이어그램 데이터 딕셔너리 리스트.
