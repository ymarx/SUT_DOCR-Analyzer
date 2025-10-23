"""
Utility functions for DeepSeek-OCR processing.

Includes image processing, numbering parsing, and keyword extraction.
"""

import re
from pathlib import Path
from typing import Optional, List, Tuple
from collections import Counter
from PIL import Image

from .types import BoundingBox


def crop_bbox(image: Image.Image, bbox: BoundingBox) -> Image.Image:
    """
    Crop image using bounding box coordinates.

    Args:
        image: PIL Image
        bbox: BoundingBox with x1, y1, x2, y2 coordinates

    Returns:
        Cropped PIL Image
    """
    return image.crop((bbox.x1, bbox.y1, bbox.x2, bbox.y2))


def save_image(
    image: Image.Image,
    output_dir: str,
    image_id: str,
    element_type: str = "unknown",
) -> str:
    """
    Save cropped element image with unique ID.

    Args:
        image: PIL Image to save
        output_dir: Base output directory
        image_id: Unique identifier for the image
        element_type: Element type ('graph', 'table', 'diagram', 'complex_image')

    Returns:
        Path to saved image file

    Example:
        >>> save_image(img, "./outputs/cropped_images", "graph_p1_e2", "graph")
        './outputs/cropped_images/graph/graph_p1_e2.png'
    """
    output_path = Path(output_dir) / element_type / f"{image_id}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, "PNG")
    return str(output_path)


def parse_numbering(text: str) -> Optional[str]:
    """
    Parse section numbering from text.

    Detects patterns like:
    - '1.', '1.1.', '1.1.1.'
    - '1)', '1.1)', '1.1.1)'
    - '1 ', '1.1 ', '1.1.1 '

    Args:
        text: Text to parse

    Returns:
        Normalized numbering string (e.g., '1.1.1') or None if not found

    Examples:
        >>> parse_numbering("1. 목적")
        '1'
        >>> parse_numbering("1.1. 적용범위")
        '1.1'
        >>> parse_numbering("1.1.1 개요")
        '1.1.1'
        >>> parse_numbering("일반 텍스트")
        None
    """
    if not text:
        return None

    # Pattern: Matches '1.', '1.1.', '1.1.1.', '1)', '1.1)', etc.
    patterns = [
        r'^(\d+(?:\.\d+)*)\.',  # '1.', '1.1.', '1.1.1.'
        r'^(\d+(?:\.\d+)*)\)',  # '1)', '1.1)', '1.1.1)'
        r'^(\d+(?:\.\d+)*)\s',  # '1 ', '1.1 ', '1.1.1 '
    ]

    for pattern in patterns:
        match = re.match(pattern, text.strip())
        if match:
            return match.group(1)

    return None


def extract_keywords(
    text: str,
    max_keywords: int = 10,
    min_length: int = 2,
    korean_only: bool = True,
) -> List[str]:
    """
    Extract important keywords from text using frequency analysis.

    Simple TF-based extraction for Korean technical documents.

    Args:
        text: Text to extract keywords from
        max_keywords: Maximum number of keywords to return
        min_length: Minimum keyword length
        korean_only: Only extract Korean words (ignore English/numbers)

    Returns:
        List of keywords sorted by frequency

    Examples:
        >>> extract_keywords("노열 관리 기준. 노열은 중요한 지표입니다.", max_keywords=3)
        ['노열', '관리', '기준']
    """
    if not text:
        return []

    # Remove special characters, keep Korean, spaces, and optionally English
    if korean_only:
        cleaned = re.sub(r'[^\uAC00-\uD7A3\s]', ' ', text)
    else:
        cleaned = re.sub(r'[^\uAC00-\uD7A3a-zA-Z\s]', ' ', text)

    # Split into words
    words = cleaned.split()

    # Filter by length
    words = [w for w in words if len(w) >= min_length]

    # Common Korean stopwords (basic set)
    stopwords = {
        '및', '등', '것', '그', '이', '저', '수', '때', '내', '외',
        '또는', '그리고', '하는', '되는', '있는', '없는', '위한', '위해',
        '경우', '대한', '통해', '따라', '에서', '으로', '에게', '에',
        '를', '을', '가', '이', '은', '는', '의', '와', '과',
    }

    # Remove stopwords
    words = [w for w in words if w not in stopwords]

    # Count frequencies
    freq = Counter(words)

    # Get top keywords
    keywords = [word for word, _ in freq.most_common(max_keywords)]

    return keywords


def normalize_bbox(
    bbox: BoundingBox,
    image_width: int,
    image_height: int,
) -> BoundingBox:
    """
    Normalize bounding box coordinates to image dimensions.

    Args:
        bbox: BoundingBox with potentially out-of-bounds coordinates
        image_width: Image width
        image_height: Image height

    Returns:
        Normalized BoundingBox clamped to image bounds
    """
    return BoundingBox(
        x1=max(0, min(bbox.x1, image_width)),
        y1=max(0, min(bbox.y1, image_height)),
        x2=max(0, min(bbox.x2, image_width)),
        y2=max(0, min(bbox.y2, image_height)),
        page=bbox.page,
    )


def generate_element_id(
    element_type: str,
    page_num: int,
    element_index: int,
) -> str:
    """
    Generate unique element ID.

    Format: {type}_p{page}_e{index}

    Args:
        element_type: Element type ('graph', 'table', etc.)
        page_num: Page number (1-indexed)
        element_index: Element index on page (0-indexed)

    Returns:
        Unique element ID

    Examples:
        >>> generate_element_id("graph", 1, 0)
        'graph_p1_e0'
        >>> generate_element_id("table", 3, 2)
        'table_p3_e2'
    """
    return f"{element_type}_p{page_num}_e{element_index}"


def split_text_by_length(
    text: str,
    max_length: int = 512,
) -> List[str]:
    """
    Split long text into chunks for processing.

    Args:
        text: Text to split
        max_length: Maximum chunk length

    Returns:
        List of text chunks
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = ""

    for sentence in re.split(r'([.!?])', text):
        if len(current_chunk) + len(sentence) > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk += sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks
