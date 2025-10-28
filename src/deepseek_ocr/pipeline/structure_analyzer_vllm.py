"""
Page structure analyzer for Pass 1 with vLLM batch processing.

Uses DeepSeek-OCR <|grounding|> mode to detect all elements with bounding boxes.
Optimized for batch processing with parallel preprocessing.
"""

from typing import List
from PIL import Image
import logging

from ..engine.deepseek_vllm_engine import DeepSeekVLLMEngine
from ..core.types import PageStructure
from .markdown_parser import MarkdownGroundingParser

logger = logging.getLogger(__name__)


class PageStructureAnalyzerVLLM:
    """
    Pass 1: Batch analyze page structure and detect all elements.

    Uses DeepSeek-OCR vLLM with <|grounding|> mode to detect:
    - Element types (7 categories)
    - Bounding box coordinates
    - Text preview (for text elements)

    Key features:
    - Batch processing for multiple pages simultaneously
    - Parallel image preprocessing
    - Markdown grounding parser for official output format
    """

    def __init__(self, engine: DeepSeekVLLMEngine):
        """
        Initialize structure analyzer.

        Args:
            engine: DeepSeekVLLMEngine instance
        """
        self.engine = engine
        self.parser = MarkdownGroundingParser()

    def analyze_batch(
        self, page_images: List[Image.Image], page_nums: List[int]
    ) -> List[PageStructure]:
        """
        Batch analyze page structures with element detection.

        This is the primary method for vLLM optimization - processes all pages
        in a single vLLM.generate() call.

        Args:
            page_images: List of PIL Images (one per page)
            page_nums: List of page numbers (1-indexed)

        Returns:
            List of PageStructure with detected elements and bounding boxes

        Example:
            >>> analyzer = PageStructureAnalyzerVLLM(engine)
            >>> page_images = [page1_img, page2_img, page3_img]
            >>> page_nums = [1, 2, 3]
            >>> structures = analyzer.analyze_batch(page_images, page_nums)
            >>> print(f"Analyzed {len(structures)} pages")
        """
        logger.info(f"Pass 1: Batch analyzing {len(page_images)} pages structure...")

        # Step 1: vLLM batch inference (single call for all pages)
        raw_structures = self.engine.infer_structure_batch(page_images, page_nums)

        # Step 2: Parse markdown outputs into structured elements
        structures = []
        for idx, (raw_structure, page_image) in enumerate(zip(raw_structures, page_images)):
            try:
                # Parse markdown with grounding tags
                elements = self.parser.parse(
                    markdown_text=raw_structure.raw_response,
                    page_num=raw_structure.page_num,
                    image_width=page_image.width,
                    image_height=page_image.height,
                )

                # Update structure with parsed elements
                structure = PageStructure(
                    page_num=raw_structure.page_num,
                    elements=elements,
                    raw_response=raw_structure.raw_response,
                )

                structures.append(structure)

                logger.info(
                    f"  Page {raw_structure.page_num}: {len(elements)} elements detected"
                )

            except Exception as e:
                logger.error(
                    f"⚠️ Warning: Failed to parse page {raw_structure.page_num}: {e}"
                )
                # Keep raw structure on error
                structures.append(raw_structure)

        logger.info(f"✅ Pass 1 complete: {len(structures)} pages analyzed")
        return structures

    def analyze(self, page_image: Image.Image, page_num: int) -> PageStructure:
        """
        Single page structure analysis (uses batch internally).

        For compatibility with existing code. Prefer analyze_batch() for performance.

        Args:
            page_image: PIL Image of the page
            page_num: Page number (1-indexed)

        Returns:
            PageStructure with detected elements and bounding boxes

        Example:
            >>> analyzer = PageStructureAnalyzerVLLM(engine)
            >>> structure = analyzer.analyze(page_image, page_num=1)
            >>> print(f"Detected {len(structure.elements)} elements")
        """
        structures = self.analyze_batch([page_image], [page_num])
        return structures[0]
