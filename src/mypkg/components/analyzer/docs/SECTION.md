# Section Analyzer (섹션 분석기)

## 개요 (Overview)
이 분석기는 문서의 문단(paragraphs) 데이터를 기반으로 숫자 형식의 제목(heading)을 식별하고, 이를 이용하여 문서의 계층적인 섹션(Section) 구조를 구축합니다. 각 섹션은 제목 번호, 제목 텍스트, 레벨, 문서 인덱스 범위 등을 포함하며, 문서의 논리적인 구조를 파악하는 데 사용됩니다.

## 주요 함수/클래스 (Key Functions/Classes)

### `_detect_heading(text: str) -> Tuple[str, str, int] | None`
- **목적**: 주어진 텍스트가 숫자 형식의 제목 패턴(예: "1.1 제목", "1. 1.1 제목")과 일치하는지 감지합니다.
- **로직**:
    - `HEADING_RE` 정규 표현식을 사용하여 텍스트에서 제목 번호와 제목 텍스트를 추출합니다.
    - 제목 번호에서 공백과 점을 정규화하여 "1. 1"을 "1.1"과 같이 만듭니다.
- **반환**: 제목 번호, 제목 텍스트, 제목 레벨(점의 개수)을 포함하는 튜플 또는 `None`.

### `build_sections(paragraphs: List[dict]) -> List[Section]`
- **목적**: 문단 리스트에서 섹션 트리를 구축합니다.
- **로직**:
    - 문단을 `doc_index`를 기준으로 정렬합니다.
    - `_detect_heading`을 사용하여 각 문단이 제목인지 확인합니다.
    - 스택(stack) 자료구조를 사용하여 계층적인 섹션 구조를 관리합니다.
    - 현재 제목의 레벨보다 높거나 같은 레벨의 이전 섹션들을 닫고(span 종료), 새로운 섹션을 스택에 추가합니다.
    - 각 섹션은 `Section` 객체로 생성되며, `id`, `number`, `title`, `level`, `doc_index`, `span`, `path`, `block_ids`, `blocks`, `subsections`, `heading_block_id` 등의 필드를 채웁니다.
    - 모든 문단을 처리한 후, 스택에 남아있는 섹션들의 `span`을 최종 `doc_index`로 닫습니다.
- **반환**: 최상위 `Section` 객체 리스트 (문서의 루트 섹션들).

### `iter_sections(sections: List[Section]) -> Iterable[Section]`
- **목적**: 주어진 섹션 리스트와 그 하위 섹션들을 재귀적으로 순회하는 제너레이터 함수입니다.
- **로직**:
    - 각 섹션을 `yield`하고, 해당 섹션의 `subsections`에 대해 재귀적으로 `iter_sections`를 호출합니다.
- **반환**: `Section` 객체를 순회하는 이터레이터.

## 사용된 주요 필드 (Key Fields Used)

- **`paragraphs`**: 원본 문단 데이터 딕셔너리 리스트.
    - **`doc_index`**: 문단의 문서 인덱스.
    - **`text`**: 문단의 텍스트 내용.
- **`Section`**: 문서의 계층적 섹션 구조를 나타내는 객체.
    - **`id`**: 섹션의 고유 식별자 (예: "sec_1.1").
    - **`number`**: 섹션의 번호 (예: "1.1").
    - **`title`**: 섹션의 제목 텍스트.
    - **`level`**: 섹션의 계층적 레벨 (예: 1, 2, 3).
    - **`doc_index`**: 섹션 제목 문단의 문서 인덱스.
    - **`span`**: 섹션이 커버하는 문서 인덱스 범위 `[start_doc_index, end_doc_index)`.
    - **`path`**: 섹션의 계층적 경로 (예: ["1 제목", "1.1 하위 제목"]).
    - **`block_ids`**: 해당 섹션에 할당된 콘텐츠 블록들의 ID 리스트.
    - **`blocks`**: 해당 섹션에 할당된 `ContentBlock` 객체 리스트.
    - **`subsections`**: 자식 섹션 리스트.
    - **`heading_block_id`**: 섹션 제목에 해당하는 블록의 ID.
- **`HEADING_RE`**: 제목 감지를 위한 정규 표현식.
