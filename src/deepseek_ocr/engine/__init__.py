"""DeepSeek-OCR engine module."""

from .deepseek_engine import DeepSeekEngine
from .prompts import (
    STRUCTURE_ANALYSIS_PROMPT,
    TEXT_HEADER_PROMPT,
    TEXT_SECTION_PROMPT,
    TEXT_PARAGRAPH_PROMPT,
    TABLE_ANALYSIS_PROMPT,
    GRAPH_ANALYSIS_PROMPT,
    DIAGRAM_ANALYSIS_PROMPT,
    COMPLEX_IMAGE_PROMPT,
    get_element_prompt,
)

__all__ = [
    "DeepSeekEngine",
    "STRUCTURE_ANALYSIS_PROMPT",
    "TEXT_HEADER_PROMPT",
    "TEXT_SECTION_PROMPT",
    "TEXT_PARAGRAPH_PROMPT",
    "TABLE_ANALYSIS_PROMPT",
    "GRAPH_ANALYSIS_PROMPT",
    "DIAGRAM_ANALYSIS_PROMPT",
    "COMPLEX_IMAGE_PROMPT",
    "get_element_prompt",
]
