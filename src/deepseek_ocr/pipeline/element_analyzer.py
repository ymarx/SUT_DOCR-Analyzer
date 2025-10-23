"""
Element analyzer for Pass 2.

Analyzes individual elements in detail with type-specific prompts.
"""

from PIL import Image
from typing import Dict, List, Optional
import logging

from ..engine.deepseek_engine import DeepSeekEngine
from ..core.types import ElementDetection, ElementAnalysis, PageStructure
from ..core.utils import crop_bbox

logger = logging.getLogger(__name__)


class ElementAnalyzer:
    """
    Pass 2: Analyze individual elements in detail.

    Extracts [항목], [키워드], [자연어 요약] for each element using
    type-specific prompts with surrounding context.
    """

    def __init__(self, engine: DeepSeekEngine, context_window: int = 2):
        """
        Initialize element analyzer.

        Args:
            engine: DeepSeekEngine instance
            context_window: Number of surrounding elements to include as context
        """
        self.engine = engine
        self.context_window = context_window

    def analyze(
        self,
        element: ElementDetection,
        page_image: Image.Image,
        all_elements: List[ElementDetection],
    ) -> ElementAnalysis:
        """
        Analyze single element in detail.

        Args:
            element: ElementDetection from Pass 1
            page_image: Full page image
            all_elements: All elements from Pass 1 (for context)

        Returns:
            ElementAnalysis with extracted data

        Example:
            >>> analyzer = ElementAnalyzer(engine)
            >>> analysis = analyzer.analyze(element, page_image, all_elements)
            >>> print(f"Keywords: {analysis.keywords}")
        """
        logger.debug(f"Analyzing element {element.element_id} ({element.element_type.value})...")

        # Crop element from page image
        cropped_image = crop_bbox(page_image, element.bbox)

        # Build context from surrounding elements
        context = self._build_context(element, all_elements)

        # Run Pass 2 analysis
        analysis = self.engine.infer_element(
            cropped_image=cropped_image,
            element_type=element.element_type.value,
            element_id=element.element_id,
            context=context,
        )

        return analysis

    def _build_context(
        self,
        target_element: ElementDetection,
        all_elements: List[ElementDetection],
    ) -> str:
        """
        Build context string from surrounding elements.

        Includes text_preview from nearby text elements.

        Args:
            target_element: Element being analyzed
            all_elements: All elements from Pass 1

        Returns:
            Context string
        """
        # Find elements within context window
        target_idx = None
        for idx, elem in enumerate(all_elements):
            if elem.element_id == target_element.element_id:
                target_idx = idx
                break

        if target_idx is None:
            return "No surrounding context available."

        # Get surrounding elements
        start_idx = max(0, target_idx - self.context_window)
        end_idx = min(len(all_elements), target_idx + self.context_window + 1)

        context_elements = all_elements[start_idx:end_idx]

        # Build context string from text elements
        context_parts = []
        for elem in context_elements:
            if elem.element_id == target_element.element_id:
                context_parts.append(f"[CURRENT ELEMENT: {elem.element_type.value}]")
            elif elem.text_preview:
                context_parts.append(f"{elem.element_type.value}: {elem.text_preview}")

        if not context_parts:
            return "No text context available in surrounding elements."

        return "\n".join(context_parts)
