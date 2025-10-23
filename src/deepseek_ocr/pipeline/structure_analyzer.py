"""
Page structure analyzer for Pass 1.

Uses DeepSeek-OCR <|grounding|> mode to detect all elements with bounding boxes.
"""

from PIL import Image
import logging

from ..engine.deepseek_engine import DeepSeekEngine
from ..core.types import PageStructure

logger = logging.getLogger(__name__)


class PageStructureAnalyzer:
    """
    Pass 1: Analyze page structure and detect all elements.

    Uses DeepSeek-OCR with <|grounding|> mode to detect:
    - Element types (7 categories)
    - Bounding box coordinates
    - Text preview (for text elements)
    """

    def __init__(self, engine: DeepSeekEngine):
        """
        Initialize structure analyzer.

        Args:
            engine: DeepSeekEngine instance
        """
        self.engine = engine

    def analyze(self, page_image: Image.Image, page_num: int) -> PageStructure:
        """
        Analyze page structure with element detection.

        Args:
            page_image: PIL Image of the page
            page_num: Page number (1-indexed)

        Returns:
            PageStructure with detected elements and bounding boxes

        Example:
            >>> analyzer = PageStructureAnalyzer(engine)
            >>> structure = analyzer.analyze(page_image, page_num=1)
            >>> print(f"Detected {len(structure.elements)} elements")
        """
        logger.info(f"Analyzing structure of page {page_num}...")

        # Call DeepSeek engine with structure analysis prompt
        structure = self.engine.infer_structure(page_image, page_num)

        logger.info(
            f"✅ Page {page_num}: Detected {len(structure.elements)} elements"
        )

        return structure
