"""
Text Preview Quality Test - Pass 2 문맥 품질 검증

Pass 1의 text_preview가 Pass 2에서 문맥으로 사용하기 충분한지 확인합니다.

Usage:
    python tests/test_text_preview.py --pdf sample.pdf --page 1
    python tests/test_text_preview.py --image sample.jpg
"""

import re
import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from deepseek_ocr.core.config import Config
from deepseek_ocr.engine.deepseek_vllm_engine import DeepSeekVLLMEngine
from deepseek_ocr.pipeline.pdf_parser import PDFParser
from deepseek_ocr.pipeline.markdown_parser import MarkdownGroundingParser


def analyze_text_preview_quality(
    markdown_text: str,
    image_width: int,
    image_height: int,
) -> dict:
    """
    Analyze quality of text previews extracted from markdown.

    Args:
        markdown_text: Raw markdown with grounding tags
        image_width: Image width
        image_height: Image height

    Returns:
        Quality analysis dict
    """
    # Parse markdown
    parser = MarkdownGroundingParser()
    elements = parser.parse(markdown_text, page_num=1, image_width=image_width, image_height=image_height)

    # Analyze text previews
    preview_stats = {
        'total_elements': len(elements),
        'with_preview': 0,
        'without_preview': 0,
        'preview_lengths': [],
        'avg_preview_length': 0,
        'min_preview_length': float('inf'),
        'max_preview_length': 0,
        'by_type': {},
    }

    for elem in elements:
        elem_type = elem.element_type.value

        # Initialize type stats
        if elem_type not in preview_stats['by_type']:
            preview_stats['by_type'][elem_type] = {
                'count': 0,
                'with_preview': 0,
                'avg_length': 0,
                'lengths': [],
            }

        preview_stats['by_type'][elem_type]['count'] += 1

        if elem.text_preview:
            preview_stats['with_preview'] += 1
            preview_stats['by_type'][elem_type]['with_preview'] += 1

            length = len(elem.text_preview)
            preview_stats['preview_lengths'].append(length)
            preview_stats['by_type'][elem_type]['lengths'].append(length)

            preview_stats['min_preview_length'] = min(preview_stats['min_preview_length'], length)
            preview_stats['max_preview_length'] = max(preview_stats['max_preview_length'], length)
        else:
            preview_stats['without_preview'] += 1

    # Calculate averages
    if preview_stats['preview_lengths']:
        preview_stats['avg_preview_length'] = sum(preview_stats['preview_lengths']) / len(preview_stats['preview_lengths'])

    for elem_type, stats in preview_stats['by_type'].items():
        if stats['lengths']:
            stats['avg_length'] = sum(stats['lengths']) / len(stats['lengths'])

    # Reset inf if no previews
    if preview_stats['min_preview_length'] == float('inf'):
        preview_stats['min_preview_length'] = 0

    return preview_stats, elements


def test_context_sufficiency(
    elements: List,
    page_image: Image.Image,
) -> dict:
    """
    Test if text previews provide sufficient context for Pass 2.

    Simulates _build_context() logic from element_analyzer_vllm.py

    Args:
        elements: List of ElementDetection objects
        page_image: Full page image

    Returns:
        Context quality analysis
    """
    from deepseek_ocr.core.types import ElementType

    context_stats = {
        'elements_tested': 0,
        'avg_context_length': 0,
        'min_context_length': float('inf'),
        'max_context_length': 0,
        'by_type': {},
    }

    text_types = {ElementType.TEXT_HEADER, ElementType.TEXT_SECTION, ElementType.TEXT_PARAGRAPH}
    context_radius = 0.2  # Same as ElementAnalyzerVLLM default

    page_height = page_image.height
    search_radius_px = page_height * context_radius

    context_lengths = []

    for target_elem in elements:
        # Skip text elements (they don't need context)
        if target_elem.element_type in text_types:
            continue

        context_stats['elements_tested'] += 1

        # Initialize type stats
        elem_type = target_elem.element_type.value
        if elem_type not in context_stats['by_type']:
            context_stats['by_type'][elem_type] = {
                'count': 0,
                'avg_context_length': 0,
                'lengths': [],
            }

        context_stats['by_type'][elem_type]['count'] += 1

        # Find nearby text elements
        target_center_y = (target_elem.bbox.y1 + target_elem.bbox.y2) / 2
        nearby_texts = []

        for elem in elements:
            if elem.element_type not in text_types:
                continue
            if elem.element_id == target_elem.element_id:
                continue

            elem_center_y = (elem.bbox.y1 + elem.bbox.y2) / 2
            distance = abs(elem_center_y - target_center_y)

            if distance <= search_radius_px and elem.text_preview:
                nearby_texts.append((distance, elem))

        # Build context
        nearby_texts.sort(key=lambda x: x[0])
        context_parts = []
        total_chars = 0
        max_chars = 500

        for _, elem in nearby_texts:
            text = f"[{elem.element_type.value}] {elem.text_preview}"
            if total_chars + len(text) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 20:
                    context_parts.append(text[:remaining] + "...")
                break
            else:
                context_parts.append(text)
                total_chars += len(text)

        context = "\n".join(context_parts)
        context_length = len(context)

        context_lengths.append(context_length)
        context_stats['by_type'][elem_type]['lengths'].append(context_length)

        context_stats['min_context_length'] = min(context_stats['min_context_length'], context_length)
        context_stats['max_context_length'] = max(context_stats['max_context_length'], context_length)

    # Calculate averages
    if context_lengths:
        context_stats['avg_context_length'] = sum(context_lengths) / len(context_lengths)

    for elem_type, stats in context_stats['by_type'].items():
        if stats['lengths']:
            stats['avg_context_length'] = sum(stats['lengths']) / len(stats['lengths'])

    # Reset inf if no contexts
    if context_stats['min_context_length'] == float('inf'):
        context_stats['min_context_length'] = 0

    return context_stats


def test_text_preview_quality(image_path: str, config: Config):
    """
    Test text preview quality on an image/PDF page.

    Args:
        image_path: Path to image file
        config: Config instance
    """
    print("\n" + "="*70)
    print(f"Text Preview Quality Test: {Path(image_path).name}")
    print("="*70)

    # Load image
    image = Image.open(image_path).convert("RGB")
    print(f"✅ Image loaded: {image.size}")

    # Initialize engine
    print("\nInitializing vLLM engine...")
    engine = DeepSeekVLLMEngine(config)

    try:
        # Run Pass 1
        print("\nRunning Pass 1: Structure analysis...")
        prompt = "<image>\n<|grounding|>Convert the document to markdown."
        response = engine.infer(image, prompt)
        print(f"✅ Response received ({len(response)} chars)")

        # Analyze text preview quality
        print("\nAnalyzing text preview quality...")
        preview_stats, elements = analyze_text_preview_quality(
            response, image.width, image.height
        )

        # Test context sufficiency
        print("Testing context sufficiency for Pass 2...")
        context_stats = test_context_sufficiency(elements, image)

        # Show results
        print("\n" + "="*70)
        print("TEXT PREVIEW QUALITY RESULTS")
        print("="*70)

        print(f"\n📊 Overall Statistics:")
        print(f"  • Total elements: {preview_stats['total_elements']}")
        print(f"  • With text preview: {preview_stats['with_preview']} ({preview_stats['with_preview']/max(preview_stats['total_elements'],1)*100:.1f}%)")
        print(f"  • Without text preview: {preview_stats['without_preview']} ({preview_stats['without_preview']/max(preview_stats['total_elements'],1)*100:.1f}%)")

        if preview_stats['preview_lengths']:
            print(f"\n📏 Preview Length Statistics:")
            print(f"  • Average: {preview_stats['avg_preview_length']:.1f} chars")
            print(f"  • Min: {preview_stats['min_preview_length']} chars")
            print(f"  • Max: {preview_stats['max_preview_length']} chars")

        print(f"\n📋 By Element Type:")
        for elem_type, stats in sorted(preview_stats['by_type'].items()):
            coverage = stats['with_preview'] / max(stats['count'], 1) * 100
            avg_len = stats['avg_length'] if stats['avg_length'] > 0 else 0
            print(f"  • {elem_type}:")
            print(f"    - Count: {stats['count']}")
            print(f"    - Coverage: {stats['with_preview']}/{stats['count']} ({coverage:.1f}%)")
            if avg_len > 0:
                print(f"    - Avg length: {avg_len:.1f} chars")

        # Context quality
        print("\n" + "="*70)
        print("CONTEXT QUALITY FOR PASS 2")
        print("="*70)

        print(f"\n📊 Context Statistics:")
        print(f"  • Elements needing context: {context_stats['elements_tested']}")
        if context_stats['elements_tested'] > 0:
            print(f"  • Average context length: {context_stats['avg_context_length']:.1f} chars")
            print(f"  • Min context length: {context_stats['min_context_length']} chars")
            print(f"  • Max context length: {context_stats['max_context_length']} chars")

        print(f"\n📋 Context Quality by Type:")
        for elem_type, stats in sorted(context_stats['by_type'].items()):
            avg_len = stats['avg_context_length']
            print(f"  • {elem_type}:")
            print(f"    - Count: {stats['count']}")
            print(f"    - Avg context: {avg_len:.1f} chars")

        # Assessment
        print("\n" + "="*70)
        print("ASSESSMENT")
        print("="*70)

        # Check preview coverage
        preview_coverage = preview_stats['with_preview'] / max(preview_stats['total_elements'], 1)
        if preview_coverage >= 0.7:
            print("\n✅ Text preview coverage: GOOD (≥70%)")
        elif preview_coverage >= 0.5:
            print("\n⚠️  Text preview coverage: MODERATE (50-70%)")
        else:
            print("\n❌ Text preview coverage: LOW (<50%)")

        # Check preview length
        if preview_stats['avg_preview_length'] >= 30:
            print("✅ Average preview length: GOOD (≥30 chars)")
        elif preview_stats['avg_preview_length'] >= 15:
            print("⚠️  Average preview length: MODERATE (15-30 chars)")
        else:
            print("❌ Average preview length: LOW (<15 chars)")

        # Check context quality
        if context_stats['avg_context_length'] >= 100:
            print("✅ Average context length: GOOD (≥100 chars)")
        elif context_stats['avg_context_length'] >= 50:
            print("⚠️  Average context length: MODERATE (50-100 chars)")
        else:
            print("❌ Average context length: LOW (<50 chars)")

        # Recommendations
        print("\n💡 Recommendations:")
        if preview_coverage < 0.7:
            print("  • Consider improving text_preview extraction in markdown_parser.py")
        if preview_stats['avg_preview_length'] < 30:
            print("  • Consider increasing text_preview length (currently ~50 chars max)")
        if context_stats['avg_context_length'] < 100:
            print("  • May need to increase context_radius or max_chars for context")
        if preview_coverage >= 0.7 and preview_stats['avg_preview_length'] >= 30 and context_stats['avg_context_length'] >= 100:
            print("  ✅ Text preview quality is sufficient for Pass 2!")

    finally:
        engine.unload()


def main():
    parser = argparse.ArgumentParser(description="Test text preview quality")
    parser.add_argument("--image", type=str, help="Path to image file")
    parser.add_argument("--pdf", type=str, help="Path to PDF file")
    parser.add_argument("--page", type=int, default=1, help="PDF page number (1-indexed)")
    parser.add_argument("--preset", type=str, default="rtx4090",
                       choices=["rtx4060", "rtx4090", "cpu"],
                       help="Hardware preset")

    args = parser.parse_args()

    if not args.image and not args.pdf:
        parser.error("Must provide --image or --pdf")

    # Load config
    from deepseek_ocr.core.config import load_config
    config = load_config(preset=args.preset)

    print("\n" + "="*70)
    print("Text Preview Quality Test")
    print("="*70)
    print(f"Hardware preset: {args.preset}")

    # Get image path
    if args.image:
        image_path = args.image
    elif args.pdf:
        # Parse PDF to get page image
        parser_obj = PDFParser(dpi=config.pdf_dpi)
        pages = parser_obj.parse(args.pdf)

        if args.page < 1 or args.page > len(pages):
            print(f"❌ Invalid page number: {args.page} (PDF has {len(pages)} pages)")
            return

        page = pages[args.page - 1]
        image_path = page.image
        print(f"✅ PDF parsed: {len(pages)} pages, testing page {args.page}")

    test_text_preview_quality(image_path, config)


if __name__ == "__main__":
    main()
