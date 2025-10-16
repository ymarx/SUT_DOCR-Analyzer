sut-preprocess
================

DOCX → Sanitized(JSON) → Components → DocJSON 으로 이어지는 전처리 파이프라인과 CLI를 제공하는 저장소입니다. 오프라인 환경을 위한 uv + offline wheels, Docker 구성도 포함합니다.

이 문서는 처음 보는 분이 위에서부터 아래로 차례로 읽으면 프로젝트의 구조와 로직을 빠르게 이해하도록 돕습니다.

핵심 용어
- Core: 공통 타입 정의, I/O 유틸, 파서 인터페이스 등 파이프라인의 기반 계층입니다. 코드가 데이터를 어떻게 표현하고 저장/로드하는지의 “뼈대”를 담당합니다.
- Component: parser/sanitizer/analyzer 같은 기능 단위 모듈입니다. 각각 특정 입력을 받아 정규화·분석·조립을 수행하며, 필요 시 중간 산출물(JSON 컴포넌트)을 `_comp`에 저장합니다.
- IR/Sanitized: 파서+정제 결과로 얻는 중간 표현(JSON). 후속 분석의 입력이 됩니다.
- DocJSON: 최종 산출 형식. 섹션 트리와 블록들이 포함된 문서 구조 JSON입니다.

읽기 순서 가이드(탑다운)
1) 전체 흐름 한눈에 보기
   - CLI 빠른 실행 예시는 `src/mypkg/cli/README.md` 참고.
   - 입력 DOCX → 파싱 → 정제(sanitized) → 컴포넌트(리스트/테이블/다이어그램) → 섹션/블록 조립 → 메타데이터 → 최종 DocJSON.
2) 파이프라인 로직
   - 1단계: Parser
     - `components/parser/docx_parser.py`(python-docx 기반 텍스트/인라인 이미지), `components/parser/xml_parser.py`(ZIP/XML 파싱: 단락/리스트 메타, 표, 헤더/푸터, 드로잉 등)
   - 2단계: Sanitizer
     - `components/sanitizer/paragraph_sanitizer.py` 문단 병합/정리
     - `components/sanitizer/table_sanitizer.py` 표 병합/매트릭스화 + 선행 문단 연결
     - `components/sanitizer/diagram_sanitizer.py` 드로잉을 Diagram용 표준 스키마로 정제
   - 3단계: Analyzer/Assembler
     - 리스트/테이블/다이어그램을 블록으로 추출하고, 제목으로 섹션 트리를 만든 뒤 섹션 구간(span)에 블록을 배치
     - 문서 메타데이터(문서번호/개정/시행일/작성자/유형/카테고리/제목)를 텍스트/헤더/테이블에서 추출
   - 4단계: 산출
     - `_sanitized`에 정제 JSON, `_comp`에 컴포넌트(JSON), `_meta`에 메타(JSON), 루트 `processed/{doc-type}` 아래 최종 DocJSON을 저장
3) 실행 진입점과 파이프라인 코드
   - CLI: `src/mypkg/cli/main.py` — 단일 파일/디렉터리 처리, 컴포넌트 생성/사용 옵션
   - Parsing: `src/mypkg/pipelines/docx_parsing_pipeline.py` — DOCX → sanitized.json
   - Layout: `src/mypkg/pipelines/layout_analyzer_pipeline.py` — sanitized.json → components/meta → DocJSON

폴더/파일 안내(중요 파일 위주)
- src/mypkg/core
  - `docjson_types.py`: DocJSON의 타입(블록, 섹션, 다이어그램 등)과 직렬화 로직 정의
  - `base_parser.py`: 파서 공통 추상(BaseParser), 파싱 결과/레코드(ParagraphRecord/TableRecord/…)
  - `io.py`: 경로 규칙, JSON 저장/로드, `_comp`/`_meta`/DocJSON 파일 경로 생성 헬퍼
- src/mypkg/components/parser
  - `docx_parser.py`: python-docx로 문단/런, 인라인 이미지 추출
  - `xml_parser.py`: ZIP/XML을 직접 파싱해 표/헤더/푸터/관계/드로잉/넘버링/리스트 메타 추출
- src/mypkg/components/sanitizer
  - `paragraph_sanitizer.py`: docx/xml 문단 정보 병합 + 런 정리(공백/속성 병합)
  - `table_sanitizer.py`: gridSpan/vMerge 보정, 앵커 텍스트 채움, 2D 매트릭스 구성
  - `diagram_sanitizer.py`: drawings_raw → DrawingRecord 정규화(의사 좌표/텍스트 시그니처 등)
- src/mypkg/components/analyzer
  - `section_analyzer.py`: 숫자형 제목 인식 → 섹션 트리/구간(span) 생성
    - 관련 문서: `components/analyzer/docs/SECTION.md`
  - `list_table_analyzer.py`: 문단에서 리스트 묶음/테이블 블록 생성, `_comp` 저장 지원
    - 관련 문서: `components/analyzer/docs/LIST_AND_TABLE.md`
  - `diagram_analyzer.py`: 정제된 드로잉에서 단계/커넥터 추출, 인접 doc_index 스티칭
    - 관련 문서: `components/analyzer/docs/DIAGRAM.md`, `components/analyzer/docs/DETAILS_OF_DIAGRAM_FIELD.md`
  - `layout_assembler.py`: 문단/리스트/테이블/다이어그램 블록을 섹션 범위에 배치
    - 관련 문서: `components/analyzer/docs/LAYOUT_ASSEMBLER.md`
  - `document_metadata_analyzer.py`: 헤더/푸터/테이블/본문에서 메타데이터 추출
    - 관련 문서: `components/analyzer/docs/DOC_META.md`
- src/mypkg/pipelines
  - `docx_parsing_pipeline.py`: 두 파서를 병렬 실행 → sanitized JSON 구성/저장
  - `layout_analyzer_pipeline.py`: 섹션 생성 → 컴포넌트 산출/적재 → 블록 조립/정렬 → 메타 추출 → DocJSON 저장
- src/mypkg/cli
  - `main.py`: `sut-preprocess` 실행 인자 파싱, 단일 파일/폴더 처리 오케스트레이션
  - `README.md`: CLI 사용법/예시/출력 경로 규칙
- tests
  - `tests/*.py`, `tests/fixtures/*.docx`, `tests/output/*`: 파서/정제/레이아웃 스냅샷 테스트
  - `tests/README.md`: 파라미터라이즈로 샘플 추가 방법 안내
- scripts (개발 편의)
  - `src_make.py`: 소스 번들(zip) 생성
  - `wheel_save.py`: 오프라인 설치용 wheels 수집
  - 자세한 사용: `scripts/_THIS_FOLDER_IS_ONLY_FOR_DEV.md`
- 기타 문서/설정
  - `DOCKER_INSTALL.md`: 오프라인 wheels 기반 Docker 빌드 가이드
  - `pyproject.toml`, `requirements.txt`, `uv.lock`: 빌드/의존성
  - `wheels/*`: 수집된 오프라인 wheels 저장소

데이터 흐름(상세)
- 입력: DOCX
- Parser 단계
  - `docx_parser.py` → `paragraphs_docx`, `inline_images`
  - `xml_parser.py` → `paragraphs_xml`, `tables`, `headers`, `footers`, `relationships.map`, `drawings_raw`
- Sanitizer 단계
  - `paragraph_sanitizer.apply(docx, xml)` → 문단 병합/정리
  - `table_sanitizer.apply(tables, paragraphs)` → 2D 표 데이터 + `preceding_text`
  - `diagram_sanitizer.apply(drawings_raw, paragraphs)` → `DrawingRecord[]`
- Sanitized JSON 저장: `{paragraphs, drawings, tables, headers, footers, relationships, inline_images}`
- Layout 단계
  - `section_analyzer.build_sections(paragraphs)` → 섹션 트리/heading 인덱스
  - `list_table_analyzer`/`diagram_analyzer` → `_comp`에 리스트/테이블/다이어그램 저장(옵션)
  - `layout_assembler` → 문단/리스트/테이블/다이어그램 블록 생성/정렬/섹션에 배치
  - `document_metadata_analyzer` → 메타데이터 산출 후 `_meta` 저장
- 최종 산출: `DocumentDocJSON`(sections + blocks + metadata)

출력/디렉터리 규칙
- Sanitized: `data_store/processed/{doc_type}/{version}/{base_name}/_sanitized/<파일>.json`
- Components: `.../{base_name}/_comp/{base_name}_{list|table|diagram|blocks}.json`
- Metadata: `.../{base_name}/_meta/{base_name}.json`
- DocJSON: `data_store/processed/{doc_type}/{base_name}_{version}.docjson`

CLI 빠른 시작(요약)
- 단일 파일
  - `uv run sut-preprocess --raw ./data_store/raw/gisul-gijun/sample2_section.docx --doc-type gisul-gijun --version v3`
- 디렉터리 전체
  - `uv run sut-preprocess --raw ./data_store/raw/gisul-gijun --doc-type gisul-gijun --version v3 --all`
- 상세 옵션/예시는 `src/mypkg/cli/README.md` 참고
