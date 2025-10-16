# List and Table Analyzer (리스트 및 테이블 분석기)

## 개요 (Overview)
이 분석기는 DocJson 데이터에서 문단(paragraphs)과 테이블(tables) 정보를 분석하여 리스트와 테이블 구성 요소를 추출하고, 이를 DocJson 형식에 맞는 콘텐츠 블록으로 변환합니다. 추출된 리스트 및 테이블 구성 요소는 별도의 JSON 파일로 저장될 수 있습니다.

## 주요 함수/클래스 (Key Functions/Classes)

### `_style_tokens_from_para(p: Dict[str, Any]) -> List[str]`
- **목적**: 문단(paragraph) 딕셔너리에서 스타일 관련 키(예: "style", "style_name")의 값을 추출하고, 이를 토큰화(소문자화, 공백/하이픈/언더스코어 제거)하여 리스트로 반환합니다.

### `_looks_like_marker(text: str) -> bool`
- **목적**: 주어진 텍스트가 리스트 마커(예: 숫자, 로마 숫자, 알파벳 뒤에 점이나 괄호, 또는 일반적인 글머리 기호)처럼 보이는지 판단합니다.

### `_is_list_para(p: Dict[str, Any]) -> bool`
- **목적**: 주어진 문단 딕셔너리가 리스트 항목인지 여부를 판단합니다.
- **로직**:
    - 파서가 이미 `list_type`을 지정했거나, Word의 넘버링(`numId`)이 있는 경우 리스트로 간주합니다.
    - 스타일 토큰(`STYLE_LIST_TOKENS`)을 기반으로 리스트를 탐지합니다.
    - 최후의 수단으로 텍스트 마커 패턴을 통해 리스트 여부를 추정합니다.

### `_classify_ordering(p: Dict[str, Any]) -> Tuple[bool, str]`
- **목적**: 주어진 문단 딕셔너리의 넘버링 형식(`numFmt` 또는 `list_type`)을 기반으로 리스트가 순서가 있는지(ordered) 여부와 순서 체계(scheme)를 분류합니다.
- **반환**: `(ordered: bool, scheme: str)` 튜플. (예: `(True, "decimal")`, `(False, "bullet")`)

### `_list_level(p: Dict[str, Any]) -> int`
- **목적**: 주어진 문단 딕셔너리에서 리스트의 들여쓰기 레벨(`ilvl`)을 추출합니다. 기본값은 0입니다.

### `analyze_lists(paragraphs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], set]`
- **목적**: 문단 리스트에서 리스트 블록을 추출하고, 리스트로 분류된 문단의 `doc_index`를 반환합니다.
- **로직**:
    - 문단을 `doc_index`를 기준으로 정렬합니다.
    - `_is_list_para`를 사용하여 리스트 문단을 식별합니다.
    - `numId` 또는 스타일 토큰을 기반으로 동일한 리스트 묶음을 찾습니다.
    - 각 리스트 묶음을 `ContentBlock` 형태의 딕셔너리로 변환하고, `list_data` 필드에 리스트 항목들을 저장합니다.
    - 리스트로 처리된 문단의 `doc_index`를 `consumed` 집합에 추가하여 반환합니다.
- **반환**: `(list_blocks: List[Dict[str, Any]], consumed: set)` 튜플.

### `analyze_tables(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]`
- **목적**: 테이블 데이터에서 `ContentBlock` 형태의 테이블 블록을 생성합니다.
- **로직**:
    - 주어진 테이블 리스트의 각 테이블을 `ContentBlock` 형태의 딕셔너리로 변환합니다.
    - `id`, `type` ("table"), `doc_index`, `table` (원본 테이블 데이터) 등의 필드를 채웁니다.
- **반환**: `table_blocks: List[Dict[str, Any]]`.

### `emit_list_table_components_from_ir(paragraphs: List[Dict[str, Any]], tables: List[Dict[str, Any]], xml_ir_path: str | Path, basename: str)`
- **목적**: 문단 및 테이블 데이터에서 리스트와 테이블 구성 요소를 분석하고, 이를 별도의 JSON 파일로 저장합니다.
- **`paragraphs`**: 원본 문단 데이터 딕셔너리 리스트.
- **`tables`**: 원본 테이블 데이터 딕셔너리 리스트.
- **`xml_ir_path`**: XML IR 파일의 경로. 출력 파일 경로를 구성하는 데 사용됩니다.
- **`basename`**: 출력 파일 이름의 기본 이름.
- **`lists`**: `analyze_lists`에서 반환된 리스트 블록.
- **`consumed`**: `analyze_lists`에서 반환된 리스트로 처리된 문단의 `doc_index` 집합.
- **`tables_blk`**: `analyze_tables`에서 반환된 테이블 블록.
- **`save_list_components_from_ir`**: 리스트 구성 요소를 저장하는 함수.
- **`save_table_components_from_ir`**: 테이블 구성 요소를 저장하는 함수.
- **반환**: 저장된 리스트 및 테이블 파일의 경로를 포함하는 딕셔너리.

## 사용된 주요 필드 (Key Fields Used)

- **`paragraphs`**: 원본 문단 데이터 딕셔너리 리스트.
    - **`doc_index`**: 문단의 문서 인덱스.
    - **`list_type`**: 파서가 감지한 리스트 유형 (예: "bullet", "number").
    - **`numId`**: Word 넘버링 리스트의 고유 ID.
    - **`ilvl`**: Word 넘버링 리스트의 들여쓰기 레벨.
    - **`style`, `style_name`, `styleId`, `style_id`, `para_style`, `pStyle`**: 문단의 스타일 정보.
    - **`text`**: 문단의 텍스트 내용.
    - **`numFmt`**: Word 넘버링 형식 (예: "decimal", "lowerRoman", "bullet").
- **`tables`**: 원본 테이블 데이터 딕셔너리 리스트.
    - **`doc_index`**: 테이블의 문서 인덱스.
    - **`tid`**: 테이블의 고유 ID.
    - **`rows`**: 테이블의 행 수.
    - **`cols`**: 테이블의 열 수.
    - **`data`**: 테이블의 셀 데이터를 담고 있는 리스트 (행 -> 셀).
- **`ContentBlock`**: 문서의 단일 콘텐츠 블록을 나타내는 객체 (이 모듈에서는 딕셔너리 형태로 생성).
    - **`id`**: 블록의 고유 식별자.
    - **`type`**: 블록의 유형 (예: "list", "table").
    - **`doc_index`**: 블록이 시작되는 문서 인덱스.
    - **`text`**: 블록의 텍스트 내용 (리스트/테이블 블록의 경우 `None`).
    - **`level`**: 리스트 블록의 들여쓰기 레벨.
    - **`list_data`**: 리스트 블록의 경우, 리스트 항목들을 포함하는 딕셔너리.
        - **`ordered`**: 순서가 있는 리스트인지 여부 (True/False).
        - **`scheme`**: 순서 체계 (예: "decimal", "bullet", "roman").
        - **`level`**: 리스트의 들여쓰기 레벨.
        - **`items`**: 리스트 항목 텍스트 리스트.
    - **`table`**: 테이블 블록의 경우, 테이블 데이터를 포함하는 딕셔너리.
- **`consumed`**: `analyze_lists` 함수에서 리스트로 처리되어 DocJson의 일반 문단 블록으로 생성되지 않아야 할 문단들의 `doc_index` 집합.
- **`ORDERED_NUMFMTS`**: 순서 있는 리스트의 넘버링 형식 집합.
- **`UNORDERED_NUMFMTS`**: 순서 없는 리스트의 넘버링 형식 집합.
- **`STYLE_KEYS`**: 문단 스타일 정보를 추출하기 위한 키 리스트.
- **`STYLE_LIST_TOKENS`**: 리스트 스타일을 나타내는 토큰 집합.
