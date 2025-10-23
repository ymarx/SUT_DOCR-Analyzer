"""
Integration test for DeepSeek-OCR pipeline.

Tests the complete 2-Pass pipeline from PDF to DocJSON.

Usage:
    # CPU test (structure validation only)
    python tests/test_integration.py --cpu

    # GPU test (full pipeline)
    python tests/test_integration.py --gpu --pdf "TP-030-030-030 노열관리 및 보상기준.pdf"
"""

import sys
import json
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from deepseek_ocr.core.config import Config
from deepseek_ocr.core.types import ElementType
from deepseek_ocr.engine.deepseek_engine import DeepSeekEngine
from deepseek_ocr.pipeline.pdf_parser import PDFParser
from deepseek_ocr.pipeline.structure_analyzer import PageStructureAnalyzer
from deepseek_ocr.pipeline.element_analyzer import ElementAnalyzer
from deepseek_ocr.pipeline.text_enricher import TextEnricher


def test_pdf_parsing(pdf_path: Path):
    """Test PDF parsing."""
    print("\n" + "="*70)
    print("TEST 1: PDF Parsing")
    print("="*70)

    parser = PDFParser(dpi=200)
    pages = parser.parse(pdf_path)

    assert len(pages) > 0, "No pages parsed"
    assert pages[0].image is not None, "No image in first page"

    print(f"✅ Parsed {len(pages)} pages")
    print(f"   Page 1 size: {pages[0].width}x{pages[0].height}")
    print(f"   Text layer length: {len(pages[0].text_layer)} chars")

    return pages


def test_structure_analysis(engine: DeepSeekEngine, pages):
    """Test Pass 1: Structure analysis."""
    print("\n" + "="*70)
    print("TEST 2: Pass 1 - Structure Analysis")
    print("="*70)

    analyzer = PageStructureAnalyzer(engine)

    # Test first page only
    structure = analyzer.analyze(pages[0].image, page_num=1)

    assert structure.page_num == 1, "Wrong page number"
    assert len(structure.elements) > 0, "No elements detected"

    print(f"✅ Detected {len(structure.elements)} elements on page 1")

    # Print element types
    type_counts = {}
    for elem in structure.elements:
        elem_type = elem.element_type.value
        type_counts[elem_type] = type_counts.get(elem_type, 0) + 1

    print("\n   Element breakdown:")
    for elem_type, count in sorted(type_counts.items()):
        print(f"   - {elem_type}: {count}")

    return [structure]


def test_element_analysis(engine: DeepSeekEngine, structures, pages):
    """Test Pass 2: Element analysis."""
    print("\n" + "="*70)
    print("TEST 3: Pass 2 - Element Analysis")
    print("="*70)

    analyzer = ElementAnalyzer(engine)
    analyses = {}

    # Test first 3 elements only (for speed)
    structure = structures[0]
    page_image = pages[0].image
    test_elements = structure.elements[:3]

    print(f"Testing {len(test_elements)} elements (out of {len(structure.elements)})...")

    for idx, element in enumerate(test_elements, 1):
        print(f"\n   [{idx}/{len(test_elements)}] {element.element_id} ({element.element_type.value})")

        analysis = analyzer.analyze(element, page_image, structure.elements)
        analyses[element.element_id] = analysis

        # Validate analysis
        assert analysis.element_id == element.element_id, "ID mismatch"
        assert analysis.element_type == element.element_type, "Type mismatch"

        print(f"      Items: {len(analysis.items)}")
        print(f"      Keywords: {analysis.keywords[:5] if len(analysis.keywords) > 5 else analysis.keywords}")
        print(f"      Summary: {analysis.summary[:100] if analysis.summary else 'None'}...")

    print(f"\n✅ Analyzed {len(analyses)} elements successfully")

    return analyses


def test_docjson_generation(config: Config, structures, analyses, pages):
    """Test DocJSON generation."""
    print("\n" + "="*70)
    print("TEST 4: DocJSON Generation")
    print("="*70)

    enricher = TextEnricher(config)
    page_images = [p.image for p in pages]

    docjson = enricher.enrich(structures, analyses, page_images)

    # Validate DocJSON
    assert docjson.version == "1.0.0", "Wrong version"
    assert docjson.metadata is not None, "No metadata"
    assert len(docjson.blocks) > 0, "No blocks"

    print(f"✅ Generated DocJSON")
    print(f"   Blocks: {len(docjson.blocks)}")
    print(f"   Sections: {len(docjson.sections)}")

    # Sample block
    if docjson.blocks:
        sample = docjson.blocks[0]
        print(f"\n   Sample block:")
        print(f"   - ID: {sample.id}")
        print(f"   - Type: {sample.type}")
        print(f"   - Text: {sample.text[:50] if sample.text else 'None'}...")

    return docjson


def test_output_saving(config: Config, docjson):
    """Test output file saving."""
    print("\n" + "="*70)
    print("TEST 5: Output Saving")
    print("="*70)

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "test_output.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(docjson.to_dict(), f, ensure_ascii=False, indent=2)

    assert output_file.exists(), "Output file not created"

    file_size = output_file.stat().st_size
    print(f"✅ Saved to: {output_file}")
    print(f"   File size: {file_size / 1024:.1f} KB")

    # Validate JSON is loadable
    with open(output_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert "version" in loaded, "Invalid JSON structure"
    print(f"   JSON structure: ✅ Valid")


def main():
    parser = argparse.ArgumentParser(description="DeepSeek-OCR Integration Test")
    parser.add_argument(
        "--pdf",
        default="TP-030-030-030 노열관리 및 보상기준.pdf",
        help="PDF file to test",
    )
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="Run on CPU (structure validation only, no GPU inference)",
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Run on GPU (full pipeline test)",
    )
    parser.add_argument(
        "--output",
        default="./test_outputs",
        help="Output directory",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.cpu and not args.gpu:
        print("❌ Error: Specify either --cpu or --gpu")
        return 1

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"❌ Error: PDF not found: {pdf_path}")
        return 1

    print("\n" + "="*70)
    print("DeepSeek-OCR Integration Test")
    print("="*70)
    print(f"PDF: {pdf_path.name}")
    print(f"Mode: {'CPU (structure only)' if args.cpu else 'GPU (full pipeline)'}")
    print("="*70)

    try:
        # Test 1: PDF Parsing
        pages = test_pdf_parsing(pdf_path)

        if args.cpu:
            print("\n" + "="*70)
            print("✅ CPU Test Complete")
            print("="*70)
            print("Structure validation passed. PDF parsing works correctly.")
            print("To test full pipeline, run with --gpu on GPU hardware.")
            return 0

        # GPU tests
        config = Config(
            device="cuda",
            dtype="float16",
            output_dir=args.output,
        )
        config.validate()

        # Initialize engine
        print("\n" + "="*70)
        print("Initializing DeepSeek-OCR Engine...")
        print("="*70)
        engine = DeepSeekEngine(config)

        # Test 2: Structure Analysis
        structures = test_structure_analysis(engine, pages)

        # Test 3: Element Analysis
        analyses = test_element_analysis(engine, structures, pages)

        # Test 4: DocJSON Generation
        docjson = test_docjson_generation(config, structures, analyses, pages)

        # Test 5: Output Saving
        test_output_saving(config, docjson)

        # Cleanup
        engine.unload()

        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print(f"Full pipeline tested successfully on {pdf_path.name}")
        print(f"Output saved to: {args.output}")

        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
