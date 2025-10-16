# Document Metadata Analyzer (문서 메타데이터 분석기)

## 개요 (Overview)
이 분석기는 `sanitizer.json` 파일에서 로드된 DocJson 데이터를 기반으로 문서의 메타데이터(문서 번호, 개정 번호, 시행일, 작성자, 문서 유형, 카테고리, 제목, 페이지 수)를 추출하고 `DocumentMetadata` 객체로 구성합니다. 텍스트, 헤더/푸터, 테이블 등 다양한 소스에서 정보를 찾아내며, 정규 표현식을 활용하여 특정 패턴의 데이터를 식별합니다.

## 주요 함수/클래스 (Key Functions/Classes)

### `DocumentMetadataAnalyzer` 클래스
- **목적**: DocJson 데이터에서 문서 메타데이터를 분석하고 추출합니다.
- **`__init__(self, docjson: Dict[str, Any])`**:
    - `docjson`: `sanitizer.json`에서 로드된 딕셔너리 형태의 DocJson 데이터.
    - `self.all_text`: `docjson` 내의 모든 텍스트를 수집한 문자열.
- **`analyze(self) -> DocumentMetadata`**:
    - 메타데이터 분석을 수행하는 핵심 메서드.
    - `_find_doc_number`, `_find_revision`, `_find_effective_date`, `_find_author`, `_extract_document_type_from_header`, `_extract_category_from_header`, `_extract_title_from_header` 등의 내부 메서드를 호출하여 각 메타데이터 필드를 채웁니다.
    - 최종적으로 `DocumentMetadata` 객체를 반환합니다.

### `_collect_all_text(self) -> str`
- **목적**: `docjson`의 헤더, 푸터, 문단, 테이블 등 모든 텍스트 요소를 하나의 문자열로 수집합니다.

### `_find_doc_number(self) -> Optional[str]`
- **목적**: 문서 번호(예: "TP-XXX-YYY-ZZZ" 형식)를 헤더/푸터, 테이블, 전체 텍스트 순으로 검색하여 추출합니다.

### `_find_revision(self) -> Optional[str]`
- **목적**: 개정 번호(예: "Rev. X" 형식)를 헤더/푸터, 테이블, 전체 텍스트 순으로 검색하여 추출합니다.

### `_find_effective_date(self) -> Optional[str]`
- **목적**: 시행일(예: "YYYY.MM.DD" 형식)을 헤더/푸터, 테이블, 전체 텍스트 순으로 검색하여 추출합니다. 다양한 날짜 패턴을 지원합니다.

### `_find_author(self) -> Optional[str]`
- **목적**: 작성자 정보를 테이블에서 우선적으로 찾고, 실패 시 전체 텍스트 또는 XML 구조 내 테이블에서 검색합니다.

### `_extract_document_type_from_header(self) -> Optional[str]`
- **목적**: 헤더 텍스트에서 문서 유형(예: "기술기준 포항제철소")을 정규 표현식을 사용하여 추출합니다.

### `_extract_category_from_header(self) -> Optional[str]`
- **목적**: 헤더 텍스트에서 카테고리(예: "제선부 > 고로공정")를 정규 표현식을 사용하여 추출합니다. 특정 키워드를 제거하는 로직을 포함합니다.

### `_extract_title_from_header(self) -> Optional[str]`
- **목적**: 헤더 텍스트에서 문서 제목을 정규 표현식을 사용하여 추출합니다.

### `_extract_document_type_from_table(self) -> Optional[str]`
- **목적**: 테이블에서 문서 유형(예: "기술기준포항제철소")을 검색하여 추출합니다.

### `_extract_category_from_table(self) -> Optional[str]`
- **목적**: 테이블에서 카테고리(예: "제선부 > 고로공정")를 검색하여 추출합니다.

### `_extract_title_from_table(self) -> Optional[str]`
- **목적**: 테이블에서 문서 제목을 검색하여 추출합니다. "Rev." 셀 옆의 셀에서 제목을 찾는 로직을 포함합니다.

## 사용된 주요 필드 (Key Fields Used)

- **`docjson`**: `sanitizer.json`에서 로드된 원본 DocJson 데이터 딕셔너리.
    - **`headers_footers`**: 문서의 헤더 및 푸터 정보를 담고 있는 딕셔너리.
        - **`headers`**: 헤더 텍스트 리스트.
        - **`footers`**: 푸터 텍스트 리스트.
    - **`paragraphs`**: 문서의 문단 정보를 담고 있는 리스트.
    - **`tables`**: 문서의 테이블 정보를 담고 있는 리스트.
        - **`data`**: 테이블의 셀 데이터를 담고 있는 리스트 (행 -> 셀).
    - **`page_count`**: 문서의 총 페이지 수.
    - **`xml_structure`**: 문서의 XML 구조 정보 (작성자 검색 시 사용될 수 있음).
- **`DocumentMetadata`**: 추출된 메타데이터를 구조화한 객체.
    - **`document_type`**: 문서의 유형.
    - **`category`**: 문서의 카테고리.
    - **`title`**: 문서의 제목.
    - **`doc_number`**: 문서 번호.
    - **`revision`**: 개정 번호.
    - **`effective_date`**: 시행일.
    - **`author`**: 작성자.
    - **`page_count`**: 페이지 수.
- **`all_text`**: `docjson`에서 수집된 모든 텍스트를 포함하는 단일 문자열.
- **`doc_num_pattern`**: 문서 번호 추출을 위한 정규 표현식 패턴.
- **`rev_pattern`**: 개정 번호 추출을 위한 정규 표현식 패턴.
- **`date_pattern_1`, `date_pattern_2`**: 시행일 추출을 위한 정규 표현식 패턴.
