"""
DeepSeek-OCR 간단한 사용 예제

단일 PDF 문서를 처리하는 기본 예제입니다.

Usage:
    python example_usage.py --pdf "document.pdf"
"""

import sys
import json
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from deepseek_ocr.core.config import Config
from deepseek_ocr.engine.deepseek_engine import DeepSeekEngine
from deepseek_ocr.pipeline.pdf_parser import PDFParser
from deepseek_ocr.pipeline.structure_analyzer import PageStructureAnalyzer
from deepseek_ocr.pipeline.element_analyzer import ElementAnalyzer
from deepseek_ocr.pipeline.text_enricher import TextEnricher


def main():
    parser = argparse.ArgumentParser(description="DeepSeek-OCR 간단한 예제")
    parser.add_argument("--pdf", required=True, help="PDF 파일 경로")
    parser.add_argument("--output", default="./example_output", help="출력 디렉토리")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"], help="실행 디바이스")

    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"❌ PDF 파일을 찾을 수 없습니다: {pdf_path}")
        return 1

    print("\n" + "="*70)
    print("DeepSeek-OCR 예제 실행")
    print("="*70)
    print(f"PDF: {pdf_path.name}")
    print(f"Device: {args.device}")
    print("="*70)

    # 1. 설정
    config = Config(
        device=args.device,
        dtype="float16" if args.device == "cuda" else "float32",
        output_dir=args.output,
    )
    config.validate()

    # 2. PDF 파싱
    print("\n[1/5] PDF 파싱...")
    parser = PDFParser(dpi=config.pdf_dpi)
    pages = parser.parse(pdf_path)
    print(f"✅ {len(pages)} 페이지 파싱 완료")

    # 3. 엔진 로드
    print("\n[2/5] DeepSeek-OCR 엔진 로드...")
    engine = DeepSeekEngine(config)
    print("✅ 엔진 로드 완료")

    # 4. Pass 1: 페이지 구조 분석
    print("\n[3/5] Pass 1: 페이지 구조 분석...")
    structure_analyzer = PageStructureAnalyzer(engine)
    structures = []

    for page in pages:
        print(f"  페이지 {page.page_number} 분석 중...")
        structure = structure_analyzer.analyze(page.image, page.page_number)
        structures.append(structure)

    total_elements = sum(len(s.elements) for s in structures)
    print(f"✅ {total_elements}개 요소 감지")

    # 5. Pass 2: 요소 상세 분석
    print("\n[4/5] Pass 2: 요소 상세 분석...")
    element_analyzer = ElementAnalyzer(engine)
    analyses = {}

    for page_idx, structure in enumerate(structures):
        page_image = pages[page_idx].image

        for elem_idx, element in enumerate(structure.elements):
            progress = (len(analyses) + 1) * 100 // total_elements
            print(f"  진행: {len(analyses)+1}/{total_elements} ({progress}%) - {element.element_type.value}")

            analysis = element_analyzer.analyze(element, page_image, structure.elements)
            analyses[element.element_id] = analysis

    print(f"✅ {len(analyses)}개 요소 분석 완료")

    # 6. DocJSON 생성
    print("\n[5/5] DocJSON 생성...")
    enricher = TextEnricher(config)
    page_images = [p.image for p in pages]
    docjson = enricher.enrich(structures, analyses, page_images)

    # 7. 결과 저장
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{pdf_path.stem}_docjson.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(docjson.to_dict(), f, ensure_ascii=False, indent=2)

    print(f"✅ DocJSON 저장: {output_file}")

    # 8. 요약 출력
    print("\n" + "="*70)
    print("처리 완료")
    print("="*70)
    print(f"📄 입력: {pdf_path.name}")
    print(f"📄 출력: {output_file}")
    print(f"📊 통계:")
    print(f"   - 페이지: {len(pages)}")
    print(f"   - 요소: {len(analyses)}")
    print(f"   - 블록: {len(docjson.blocks)}")
    print(f"   - 섹션: {len(docjson.sections)}")

    # 요소 타입별 통계
    type_counts = {}
    for block in docjson.blocks:
        block_type = block.type.value if hasattr(block.type, 'value') else str(block.type)
        type_counts[block_type] = type_counts.get(block_type, 0) + 1

    print(f"\n📑 요소 타입별 통계:")
    for elem_type, count in sorted(type_counts.items()):
        print(f"   - {elem_type}: {count}")

    # 저장된 이미지
    if config.save_images:
        image_dir = Path(config.image_output_dir)
        saved_images = list(image_dir.rglob("*.png"))
        print(f"\n🖼️  저장된 이미지: {len(saved_images)}개")
        print(f"   위치: {image_dir}")

    print("="*70)

    # 정리
    engine.unload()

    return 0


if __name__ == "__main__":
    sys.exit(main())
