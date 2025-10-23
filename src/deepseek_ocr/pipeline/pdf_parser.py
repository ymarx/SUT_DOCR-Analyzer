"""
PDF parsing module for DeepSeek-OCR pipeline.

Converts PDF pages to images for OCR processing.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List
import logging

import fitz  # PyMuPDF
from pdf2image import convert_from_path
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class PDFPage:
    """PDF page information with image."""
    page_number: int
    image: Image.Image
    text_layer: str
    width: int
    height: int
    dpi: int


class PDFParser:
    """
    PDF document parser.

    Converts PDF pages to images at specified DPI for DeepSeek-OCR processing.
    Also extracts text layer (if available) for context.
    """

    def __init__(
        self,
        dpi: int = 200,
        image_format: str = "PNG",
        extract_text: bool = True,
    ):
        """
        Initialize PDF parser.

        Args:
            dpi: PDF to image conversion resolution (200-300 recommended)
            image_format: Image format ('PNG' or 'JPEG')
            extract_text: Extract text layer for context (True recommended)
        """
        self.dpi = dpi
        self.image_format = image_format
        self.extract_text = extract_text

    def parse(self, pdf_path: Path | str) -> List[PDFPage]:
        """
        Parse PDF file into page images.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of PDFPage objects with images

        Raises:
            FileNotFoundError: If PDF file doesn't exist
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        logger.info(f"Parsing PDF: {pdf_path.name} (DPI={self.dpi})")

        # Convert PDF to images
        images = convert_from_path(
            pdf_path,
            dpi=self.dpi,
            fmt=self.image_format.lower(),
        )

        # Extract text layers (for context, not for OCR)
        text_layers = self._extract_text_layers(pdf_path) if self.extract_text else []

        # Create PDFPage objects
        pages = []
        for idx, image in enumerate(images):
            page = PDFPage(
                page_number=idx + 1,
                image=image,
                text_layer=text_layers[idx] if idx < len(text_layers) else "",
                width=image.width,
                height=image.height,
                dpi=self.dpi,
            )
            pages.append(page)

        logger.info(f"✅ Parsed {len(pages)} pages from {pdf_path.name}")
        return pages

    def _extract_text_layers(self, pdf_path: Path) -> List[str]:
        """
        Extract text layer using PyMuPDF.

        Note: For scanned documents, this will return empty strings.
        Text layer is used for context, not as primary OCR source.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of text strings (one per page)
        """
        text_layers = []

        try:
            doc = fitz.open(pdf_path)

            for page in doc:
                text = page.get_text("text")
                text_layers.append(text.strip())

            doc.close()

        except Exception as e:
            logger.warning(f"Failed to extract text layers: {e}")
            # Return empty strings for all pages
            text_layers = [""] * len(convert_from_path(pdf_path, dpi=72))

        return text_layers
