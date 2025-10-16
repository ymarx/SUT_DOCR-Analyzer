from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------
# 블록 타입 정의
# ---------------------------
class ContentBlockType(Enum):
    """콘텐츠 블록 타입"""
    PARAGRAPH = "paragraph"
    TITLE = "title"
    HEADING = "heading"
    TABLE = "table"
    DIAGRAM = "diagram"
    IMAGE = "image"
    LIST = "list"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    FORMULA = "formula"

class DiagramType(Enum):
    """다이어그램 유형"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"

# ---------------------------
# 서브 데이터 타입
# ---------------------------
@dataclass
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float
    page: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SemanticInfo:
    keywords: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    cross_refs: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TableData:
    doc_index: int
    rows: int
    cols: int
    data: List[List[str]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ListData:
    ordered: bool
    level: int
    items: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessStep:
    """
    다이어그램의 개별 단계(스텝).
    - sequence: 스텝 순서(1부터). 원형숫자/숫자 마커를 분석하여 채움. 없으면 좌표/연결선 기반 추론.
    - title: 스텝의 간단한 라벨(노멀라이즈된 문자열).
    - details: 괄호/주석 등 보조 설명 문자열들.
    - marker: 원문에 나타난 단계 마커 문자열(예: '①', '1.', '2)' 등).
    - marker_type: 'circled' | 'arabic' | 'roman' | 'alpha' | 'bullet' | 'unknown'
    - raw_text: 도형에 들어있던 원문 텍스트(정규화 전).
    - dids: 이 스텝과 매핑된 shape id 목록(예: ['d19_2']).
    - doc_index: 스텝이 속한 문서 단락 인덱스.
    - linked_text_paragraphs: 같은 섹션 내에서 설명으로 연결된 문단 doc_index들.
    - confidence: 스텝 추정 신뢰도(0~1).
    """
    sequence: int
    title: str
    details: List[str] = field(default_factory=list)
    marker: str = ""
    marker_type: Optional[str] = None
    raw_text: Optional[str] = None
    dids: List[str] = field(default_factory=list)
    doc_index: Optional[int] = None
    linked_text_paragraphs: List[int] = field(default_factory=list)
    confidence: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class DiagramConnector:
    """스텝 간 연결선(간선) 정보"""
    did: str                      # 커넥터 shape id
    type: str = "arrow"           # 'arrow' 등
    from_step: Optional[int] = None
    to_step: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class DiagramData:
    """
    다이어그램 구조 데이터 (DocJSON에 저장되는 최종 형태)

    필수
    - id: 다이어그램 식별자(예: 'diag_4_2_seq')
    - doc_index: 대표 문단 인덱스 (섹션 제목에 가장 가까운 인덱스 등)
    - diagram_type: DiagramType (sequential/parallel/hybrid/unknown)

    선택
    - anchor_heading: 다이어그램이 걸린 섹션 제목(선행 문단 텍스트)
    - doc_indices: 다이어그램에 포함된 모든 도형의 doc_index 집합
    - flow_direction: 'left_to_right' | 'top_to_bottom' | 'unknown'
    - page_hint: 페이지 힌트(좌표 확정 전)
    - order_evidence: 순서 추론에 사용된 근거(예: ['circled_number','connector_arrow','x_position'])
    - steps: ProcessStep 리스트
    - connectors: DiagramConnector 리스트
    - bbox: 페이지 좌표(BoundingBox dict 등). 후처리에서 채움
    - notes: 비고

    """
    id: str
    doc_index: int
    diagram_type: "DiagramType"

    # optional
    anchor_heading: Optional[str] = None
    doc_indices: List[int] = field(default_factory=list)
    flow_direction: Optional[str] = None
    page_hint: Optional[int] = None
    order_evidence: List[str] = field(default_factory=list)
    steps: List["ProcessStep"] = field(default_factory=list)
    connectors: List["DiagramConnector"] = field(default_factory=list)
    bbox: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Enum 직렬화
        if hasattr(self.diagram_type, "value"):
            d["diagram_type"] = self.diagram_type.value
        return d


# ---------------------------
# 콘텐츠 블록 (flat list 단위)
# ---------------------------
@dataclass
class ContentBlock:
    id: str
    type: ContentBlockType | str
    doc_index: Optional[int] = None
    text: Optional[str] = None         # paragraph/heading/caption 텍스트 등
    level: Optional[int] = None        # heading/list 레벨
    page: Optional[int] = None

    bbox: Optional[BoundingBox] = None
    semantic: Optional[SemanticInfo] = None

    table: Optional[TableData] = None
    list_data: Optional[ListData] = None
    diagram: Optional[DiagramData] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        t = self.type
        d["type"] = t.value if hasattr(t, "value") else t
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ContentBlock":
        t = d.get("type")
        # 허용: 문자열이면 Enum으로 매핑 시도(실패 시 원문 유지)
        cb_type = ContentBlockType(t) if isinstance(t, str) and t in {e.value for e in ContentBlockType} else (t if t is not None else ContentBlockType.PARAGRAPH)
        return ContentBlock(
            id=d.get("id"),
            type=cb_type,
            doc_index=d.get("doc_index"),
            text=d.get("text"),
            level=d.get("level"),
            page=d.get("page"),
            bbox=d.get("bbox"),
            semantic=d.get("semantic"),
            table=d.get("table"),
            list_data=d.get("list_data"),
            diagram=d.get("diagram"),
        )


# ---------------------------
# 문서 메타데이터
# ---------------------------
@dataclass
class DocumentMetadata:
    document_type: Optional[str] = None 
    category: Optional[str] = None      
    title: Optional[str] = None
    doc_number: Optional[str] = None
    revision: Optional[str] = None
    effective_date: Optional[str] = None
    author: Optional[str] = None
    page_count: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------
# 섹션 트리 (섹션마다 path, blocks 포함)
# ---------------------------
@dataclass
class Section:
    """
    section == heading
    - number: '1', '1.1', '1.1.1', ...
    - doc_index: heading이 등장한 단락의 doc_index
    - span: [start, end) 구간. start = doc_index, end = 다음 동레벨↑ 헤딩의 doc_index 또는 문서 끝 + 1
    """
    id: str
    number: str
    title: str
    level: int
    doc_index: int

    # 구간 및 탐색 보조
    span: List[int] = field(default_factory=lambda: [0, 0])        # [start, end)
    path: List[str] = field(default_factory=list)                   # e.g., ["1 목적", "1.1 적용범위"]

    # 소속 블록
    block_ids: List[str] = field(default_factory=list)
    blocks: List["ContentBlock"] = field(default_factory=list)

    # 트리
    subsections: List["Section"] = field(default_factory=list)

    # (선택) 과거 호환용: heading_block_id가 필요하면 Optional로
    heading_block_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "number": self.number,
            "title": self.title,
            "level": self.level,
            "doc_index": self.doc_index,
            "span": list(self.span),
            "path": list(self.path),
            "block_ids": list(self.block_ids),
            "blocks": [b.to_dict() for b in self.blocks],
            "subsections": [s.to_dict() for s in self.subsections],
            "heading_block_id": self.heading_block_id,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Section":
        sec = Section(
            id=d.get("id"),
            number=d.get("number"),
            title=d.get("title"),
            level=int(d.get("level")) if d.get("level") is not None else 1,
            doc_index=int(d.get("doc_index")) if d.get("doc_index") is not None else 0,
        )
        # Optional fields
        sec.span = list(d.get("span") or [sec.doc_index, sec.doc_index + 1])
        sec.path = list(d.get("path") or [])
        sec.block_ids = list(d.get("block_ids") or [])
        blks = d.get("blocks") or []
        sec.blocks = [ContentBlock.from_dict(b) if not isinstance(b, ContentBlock) else b for b in blks]
        subs = d.get("subsections") or []
        sec.subsections = [Section.from_dict(s) if not isinstance(s, Section) else s for s in subs]
        sec.heading_block_id = d.get("heading_block_id")
        return sec
    
# ---------------------------
# 최종 산출 루트
# ---------------------------
@dataclass
class DocumentDocJSON:
    version: str
    metadata: DocumentMetadata | Dict[str, Any]
    blocks: List[ContentBlock] = field(default_factory=list)   # flat 블록 전체
    sections: List[Section] = field(default_factory=list)      # 섹션 트리

    def __post_init__(self) -> None:
        # metadata가 dict로 들어오면 DocumentMetadata로 변환하여 내부 일관성 유지
        if isinstance(self.metadata, dict):
            self.metadata = DocumentMetadata(**self.metadata)

        self.blocks = [b if isinstance(b, ContentBlock) else ContentBlock.from_dict(b) for b in (self.blocks or [])]
        self.sections = [s if isinstance(s, Section) else Section.from_dict(s) for s in (self.sections or [])]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "metadata": self.metadata.to_dict() if hasattr(self.metadata, "to_dict") else self.metadata,
            "blocks": [b.to_dict() for b in self.blocks],
            "sections": [s.to_dict() for s in self.sections],
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "DocumentDocJSON":
        return cls(
            version=payload.get("version", "0.0.0"),
            metadata=payload.get("metadata", {}),
            blocks=payload.get("blocks", []),
            sections=payload.get("sections", []),
        )
