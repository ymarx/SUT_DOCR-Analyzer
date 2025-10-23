"""
DeepSeek-OCR Core Module

핵심 타입, 설정, 유틸리티 모듈
"""

from .types import (
    # Element Types
    ElementType,

    # Data Classes
    BoundingBox,
    TextBlockData,
    GraphData,
    TableData,
    DiagramData,
    ComplexImageData,

    # Content Block
    ContentBlock,

    # Document Structure
    Section,
    DocumentMetadata,
    DocumentDocJSON,

    # Analysis Results
    PageStructure,
    ElementDetection,
    ElementAnalysis,
)

from .config import Config, load_config
from .utils import (
    crop_bbox,
    save_image,
    parse_numbering,
    extract_keywords,
)

__all__ = [
    # Types
    "ElementType",
    "BoundingBox",
    "TextBlockData",
    "GraphData",
    "TableData",
    "DiagramData",
    "ComplexImageData",
    "ContentBlock",
    "Section",
    "DocumentMetadata",
    "DocumentDocJSON",
    "PageStructure",
    "ElementDetection",
    "ElementAnalysis",

    # Config
    "Config",
    "load_config",

    # Utils
    "crop_bbox",
    "save_image",
    "parse_numbering",
    "extract_keywords",
]
