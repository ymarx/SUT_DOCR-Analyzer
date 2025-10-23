"""
DeepSeek-OCR CLI interface.

Usage:
    python -m deepseek_ocr.cli.main process --pdf document.pdf --output outputs/
"""

import argparse
import json
import time
import logging
from pathlib import Path
from typing import Dict

from ..core.config import Config, load_config
from ..engine.deepseek_engine import DeepSeekEngine
from ..pipeline.pdf_parser import PDFParser
from ..pipeline.structure_analyzer import PageStructureAnalyzer
from ..pipeline.element_analyzer import ElementAnalyzer
from ..pipeline.text_enricher import TextEnricher

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_document(pdf_path: str, config: Config) -> None:
    """
    Process PDF document through 2-Pass pipeline.

    Args:
        pdf_path: Path to PDF file
        config: Configuration
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("="*70)
    logger.info(f"Processing: {pdf_path.name}")
    logger.info(f"Device: {config.device} | Dtype: {config.dtype}")
    logger.info("="*70)

    start_time = time.time()

    # Step 1: Parse PDF
    logger.info("\n[Step 1/5] Parsing PDF...")
    parser = PDFParser(dpi=config.pdf_dpi)
    pages = parser.parse(pdf_path)
    logger.info(f"✅ Parsed {len(pages)} pages")

    # Step 2: Initialize engine
    logger.info("\n[Step 2/5] Loading DeepSeek-OCR model...")
    engine = DeepSeekEngine(config)
    logger.info("✅ Engine initialized")

    # Step 3: Pass 1 - Structure analysis
    logger.info("\n[Step 3/5] Pass 1: Analyzing page structures...")
    structure_analyzer = PageStructureAnalyzer(engine)
    structures = []

    for page in pages:
        structure = structure_analyzer.analyze(page.image, page.page_number)
        structures.append(structure)

    total_elements = sum(len(s.elements) for s in structures)
    logger.info(f"✅ Pass 1 complete: {total_elements} elements detected across {len(pages)} pages")

    # Step 4: Pass 2 - Element analysis
    logger.info("\n[Step 4/5] Pass 2: Analyzing elements in detail...")
    element_analyzer = ElementAnalyzer(engine)
    analyses = {}

    elem_count = 0
    for page_idx, structure in enumerate(structures):
        page_image = pages[page_idx].image

        for element in structure.elements:
            elem_count += 1
            logger.info(f"  [{elem_count}/{total_elements}] {element.element_id} ({element.element_type.value})")

            analysis = element_analyzer.analyze(element, page_image, structure.elements)
            analyses[element.element_id] = analysis

    logger.info(f"✅ Pass 2 complete: {len(analyses)} elements analyzed")

    # Step 5: Generate DocJSON
    logger.info("\n[Step 5/5] Generating DocJSON...")
    enricher = TextEnricher(config)
    page_images = [p.image for p in pages]
    docjson = enricher.enrich(structures, analyses, page_images)

    # Save results
    output_file = output_dir / f"{pdf_path.stem}_docjson.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(docjson.to_dict(), f, ensure_ascii=False, indent=2)

    logger.info(f"✅ DocJSON saved to: {output_file}")

    # Summary
    elapsed = time.time() - start_time
    logger.info("\n" + "="*70)
    logger.info("Processing complete!")
    logger.info(f"Total time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    logger.info(f"Pages: {len(pages)}")
    logger.info(f"Elements: {len(analyses)}")
    logger.info(f"Blocks: {len(docjson.blocks)}")
    logger.info(f"Sections: {len(docjson.sections)}")
    logger.info(f"Output: {output_file}")
    logger.info("="*70)

    # Cleanup
    engine.unload()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="DeepSeek-OCR Document Processing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Process command
    process_parser = subparsers.add_parser("process", help="Process PDF document")
    process_parser.add_argument(
        "--pdf",
        required=True,
        help="Path to PDF file",
    )
    process_parser.add_argument(
        "--output",
        default="./outputs",
        help="Output directory (default: ./outputs)",
    )
    process_parser.add_argument(
        "--config",
        help="Path to config YAML file",
    )
    process_parser.add_argument(
        "--preset",
        choices=["rtx4060", "rtx4090", "cpu"],
        help="Use preset configuration",
    )
    process_parser.add_argument(
        "--device",
        choices=["cuda", "cpu"],
        help="Override device (cuda/cpu)",
    )
    process_parser.add_argument(
        "--dtype",
        choices=["float16", "float32", "bfloat16"],
        help="Override dtype",
    )

    args = parser.parse_args()

    if args.command == "process":
        # Load configuration
        if args.config:
            config = load_config(path=args.config)
        elif args.preset:
            config = load_config(preset=args.preset)
        else:
            config = Config()  # Default

        # Override settings
        if args.output:
            config.output_dir = args.output
            config.image_output_dir = str(Path(args.output) / "cropped_images")

        if args.device:
            config.device = args.device

        if args.dtype:
            config.dtype = args.dtype

        # Validate config
        config.validate()

        # Process document
        process_document(args.pdf, config)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
