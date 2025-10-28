"""
Markdown grounding parser for DeepSeek-OCR vLLM output.

Parses official <|ref|>...<|/ref|><|det|>...<|/det|> format
into structured ElementDetection objects.

Based on DeepSeek-OCR-vllm/run_dpsk_ocr_pdf.py re_match() function.
"""

import re
from typing import List, Tuple, Optional
from PIL import Image
from ..core.types import ElementDetection, ElementType, BoundingBox


class MarkdownGroundingParser:
    """
    Parser for DeepSeek-OCR markdown output with grounding tags.

    Official output format:
    ```
    <|ref|>label<|/ref|><|det|>[x1,y1,x2,y2]<|/det|>
    Markdown content...
    ```

    Where:
    - label: element type (e.g., 'title', 'text', 'table', 'image', 'figure')
    - [x1,y1,x2,y2]: bounding box in normalized coordinates (0-999)
    """

    # Official label to 7-category mapping
    LABEL_MAPPING = {
        # Text elements
        "title": ElementType.TEXT_HEADER,
        "heading": ElementType.TEXT_HEADER,
        "section-header": ElementType.TEXT_SECTION,
        "section_header": ElementType.TEXT_SECTION,
        "text": ElementType.TEXT_PARAGRAPH,
        "paragraph": ElementType.TEXT_PARAGRAPH,
        # Visual elements
        "table": ElementType.TABLE,
        "graph": ElementType.GRAPH,
        "chart": ElementType.GRAPH,
        "plot": ElementType.GRAPH,
        "figure": ElementType.DIAGRAM,  # Can be diagram or complex_image
        "diagram": ElementType.DIAGRAM,
        "flowchart": ElementType.DIAGRAM,
        "image": ElementType.COMPLEX_IMAGE,
        "photo": ElementType.COMPLEX_IMAGE,
        "picture": ElementType.COMPLEX_IMAGE,
    }

    def __init__(self):
        """Initialize markdown grounding parser."""
        # Pattern: <|ref|>label<|/ref|><|det|>[coordinates]<|/det|>
        self.ref_det_pattern = re.compile(
            r"<\|ref\|>(.*?)<\|/ref\|><\|det\|>(.*?)<\|/det\|>", re.DOTALL
        )

    def parse(
        self, markdown_text: str, page_num: int = 1, image_width: int = 1000, image_height: int = 1000
    ) -> List[ElementDetection]:
        """
        Parse markdown with grounding tags into ElementDetection objects.

        Args:
            markdown_text: Markdown text with <|ref|>/<|det|> tags
            page_num: Page number (1-indexed)
            image_width: Original image width (for bbox normalization)
            image_height: Original image height (for bbox normalization)

        Returns:
            List of ElementDetection objects
        """
        elements = []

        # Find all <|ref|>...<|/ref|><|det|>...<|/det|> matches
        matches = self.ref_det_pattern.findall(markdown_text)

        for idx, (label, coords_str) in enumerate(matches):
            try:
                # Parse coordinates
                # coords_str example: "[[100,200,800,600]]" or "[100,200,800,600]"
                coords_str = coords_str.strip()

                # Try to evaluate as Python literal (handles nested lists)
                try:
                    coords_list = eval(coords_str)
                except Exception:
                    # Fallback: manual parsing
                    coords_list = self._parse_coords_manual(coords_str)

                # Handle nested list [[x1,y1,x2,y2]] -> [x1,y1,x2,y2]
                if isinstance(coords_list, list) and len(coords_list) > 0:
                    if isinstance(coords_list[0], list):
                        coords_list = coords_list[0]

                # Extract coordinates
                if len(coords_list) < 4:
                    print(f"⚠️ Warning: Invalid coordinates for element {idx}: {coords_str}")
                    continue

                x1, y1, x2, y2 = coords_list[:4]

                # Normalize from 0-999 to 0-1 (official DeepSeek-OCR uses 0-999)
                # Then scale to image dimensions
                x1_norm = (x1 / 999.0) * image_width
                y1_norm = (y1 / 999.0) * image_height
                x2_norm = (x2 / 999.0) * image_width
                y2_norm = (y2 / 999.0) * image_height

                # Convert to pixel coordinates (integers)
                x1_px = int(x1_norm)
                y1_px = int(y1_norm)
                x2_px = int(x2_norm)
                y2_px = int(y2_norm)

                # Map label to 7-category
                element_type = self._map_label(label.strip().lower())

                # Extract text preview (first 50 chars of content after this ref/det)
                text_preview = self._extract_text_preview(markdown_text, idx)

                # Create ElementDetection
                detection = ElementDetection(
                    element_id=f"page_{page_num}_e{idx}",
                    element_type=element_type,
                    bbox=BoundingBox(
                        x1=x1_px,
                        y1=y1_px,
                        x2=x2_px,
                        y2=y2_px,
                        page=page_num,
                    ),
                    confidence=1.0,  # DeepSeek-OCR doesn't provide confidence
                    text_preview=text_preview,
                )

                elements.append(detection)

            except Exception as e:
                print(f"⚠️ Warning: Failed to parse element {idx} ({label}): {e}")
                continue

        return elements

    def _parse_coords_manual(self, coords_str: str) -> List[int]:
        """
        Manual coordinate parsing fallback.

        Args:
            coords_str: Coordinate string (e.g., "[100,200,800,600]")

        Returns:
            List of integers [x1, y1, x2, y2]
        """
        # Remove brackets and whitespace
        coords_str = coords_str.replace("[", "").replace("]", "").strip()

        # Split by comma
        coords = [int(x.strip()) for x in coords_str.split(",") if x.strip()]

        return coords

    def _map_label(self, label: str) -> ElementType:
        """
        Map official DeepSeek-OCR label to our 7-category ElementType.

        Args:
            label: Official label string (e.g., 'title', 'table', 'figure')

        Returns:
            ElementType enum value
        """
        # Direct mapping
        if label in self.LABEL_MAPPING:
            return self.LABEL_MAPPING[label]

        # Heuristic mapping for unknown labels
        if "title" in label or "header" in label or "heading" in label:
            return ElementType.TEXT_HEADER
        elif "section" in label:
            return ElementType.TEXT_SECTION
        elif "table" in label:
            return ElementType.TABLE
        elif "graph" in label or "chart" in label or "plot" in label:
            return ElementType.GRAPH
        elif "diagram" in label or "flow" in label:
            return ElementType.DIAGRAM
        elif "image" in label or "figure" in label or "photo" in label:
            # Default to complex_image for unknown visual elements
            return ElementType.COMPLEX_IMAGE
        else:
            # Default to paragraph for text
            return ElementType.TEXT_PARAGRAPH

    def _extract_text_preview(self, markdown_text: str, match_index: int) -> Optional[str]:
        """
        Extract text preview after the current ref/det tag.

        Args:
            markdown_text: Full markdown text
            match_index: Index of current match

        Returns:
            First 50 characters of content (or None)
        """
        try:
            # Find all matches
            matches = self.ref_det_pattern.finditer(markdown_text)

            # Get current match
            for idx, match in enumerate(matches):
                if idx == match_index:
                    # Content after current match
                    end_pos = match.end()

                    # Find next match (or end of text)
                    next_match = None
                    for next_idx, next_m in enumerate(self.ref_det_pattern.finditer(markdown_text)):
                        if next_idx == match_index + 1:
                            next_match = next_m
                            break

                    if next_match:
                        content = markdown_text[end_pos : next_match.start()]
                    else:
                        content = markdown_text[end_pos:]

                    # Clean and truncate
                    content = content.strip()
                    if len(content) > 50:
                        content = content[:47] + "..."

                    return content if content else None

            return None

        except Exception:
            return None

    def extract_images(
        self, markdown_text: str, page_image: Image.Image, page_num: int
    ) -> Tuple[List[Image.Image], List[ElementDetection]]:
        """
        Extract cropped images for all visual elements (table, graph, diagram, complex_image).

        Args:
            markdown_text: Markdown text with grounding tags
            page_image: Full page PIL Image
            page_num: Page number (1-indexed)

        Returns:
            (List of cropped images, List of corresponding ElementDetection)
        """
        # Parse all elements
        elements = self.parse(
            markdown_text, page_num, page_image.width, page_image.height
        )

        # Filter visual elements only
        visual_types = {
            ElementType.TABLE,
            ElementType.GRAPH,
            ElementType.DIAGRAM,
            ElementType.COMPLEX_IMAGE,
        }
        visual_elements = [e for e in elements if e.element_type in visual_types]

        # Crop images
        cropped_images = []
        for element in visual_elements:
            try:
                box = (
                    element.bbox.x1,
                    element.bbox.y1,
                    element.bbox.x2,
                    element.bbox.y2,
                )
                cropped = page_image.crop(box)
                cropped_images.append(cropped)
            except Exception as e:
                print(f"⚠️ Warning: Failed to crop {element.element_id}: {e}")
                # Use empty placeholder
                cropped_images.append(Image.new("RGB", (100, 100), color="white"))

        return cropped_images, visual_elements
