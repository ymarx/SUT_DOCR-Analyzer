"""
Element analyzer for Pass 2 with vLLM batch processing.

Analyzes individual elements in detail with type-specific prompts and context.
Optimized for batch processing with parallel cropping and preprocessing.
"""

from typing import List, Tuple
from PIL import Image
import logging
from concurrent.futures import ThreadPoolExecutor

from ..engine.deepseek_vllm_engine import DeepSeekVLLMEngine
from ..core.types import ElementDetection, ElementAnalysis, PageStructure, ElementType
from ..core.utils import crop_bbox

logger = logging.getLogger(__name__)


class ElementAnalyzerVLLM:
    """
    Pass 2: Batch analyze individual elements in detail.

    Extracts [항목], [키워드], [자연어 요약] for each element using
    type-specific prompts with surrounding context.

    Key features:
    - Batch processing for multiple elements simultaneously
    - Parallel image cropping
    - Context extraction from surrounding elements
    - Type-specific analysis prompts
    """

    def __init__(self, engine: DeepSeekVLLMEngine, context_radius: float = 0.2):
        """
        Initialize element analyzer.

        Args:
            engine: DeepSeekVLLMEngine instance
            context_radius: Spatial radius for context extraction (as fraction of page height)
        """
        self.engine = engine
        self.context_radius = context_radius

    def analyze_batch(
        self,
        elements: List[ElementDetection],
        page_images: List[Image.Image],
        page_structures: List[PageStructure],
    ) -> List[ElementAnalysis]:
        """
        Batch analyze elements from multiple pages.

        This is the primary method for vLLM optimization - processes all elements
        in a single vLLM.generate() call.

        Args:
            elements: List of ElementDetection objects from Pass 1
            page_images: List of full page PIL Images (indexed by page_num)
            page_structures: List of PageStructure from Pass 1 (for context extraction)

        Returns:
            List of ElementAnalysis with extracted data

        Example:
            >>> analyzer = ElementAnalyzerVLLM(engine)
            >>> elements = [elem1, elem2, elem3]  # From Pass 1
            >>> page_images = {1: page1_img, 2: page2_img}
            >>> analyses = analyzer.analyze_batch(elements, page_images, structures)
            >>> print(f"Analyzed {len(analyses)} elements")
        """
        if not elements:
            logger.warning("No elements to analyze in Pass 2")
            return []

        logger.info(f"Pass 2: Batch analyzing {len(elements)} elements...")

        # Step 1: Parallel crop images
        logger.debug("Cropping element images...")
        cropped_images = []
        element_types = []
        element_ids = []
        contexts = []

        # Create page_num -> page_image mapping
        page_image_map = {i + 1: img for i, img in enumerate(page_images)}

        # Create page_num -> structure mapping
        structure_map = {s.page_num: s for s in page_structures}

        for element in elements:
            try:
                # Get page image
                page_image = page_image_map.get(element.bbox.page)
                if page_image is None:
                    logger.warning(
                        f"Page {element.bbox.page} not found for element {element.element_id}"
                    )
                    continue

                # Crop element
                cropped = crop_bbox(page_image, element.bbox)
                cropped_images.append(cropped)

                # Extract metadata
                element_types.append(element.element_type.value)
                element_ids.append(element.element_id)

                # Build context
                structure = structure_map.get(element.bbox.page)
                if structure:
                    context = self._build_context(element, structure.elements, page_image)
                else:
                    context = ""

                contexts.append(context)

            except Exception as e:
                logger.error(f"Failed to prepare element {element.element_id}: {e}")
                continue

        if not cropped_images:
            logger.warning("No elements successfully cropped")
            return []

        # Step 2: vLLM batch inference (single call for all elements)
        logger.info(f"Running vLLM batch inference for {len(cropped_images)} elements...")
        analyses = self.engine.infer_element_batch(
            cropped_images=cropped_images,
            element_types=element_types,
            element_ids=element_ids,
            contexts=contexts,
        )

        logger.info(f"✅ Pass 2 complete: {len(analyses)} elements analyzed")
        return analyses

    def analyze(
        self,
        element: ElementDetection,
        page_image: Image.Image,
        all_elements: List[ElementDetection],
    ) -> ElementAnalysis:
        """
        Single element analysis (uses batch internally).

        For compatibility with existing code. Prefer analyze_batch() for performance.

        Args:
            element: ElementDetection from Pass 1
            page_image: Full page image
            all_elements: All elements from Pass 1 (for context)

        Returns:
            ElementAnalysis with extracted data

        Example:
            >>> analyzer = ElementAnalyzerVLLM(engine)
            >>> analysis = analyzer.analyze(element, page_image, all_elements)
            >>> print(f"Keywords: {analysis.keywords}")
        """
        # Create minimal PageStructure for context
        structure = PageStructure(
            page_num=element.bbox.page, elements=all_elements, raw_response=""
        )

        # Use batch method with single element
        analyses = self.analyze_batch(
            elements=[element], page_images=[page_image], page_structures=[structure]
        )

        return analyses[0] if analyses else None

    def _build_context(
        self,
        target_element: ElementDetection,
        all_elements: List[ElementDetection],
        page_image: Image.Image,
    ) -> str:
        """
        Build context string from spatially nearby elements.

        Uses spatial proximity (within context_radius of page height) and
        extracts text_preview from nearby text elements.

        Args:
            target_element: Element being analyzed
            all_elements: All elements from Pass 1 (same page)
            page_image: Page image (for height calculation)

        Returns:
            Context string (max 500 chars)
        """
        # Calculate spatial search radius
        page_height = page_image.height
        search_radius_px = page_height * self.context_radius

        # Target element center
        target_center_y = (target_element.bbox.y1 + target_element.bbox.y2) / 2

        # Find nearby text elements
        nearby_texts = []
        text_types = {
            ElementType.TEXT_HEADER,
            ElementType.TEXT_SECTION,
            ElementType.TEXT_PARAGRAPH,
        }

        for elem in all_elements:
            # Skip non-text elements
            if elem.element_type not in text_types:
                continue

            # Skip self
            if elem.element_id == target_element.element_id:
                continue

            # Calculate distance
            elem_center_y = (elem.bbox.y1 + elem.bbox.y2) / 2
            distance = abs(elem_center_y - target_center_y)

            # Within radius?
            if distance <= search_radius_px:
                # Add with distance (for sorting)
                nearby_texts.append((distance, elem))

        # Sort by distance (closest first)
        nearby_texts.sort(key=lambda x: x[0])

        # Build context string
        context_parts = []
        total_chars = 0
        max_chars = 500

        for _, elem in nearby_texts:
            if elem.text_preview:
                # Add text with element type label
                text = f"[{elem.element_type.value}] {elem.text_preview}"
                if total_chars + len(text) > max_chars:
                    # Truncate
                    remaining = max_chars - total_chars
                    if remaining > 20:  # Only add if meaningful length
                        context_parts.append(text[:remaining] + "...")
                    break
                else:
                    context_parts.append(text)
                    total_chars += len(text)

        context = "\n".join(context_parts)

        logger.debug(
            f"Built context for {target_element.element_id}: {len(context)} chars from {len(nearby_texts)} nearby elements"
        )

        return context
