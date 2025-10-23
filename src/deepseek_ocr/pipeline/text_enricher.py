"""
Text enricher for DocJSON generation.

Combines Pass 1 and Pass 2 results into structured DocJSON format.
"""

from typing import List, Dict, Optional
from pathlib import Path
import logging

from PIL import Image

from ..core.types import (
    PageStructure,
    ElementAnalysis,
    DocumentDocJSON,
    DocumentMetadata,
    ContentBlock,
    Section,
    ElementType,
    TextBlockData,
    GraphData,
    TableData,
    DiagramData,
    ComplexImageData,
)
from ..core.utils import parse_numbering, generate_element_id, save_image, crop_bbox
from ..core.config import Config

logger = logging.getLogger(__name__)


class TextEnricher:
    """
    Convert Pass 1 + Pass 2 results into DocJSON structure.

    Responsibilities:
    - Build section tree from numbering
    - Create ContentBlocks with type-specific data
    - Save element images with IDs
    - Generate final DocumentDocJSON
    """

    def __init__(self, config: Config):
        """
        Initialize text enricher.

        Args:
            config: Configuration with output paths
        """
        self.config = config

    def enrich(
        self,
        structures: List[PageStructure],
        analyses: Dict[str, ElementAnalysis],
        page_images: List[Image.Image],
        metadata: Optional[DocumentMetadata] = None,
    ) -> DocumentDocJSON:
        """
        Enrich structures and analyses into DocJSON.

        Args:
            structures: List of PageStructure from Pass 1
            analyses: Dict of ElementAnalysis from Pass 2 (key: element_id)
            page_images: List of page images (for cropping elements)
            metadata: Optional document metadata

        Returns:
            Complete DocumentDocJSON

        Example:
            >>> enricher = TextEnricher(config)
            >>> docjson = enricher.enrich(structures, analyses, page_images)
        """
        logger.info("Enriching document structure into DocJSON...")

        # Create content blocks
        blocks = []
        doc_index = 0

        for page_struct in structures:
            page_image = page_images[page_struct.page_num - 1]

            for element in page_struct.elements:
                analysis = analyses.get(element.element_id)

                if analysis is None:
                    logger.warning(f"No analysis found for {element.element_id}, skipping")
                    continue

                # Create ContentBlock
                block = self._create_content_block(
                    element=element,
                    analysis=analysis,
                    page_image=page_image,
                    doc_index=doc_index,
                )

                blocks.append(block)
                doc_index += 1

        # Build section tree
        sections = self._build_section_tree(blocks)

        # Create metadata if not provided
        if metadata is None:
            metadata = DocumentMetadata(
                page_count=len(structures),
            )

        # Generate DocJSON
        docjson = DocumentDocJSON(
            version="1.0.0",
            metadata=metadata,
            blocks=blocks,
            sections=sections,
        )

        logger.info(f"✅ Generated DocJSON with {len(blocks)} blocks and {len(sections)} sections")

        return docjson

    def _create_content_block(
        self,
        element,
        analysis: ElementAnalysis,
        page_image: Image.Image,
        doc_index: int,
    ) -> ContentBlock:
        """Create ContentBlock from element and analysis."""
        element_type = element.element_type

        # Base block
        block = ContentBlock(
            id=element.element_id,
            type=element_type,
            doc_index=doc_index,
            page=element.bbox.page,
            bbox=element.bbox,
        )

        # Extract text from items (first item usually contains the main text)
        if analysis.items:
            block.text = analysis.items[0] if len(analysis.items) > 0 else None

        # Type-specific data
        if element_type in [ElementType.TEXT_HEADER, ElementType.TEXT_SECTION, ElementType.TEXT_PARAGRAPH]:
            block.text_data = TextBlockData(
                numbering=parse_numbering(block.text) if block.text else None,
                keywords=analysis.keywords,
                summary=analysis.summary,
            )
            # For sections, set level based on numbering depth
            if element_type == ElementType.TEXT_SECTION and block.text_data.numbering:
                block.level = block.text_data.numbering.count('.') + 1

        elif element_type == ElementType.TABLE:
            # Save table image
            image_id = generate_element_id("table", element.bbox.page, doc_index)
            if self.config.save_images:
                cropped = crop_bbox(page_image, element.bbox)
                save_image(cropped, self.config.image_output_dir, image_id, "table")

            # Extract table data from structured_data
            table_info = analysis.structured_data or {}
            block.table = TableData(
                doc_index=doc_index,
                rows=0,  # TODO: parse from structured_data
                cols=0,  # TODO: parse from structured_data
                data=[],  # TODO: parse from structured_data
                markdown=table_info.get("markdown"),
                keywords=analysis.keywords,
                summary=analysis.summary,
                image_id=image_id,
                is_complex=(table_info.get("complexity") == "complex"),
            )

        elif element_type == ElementType.GRAPH:
            # Save graph image
            image_id = generate_element_id("graph", element.bbox.page, doc_index)
            if self.config.save_images:
                cropped = crop_bbox(page_image, element.bbox)
                save_image(cropped, self.config.image_output_dir, image_id, "graph")

            # Extract graph data
            graph_info = analysis.structured_data.get("graph_data", {}) if analysis.structured_data else {}
            block.graph = GraphData(
                title=graph_info.get("title"),
                graph_type=graph_info.get("graph_type", "unknown"),
                x_axis=graph_info.get("x_axis", {}),
                y_axis=graph_info.get("y_axis", {}),
                legend=graph_info.get("legend", []),
                data_trends=graph_info.get("trends", []),
                keywords=analysis.keywords,
                summary=analysis.summary,
                image_id=image_id,
            )

        elif element_type == ElementType.DIAGRAM:
            # Save diagram image
            image_id = generate_element_id("diagram", element.bbox.page, doc_index)
            if self.config.save_images:
                cropped = crop_bbox(page_image, element.bbox)
                save_image(cropped, self.config.image_output_dir, image_id, "diagram")

            # Extract diagram data
            diagram_info = analysis.structured_data.get("diagram_data", {}) if analysis.structured_data else {}
            block.diagram = DiagramData(
                id=element.element_id,
                doc_index=doc_index,
                diagram_type=diagram_info.get("diagram_type", "unknown"),
                components=diagram_info.get("components", []),
                connections=diagram_info.get("connections", []),
                mermaid=diagram_info.get("mermaid"),
                keywords=analysis.keywords,
                summary=analysis.summary,
                image_id=image_id,
                is_complex=(diagram_info.get("complexity") == "complex"),
                bbox=element.bbox.to_dict(),
            )

        elif element_type == ElementType.COMPLEX_IMAGE:
            # Save complex image
            image_id = generate_element_id("complex_image", element.bbox.page, doc_index)
            if self.config.save_images:
                cropped = crop_bbox(page_image, element.bbox)
                save_image(cropped, self.config.image_output_dir, image_id, "complex_image")

            # Extract complexity data
            complexity_info = analysis.structured_data.get("complexity_data", {}) if analysis.structured_data else {}
            block.complex_image = ComplexImageData(
                underlying_type=complexity_info.get("underlying_type", "unknown"),
                visible_text=complexity_info.get("visible_text"),
                keywords=analysis.keywords,
                complexity_reasons=complexity_info.get("complexity_reasons", []),
                summary=analysis.summary,
                image_id=image_id,
            )

        return block

    def _build_section_tree(self, blocks: List[ContentBlock]) -> List[Section]:
        """
        Build hierarchical section tree from text blocks with numbering.

        Args:
            blocks: List of ContentBlocks

        Returns:
            List of root-level Section objects
        """
        sections = []
        section_stack = []  # Stack to track current section hierarchy

        for block in blocks:
            # Only process section headings
            if block.type != ElementType.TEXT_SECTION or not block.text_data or not block.text_data.numbering:
                continue

            numbering = block.text_data.numbering
            level = numbering.count('.') + 1
            title = block.text or ""

            # Create section
            section = Section(
                id=f"sec_{block.id}",
                number=numbering,
                title=title,
                level=level,
                doc_index=block.doc_index,
                heading_block_id=block.id,
            )

            # Build hierarchy
            # Pop sections from stack until we find the parent level
            while section_stack and section_stack[-1].level >= level:
                section_stack.pop()

            # Add to parent or root
            if section_stack:
                section_stack[-1].subsections.append(section)
            else:
                sections.append(section)

            # Push to stack
            section_stack.append(section)

        # Assign blocks to sections (simplified - assign to nearest preceding section)
        current_section = None
        for block in blocks:
            if block.type == ElementType.TEXT_SECTION and block.text_data and block.text_data.numbering:
                # Find corresponding section
                for sec in self._flatten_sections(sections):
                    if sec.heading_block_id == block.id:
                        current_section = sec
                        break

            if current_section:
                current_section.blocks.append(block)
                current_section.block_ids.append(block.id)

        return sections

    def _flatten_sections(self, sections: List[Section]) -> List[Section]:
        """Flatten section tree into list."""
        result = []
        for section in sections:
            result.append(section)
            result.extend(self._flatten_sections(section.subsections))
        return result
