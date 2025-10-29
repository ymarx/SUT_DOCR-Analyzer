"""
Label Detection Test - 공식 vLLM이 사용하는 label 검증

이 테스트는 vLLM nightly 마이그레이션 전에 실행하여
공식 DeepSeek-OCR가 어떤 label을 사용하는지 확인합니다.

Usage:
    python tests/test_label_detection.py --image sample.jpg
    python tests/test_label_detection.py --pdf sample.pdf --page 1
"""

import re
import sys
import argparse
from pathlib import Path
from collections import Counter
from typing import List, Tuple, Dict
from PIL import Image

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from deepseek_ocr.core.config import Config
from deepseek_ocr.engine.deepseek_vllm_engine import DeepSeekVLLMEngine
from deepseek_ocr.pipeline.pdf_parser import PDFParser


def extract_labels_from_markdown(markdown_text: str) -> List[Tuple[str, str]]:
    """
    Extract all <|ref|> labels and their bounding boxes from markdown.

    Args:
        markdown_text: Raw markdown with grounding tags

    Returns:
        List of (label, bbox_str) tuples
    """
    pattern = re.compile(r"<\|ref\|>(.*?)<\|/ref\|><\|det\|>(.*?)<\|/det\|>", re.DOTALL)
    matches = pattern.findall(markdown_text)

    return [(label.strip(), bbox.strip()) for label, bbox in matches]


def analyze_labels(labels: List[str]) -> Dict[str, any]:
    """
    Analyze label distribution and patterns.

    Args:
        labels: List of label strings

    Returns:
        Analysis dictionary
    """
    label_counter = Counter(labels)

    # Known labels from our mapping
    known_labels = {
        "title", "heading", "section-header", "section_header",
        "text", "paragraph",
        "table", "graph", "chart", "plot",
        "figure", "diagram", "flowchart",
        "image", "photo", "picture"
    }

    unknown_labels = set(labels) - known_labels

    return {
        "total_elements": len(labels),
        "unique_labels": len(label_counter),
        "label_distribution": dict(label_counter.most_common()),
        "known_labels": {k: v for k, v in label_counter.items() if k in known_labels},
        "unknown_labels": {k: v for k, v in label_counter.items() if k in unknown_labels},
    }


def test_single_image(image_path: str, config: Config):
    """
    Test label detection on a single image.

    Args:
        image_path: Path to image file
        config: Config instance
    """
    print("\n" + "="*70)
    print(f"Label Detection Test: {Path(image_path).name}")
    print("="*70)

    # Load image
    image = Image.open(image_path).convert("RGB")
    print(f"✅ Image loaded: {image.size}")

    # Initialize engine
    print("\nInitializing vLLM engine...")
    engine = DeepSeekVLLMEngine(config)

    # Run Pass 1 (structure analysis)
    print("\nRunning Pass 1: Structure analysis with <|grounding|>...")
    prompt = "<image>\n<|grounding|>Convert the document to markdown."

    try:
        response = engine.infer(image, prompt)
        print(f"✅ Response received ({len(response)} chars)")

        # Extract labels
        label_bbox_pairs = extract_labels_from_markdown(response)
        labels = [label for label, _ in label_bbox_pairs]

        print(f"\n📊 Detected {len(labels)} elements")

        # Show raw output sample
        print("\n" + "-"*70)
        print("Raw Output Sample (first 500 chars):")
        print("-"*70)
        print(response[:500])
        if len(response) > 500:
            print(f"... ({len(response) - 500} more chars)")

        # Show detected labels
        print("\n" + "-"*70)
        print("Detected Labels with Bounding Boxes:")
        print("-"*70)
        for i, (label, bbox) in enumerate(label_bbox_pairs[:10]):  # First 10
            print(f"{i+1}. <|ref|>{label}<|/ref|><|det|>{bbox}<|/det|>")
        if len(label_bbox_pairs) > 10:
            print(f"... and {len(label_bbox_pairs) - 10} more elements")

        # Analyze labels
        analysis = analyze_labels(labels)

        print("\n" + "="*70)
        print("LABEL ANALYSIS RESULTS")
        print("="*70)

        print(f"\n📌 Total elements detected: {analysis['total_elements']}")
        print(f"📌 Unique label types: {analysis['unique_labels']}")

        print("\n🔵 Label Distribution:")
        for label, count in sorted(analysis['label_distribution'].items(), key=lambda x: -x[1]):
            print(f"  • {label}: {count} occurrences")

        if analysis['known_labels']:
            print("\n✅ Known Labels (in our LABEL_MAPPING):")
            for label, count in sorted(analysis['known_labels'].items(), key=lambda x: -x[1]):
                print(f"  • {label}: {count}")

        if analysis['unknown_labels']:
            print("\n⚠️  UNKNOWN Labels (NOT in our LABEL_MAPPING):")
            for label, count in sorted(analysis['unknown_labels'].items(), key=lambda x: -x[1]):
                print(f"  • {label}: {count} ← NEEDS MAPPING!")
        else:
            print("\n✅ All labels are known (no mapping updates needed)")

        # Special focus: figure labels
        figure_labels = [l for l in labels if 'figure' in l.lower() or 'fig' in l.lower()]
        if figure_labels:
            print(f"\n🔍 Figure-related labels found: {len(figure_labels)}")
            print(f"  Distribution: {Counter(figure_labels)}")

        return response, analysis

    except Exception as e:
        print(f"\n❌ Error during inference: {e}")
        import traceback
        traceback.print_exc()
        return None, None
    finally:
        engine.unload()


def test_pdf_page(pdf_path: str, page_num: int, config: Config):
    """
    Test label detection on a PDF page.

    Args:
        pdf_path: Path to PDF file
        page_num: Page number (1-indexed)
        config: Config instance
    """
    print("\n" + "="*70)
    print(f"Label Detection Test: {Path(pdf_path).name} - Page {page_num}")
    print("="*70)

    # Parse PDF
    parser = PDFParser(dpi=config.pdf_dpi)
    pages = parser.parse(pdf_path)

    if page_num < 1 or page_num > len(pages):
        print(f"❌ Invalid page number: {page_num} (PDF has {len(pages)} pages)")
        return None, None

    page = pages[page_num - 1]
    print(f"✅ PDF parsed: {len(pages)} pages, testing page {page_num}")

    # Test with page image
    return test_single_image(page.image, config)


def main():
    parser = argparse.ArgumentParser(description="Test official vLLM label detection")
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
    print("Official DeepSeek-OCR vLLM Label Detection Test")
    print("="*70)
    print(f"Hardware preset: {args.preset}")
    print(f"vLLM config: max_num_seqs={config.max_num_seqs}, "
          f"gpu_util={config.gpu_memory_utilization}")

    # Run test
    if args.image:
        response, analysis = test_single_image(args.image, config)
    elif args.pdf:
        response, analysis = test_pdf_page(args.pdf, args.page, config)

    if analysis:
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)

        if analysis['unknown_labels']:
            print("\n⚠️  ACTION REQUIRED:")
            print("  The following labels need to be added to LABEL_MAPPING:")
            print("  in src/deepseek_ocr/pipeline/markdown_parser.py")
            print()
            for label in sorted(analysis['unknown_labels'].keys()):
                print(f'  "{label}": ElementType.???  # TODO: Map to appropriate type')
        else:
            print("\n✅ SUCCESS: All labels are already mapped!")
            print("  No changes needed to LABEL_MAPPING")

        print("\n" + "="*70)


if __name__ == "__main__":
    main()
