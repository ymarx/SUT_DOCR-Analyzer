"""
Extended DocJSON types for DeepSeek-OCR-based document processing.

This module extends the legacy DocJSON schema with:
- 7-category element classification (text_header, text_section, text_paragraph, table, graph, diagram, complex_image)
- Enhanced data types for graphs, tables, and diagrams with [항목], [키워드], [자연어 요약]
- Pass 1 (PageStructure) and Pass 2 (ElementAnalysis) result types
- Complex image handling with underlying type classification
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------
# Element Classification (7 categories)
# ---------------------------
class ElementType(Enum):
    """Document element types for DeepSeek-OCR classification"""
    TEXT_HEADER = "text_header"
    TEXT_SECTION = "text_section"
    TEXT_PARAGRAPH = "text_paragraph"
    TABLE = "table"
    GRAPH = "graph"
    DIAGRAM = "diagram"
    COMPLEX_IMAGE = "complex_image"


# ---------------------------
# Spatial Information
# ---------------------------
@dataclass
class BoundingBox:
    """Bounding box coordinates from <|grounding|> mode"""
    x1: float
    y1: float
    x2: float
    y2: float
    page: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height


# ---------------------------
# Enhanced Element Data Types
# ---------------------------
@dataclass
class TextBlockData:
    """
    Text element data with numbering detection.

    Fields:
    - numbering: Detected section number (e.g., '1.', '1.1.', '1.1.1.')
    - keywords: 5-10 important terms for vector embedding
    - summary: 2-3 sentence natural language summary
    """
    numbering: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GraphData:
    """
    Graph/Chart element data.

    Fields:
    - title: Graph title
    - graph_type: 'line_chart', 'bar_chart', 'scatter_plot', 'pie_chart', etc.
    - x_axis: {label, unit, range, values}
    - y_axis: {label, unit, range, values}
    - legend: List of legend labels
    - data_trends: List of observed trends (increasing, decreasing, etc.)
    - keywords: 5-10 important terms
    - summary: 2-3 sentence description
    - image_id: Unique ID for cropped image retrieval
    """
    title: Optional[str] = None
    graph_type: str = "unknown"
    x_axis: Dict[str, Any] = field(default_factory=dict)
    y_axis: Dict[str, Any] = field(default_factory=dict)
    legend: List[str] = field(default_factory=list)
    data_trends: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    image_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TableData:
    """
    Table element data.

    Extended fields:
    - markdown: Markdown representation of table
    - keywords: 5-10 important terms
    - summary: 2-3 sentence description
    - image_id: Unique ID for cropped image retrieval
    - is_complex: True if >30% merged cells or irregular structure
    """
    doc_index: int
    rows: int
    cols: int
    data: List[List[str]]
    markdown: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    image_id: Optional[str] = None
    is_complex: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiagramData:
    """
    Diagram element data.

    Extended fields:
    - mermaid: Mermaid diagram code
    - keywords: 5-10 important terms
    - summary: 2-3 sentence description
    - is_complex: True if >10 components or irregular structure
    """
    id: str
    doc_index: int
    diagram_type: str = "unknown"
    components: List[Dict[str, Any]] = field(default_factory=list)
    connections: List[Dict[str, Any]] = field(default_factory=list)
    mermaid: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    image_id: Optional[str] = None
    is_complex: bool = False
    bbox: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComplexImageData:
    """
    Complex image that cannot be properly analyzed.

    Fields:
    - underlying_type: Guessed element type ('table', 'graph', 'diagram', 'photo', 'unknown')
    - visible_text: Any text visible in the image
    - keywords: 5-10 extracted terms
    - complexity_reasons: List of reasons why it's complex (e.g., 'merged_cells', 'low_resolution', 'irregular_layout')
    - summary: 2-3 sentence description
    - image_id: Unique ID for cropped image retrieval
    """
    underlying_type: str = "unknown"
    visible_text: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    complexity_reasons: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    image_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------
# Unified Content Block
# ---------------------------
@dataclass
class ContentBlock:
    """
    Unified content block supporting all element types.

    Type-specific data is stored in corresponding fields:
    - text_data: For text_header, text_section, text_paragraph
    - table: For table elements
    - graph: For graph elements
    - diagram: For diagram elements
    - complex_image: For complex_image elements
    """
    id: str
    type: ElementType | str
    doc_index: Optional[int] = None
    text: Optional[str] = None
    level: Optional[int] = None
    page: Optional[int] = None
    bbox: Optional[BoundingBox] = None

    # Type-specific data
    text_data: Optional[TextBlockData] = None
    table: Optional[TableData] = None
    graph: Optional[GraphData] = None
    diagram: Optional[DiagramData] = None
    complex_image: Optional[ComplexImageData] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        t = self.type
        d["type"] = t.value if hasattr(t, "value") else t
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> ContentBlock:
        t = d.get("type")
        element_type = ElementType(t) if isinstance(t, str) and t in {e.value for e in ElementType} else t
        return ContentBlock(
            id=d.get("id"),
            type=element_type,
            doc_index=d.get("doc_index"),
            text=d.get("text"),
            level=d.get("level"),
            page=d.get("page"),
            bbox=d.get("bbox"),
            text_data=d.get("text_data"),
            table=d.get("table"),
            graph=d.get("graph"),
            diagram=d.get("diagram"),
            complex_image=d.get("complex_image"),
        )


# ---------------------------
# Document Metadata
# ---------------------------
@dataclass
class DocumentMetadata:
    """Document metadata for SUT technical documents"""
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
# Section Tree
# ---------------------------
@dataclass
class Section:
    """
    Hierarchical section structure based on numbering.

    Fields:
    - number: Section number ('1', '1.1', '1.1.1', ...)
    - doc_index: Heading appearance position
    - span: [start, end) range of doc_indices
    - path: Breadcrumb path (e.g., ["1 목적", "1.1 적용범위"])
    - blocks: Content blocks in this section
    - subsections: Child sections
    """
    id: str
    number: str
    title: str
    level: int
    doc_index: int
    span: List[int] = field(default_factory=lambda: [0, 0])
    path: List[str] = field(default_factory=list)
    block_ids: List[str] = field(default_factory=list)
    blocks: List[ContentBlock] = field(default_factory=list)
    subsections: List[Section] = field(default_factory=list)
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
    def from_dict(d: Dict[str, Any]) -> Section:
        sec = Section(
            id=d.get("id"),
            number=d.get("number"),
            title=d.get("title"),
            level=int(d.get("level")) if d.get("level") is not None else 1,
            doc_index=int(d.get("doc_index")) if d.get("doc_index") is not None else 0,
        )
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
# Final Document Structure
# ---------------------------
@dataclass
class DocumentDocJSON:
    """
    Final DocJSON output structure.

    Fields:
    - version: Schema version
    - metadata: Document metadata
    - blocks: Flat list of all content blocks
    - sections: Hierarchical section tree
    """
    version: str
    metadata: DocumentMetadata | Dict[str, Any]
    blocks: List[ContentBlock] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)

    def __post_init__(self) -> None:
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
    def from_dict(cls, payload: Dict[str, Any]) -> DocumentDocJSON:
        return cls(
            version=payload.get("version", "0.0.0"),
            metadata=payload.get("metadata", {}),
            blocks=payload.get("blocks", []),
            sections=payload.get("sections", []),
        )


# ---------------------------
# Pass 1: Page Structure Analysis Results
# ---------------------------
@dataclass
class ElementDetection:
    """
    Single element detected in Pass 1 structure analysis.

    Fields:
    - element_id: Unique element identifier
    - element_type: Detected type (ElementType enum)
    - bbox: Bounding box coordinates
    - confidence: Detection confidence (0-1)
    - text_preview: First few characters (for text elements)
    """
    element_id: str
    element_type: ElementType
    bbox: BoundingBox
    confidence: float = 1.0
    text_preview: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["element_type"] = self.element_type.value
        return d


@dataclass
class PageStructure:
    """
    Pass 1 result: Page-level structure with all detected elements.

    Fields:
    - page_num: Page number
    - elements: List of detected elements with bbox
    - raw_response: Raw DeepSeek-OCR response (for debugging)
    """
    page_num: int
    elements: List[ElementDetection] = field(default_factory=list)
    raw_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_num": self.page_num,
            "elements": [e.to_dict() for e in self.elements],
            "raw_response": self.raw_response,
        }


# ---------------------------
# Pass 2: Element-Specific Analysis Results
# ---------------------------
@dataclass
class ElementAnalysis:
    """
    Pass 2 result: Detailed analysis of a single element.

    Fields:
    - element_id: Matches ElementDetection.element_id from Pass 1
    - element_type: Element type
    - items: [항목] - Structural components
    - keywords: [키워드] - 5-10 important terms
    - summary: [자연어 요약] - 2-3 sentence description
    - structured_data: Type-specific parsed data (TableData, GraphData, etc.)
    - raw_response: Raw DeepSeek-OCR response (for debugging)
    """
    element_id: str
    element_type: ElementType
    items: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    raw_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["element_type"] = self.element_type.value
        return d
