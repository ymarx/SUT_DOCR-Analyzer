# Diagram Analyzer (다이어그램 분석기)

## 개요 (Overview)
이 분석기는 XML IR(Intermediate Representation)에서 다이어그램 구성 요소(단계 및 연결선)를 추출하고, 이를 재구성하여 DocJson 형식에 맞는 다이어그램 데이터를 생성합니다. 주요 기능은 다음과 같습니다:
- 문서 인덱스(doc_index)별로 드로잉(drawing)을 그룹화합니다.
- 인접한 문서 인덱스의 다이어그램 부분을 병합하여 전체 다이어그램을 스티칭합니다.
- 마커(예: 숫자, 로마 숫자, 원형 숫자)를 기반으로 다이어그램 단계의 순서를 정렬합니다. 마커가 없는 경우, 좌표(x+y)를 기준으로 정렬하여 순서를 부여합니다.
- 연결선(connector)의 경우, 가장 가까운 두 단계를 추정하여 `from_step`과 `to_step`을 연결합니다.

## 주요 함수/클래스 (Key Functions/Classes)

### `DiagramAnalyzer` 클래스
- **목적**: 정제된(sanitized) XML IR 데이터를 기반으로 다이어그램 구성 요소를 추출하고 재구성합니다.
- **`__init__(self, sanitized: Dict[str, Any])`**:
    - `sanitized`: 정제된 XML IR 딕셔너리. `drawings` 키를 포함해야 합니다.
    - `self.drawings`: `sanitized` 딕셔너리에서 추출된 드로잉 리스트.
- **`extract(self) -> List[DiagramData]`**:
    - `DiagramAnalyzer`의 핵심 메서드로, 드로잉 데이터를 분석하여 `DiagramData` 객체 리스트를 반환합니다.
    - `doc_index`별로 드로잉을 분류하고, 인접한 다이어그램 부분을 병합합니다.

### `_parse_marker(text: str, circled: bool) -> Tuple[int, str, Optional[str], str]`
- **목적**: 텍스트에서 마커(예: "①", "1.", "I.")를 파싱하여 순서, 레이블, 마커 타입 및 원본 마커 텍스트를 추출합니다.
- **반환**: `(sequence, title, marker_type, marker_literal)` 튜플.

### `_is_connector(d: Dict[str, Any]) -> bool`
- **목적**: 주어진 드로잉 딕셔너리가 연결선(connector)인지 여부를 판단합니다.

### `_pos(s: Dict[str, Any]) -> Tuple[float, float, float, float]`
- **목적**: 주어진 도형(shape) 딕셔너리에서 위치(x, y)와 크기(width, height) 정보를 추출합니다.
- **반환**: `(x, y, width, height)` 튜플.

### `_center(s: Dict[str, Any]) -> Tuple[float, float]`
- **목적**: 주어진 도형(shape) 딕셔너리의 중심 좌표(x, y)를 계산합니다.

### `_serialize_diagram(d: Any) -> Dict[str, Any]`
- **목적**: `DiagramData` 객체 또는 유사한 객체를 안전하게 딕셔너리 형태로 직렬화합니다.

### `extract_diagram_components(diagrams: List[Any]) -> Dict[str, Any]`
- **목적**: 분석 결과를 `{'diagrams': [...]}` 포맷으로 감싸서 반환합니다.

### `_try_run_diagram_analyzer(ir: Dict[str, Any]) -> List[DiagramData]`
- **목적**: `DiagramAnalyzer`를 실행하여 다이어그램을 추출하고, 예외 발생 시 로깅합니다.

### `emit_diagram_components_from_ir(ir: Dict[str, Any], xml_ir_path: str | Path, basename: str) -> str`
- **목적**: XML IR에서 다이어그램 구성 요소를 추출하고, 이를 JSON 파일로 저장합니다.
- **`ir`**: XML IR 딕셔너리 (원본 `drawings` 키를 포함해야 함).
- **`xml_ir_path`**: XML IR 파일의 경로. 출력 파일 경로를 구성하는 데 사용됩니다.
- **`basename`**: 출력 파일 이름의 기본 이름.
- **`payload`**: `DiagramData` 객체 리스트를 딕셔너리 리스트로 변환한 것.
- **`output_dir`**: `xml_ir_path`를 기반으로 생성되는 `_components` 디렉토리.
- **`output_path`**: 최종 JSON 파일이 저장될 경로.

## 사용된 주요 필드 (Key Fields Used)

- **`ir` (Intermediate Representation)**:
    - **`drawings`**: 문서 내의 모든 드로잉(도형, 연결선 등) 정보를 담고 있는 리스트.
    - **`paragraphs`**: 문서 내의 모든 문단 정보를 담고 있는 리스트.
    - **`tables`**: 문서 내의 모든 테이블 정보를 담고 있는 리스트.
- **`DiagramData`**: 추출된 단일 다이어그램의 구조화된 데이터.
    - **`id`**: 다이어그램의 고유 식별자.
    - **`doc_index`**: 다이어그램이 속한 문서의 인덱스.
    - **`diagram_type`**: 다이어그램의 유형 (예: `SEQUENTIAL`, `UNKNOWN`).
    - **`steps`**: 다이어그램 내의 각 단계를 나타내는 `ProcessStep` 객체 리스트.
    - **`connectors`**: 다이어그램 내의 연결선을 나타내는 `DiagramConnector` 객체 리스트.
- **`ProcessStep`**: 다이어그램 내의 단일 단계.
    - **`sequence`**: 단계의 순서 번호.
    - **`title`**: 단계의 제목 또는 설명.
    - **`marker`**: 단계에 사용된 원본 마커 텍스트 (예: "①").
    - **`marker_type`**: 마커의 유형 (예: "circled", "arabic", "roman").
    - **`dids`**: 드로잉 식별자 리스트.
- **`DiagramConnector`**: 다이어그램 내의 단일 연결선.
    - **`did`**: 연결선의 고유 식별자.
    - **`type`**: 연결선의 유형 (예: "arrow").
    - **`from_step`**: 연결선이 시작되는 단계의 순서 번호.
    - **`to_step`**: 연결선이 끝나는 단계의 순서 번호.
- **`sanitized`**: `DiagramAnalyzer`의 입력으로 사용되는 정제된 데이터. `drawings` 키를 포함합니다.
- **`output_dir`**: 다이어그램 구성 요소 JSON 파일이 저장될 디렉토리.
- **`file_name`**: 저장될 JSON 파일의 이름.
- **`payload`**: `DiagramData` 객체 리스트를 딕셔너리 리스트로 변환한 최종 저장 데이터.
