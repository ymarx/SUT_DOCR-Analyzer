"""
RunPod 배치 처리 스크립트

여러 PDF 문서를 자동으로 처리합니다.

Usage:
    python runpod/process.py --input pdfs/ --output outputs/
    python runpod/process.py --input pdfs/ --preset rtx4090 --max-workers 2
"""

import sys
import argparse
import time
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from deepseek_ocr.core.config import Config, load_config
from deepseek_ocr.engine.deepseek_vllm_engine import DeepSeekVLLMEngine
from deepseek_ocr.pipeline.pdf_parser import PDFParser
from deepseek_ocr.pipeline.structure_analyzer_vllm import PageStructureAnalyzerVLLM
from deepseek_ocr.pipeline.element_analyzer_vllm import ElementAnalyzerVLLM
from deepseek_ocr.pipeline.text_enricher import TextEnricher


def process_single_pdf(
    pdf_path: Path,
    output_dir: Path,
    config: Config,
) -> Dict[str, Any]:
    """
    단일 PDF 처리

    Args:
        pdf_path: PDF 파일 경로
        output_dir: 출력 디렉토리
        config: 처리 설정

    Returns:
        처리 결과 딕셔너리
    """
    start_time = time.time()

    try:
        print(f"\n{'='*70}")
        print(f"처리 시작: {pdf_path.name}")
        print(f"{'='*70}")

        # PDF 파싱
        parser = PDFParser(dpi=config.pdf_dpi)
        pages = parser.parse(pdf_path)
        print(f"✅ PDF 파싱: {len(pages)} 페이지")

        # vLLM 엔진 초기화
        engine = DeepSeekVLLMEngine(config)

        # Pass 1: 배치 구조 분석
        print(f"\nPass 1: 페이지 구조 분석 (배치 모드)...")
        structure_analyzer = PageStructureAnalyzerVLLM(engine)

        # 배치 처리 (전체 페이지 동시 분석)
        page_images = [p.image for p in pages]
        page_nums = [p.page_number for p in pages]
        structures = structure_analyzer.analyze_batch(page_images, page_nums)

        total_elements = sum(len(s.elements) for s in structures)
        print(f"✅ Pass 1 완료: {total_elements}개 요소 감지")

        # Pass 2: 배치 요소 분석
        print(f"\nPass 2: 요소 상세 분석 (배치 모드)...")
        element_analyzer = ElementAnalyzerVLLM(engine)

        # 모든 요소 수집
        all_elements = []
        for structure in structures:
            all_elements.extend(structure.elements)

        # 배치 처리 (전체 요소 동시 분석)
        if all_elements:
            analyses_list = element_analyzer.analyze_batch(
                elements=all_elements,
                page_images=page_images,
                page_structures=structures,
            )
            analyses = {analysis.element_id: analysis for analysis in analyses_list}
        else:
            analyses = {}

        print(f"✅ Pass 2 완료: {len(analyses)}개 요소 분석")

        # DocJSON 생성
        print(f"\nDocJSON 생성...")
        enricher = TextEnricher(config)
        page_images = [p.image for p in pages]
        docjson = enricher.enrich(structures, analyses, page_images)

        # 결과 저장
        output_file = output_dir / f"{pdf_path.stem}_docjson.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(docjson.to_dict(), f, ensure_ascii=False, indent=2)

        elapsed = time.time() - start_time

        # 정리
        engine.unload()

        result = {
            "status": "success",
            "pdf": pdf_path.name,
            "pages": len(pages),
            "elements": len(analyses),
            "blocks": len(docjson.blocks),
            "sections": len(docjson.sections),
            "elapsed": elapsed,
            "output": str(output_file),
        }

        print(f"\n{'='*70}")
        print(f"✅ 완료: {pdf_path.name}")
        print(f"   처리 시간: {elapsed/60:.1f}분")
        print(f"   출력: {output_file}")
        print(f"{'='*70}")

        return result

    except Exception as e:
        elapsed = time.time() - start_time

        print(f"\n❌ 실패: {pdf_path.name}")
        print(f"   에러: {e}")

        return {
            "status": "failed",
            "pdf": pdf_path.name,
            "error": str(e),
            "elapsed": elapsed,
        }


def main():
    parser = argparse.ArgumentParser(
        description="RunPod 배치 처리 스크립트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--input",
        required=True,
        help="입력 PDF 디렉토리",
    )
    parser.add_argument(
        "--output",
        default="./outputs",
        help="출력 디렉토리 (기본: ./outputs)",
    )
    parser.add_argument(
        "--preset",
        choices=["rtx4060", "rtx4090", "cpu"],
        default="rtx4090",
        help="설정 프리셋 (기본: rtx4090)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="동시 처리 개수 (기본: 1, GPU 메모리 충분시 2-3 가능)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="이미 처리된 파일 건너뛰기",
    )

    args = parser.parse_args()

    # 디렉토리 설정
    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists():
        print(f"❌ 입력 디렉토리가 없습니다: {input_dir}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    # PDF 파일 찾기
    pdf_files = list(input_dir.glob("*.pdf"))

    if not pdf_files:
        print(f"❌ PDF 파일을 찾을 수 없습니다: {input_dir}")
        return 1

    # Resume: 이미 처리된 파일 제외
    if args.resume:
        remaining_files = []
        for pdf in pdf_files:
            output_file = output_dir / f"{pdf.stem}_docjson.json"
            if not output_file.exists():
                remaining_files.append(pdf)
        pdf_files = remaining_files

    if not pdf_files:
        print("✅ 모든 파일이 이미 처리되었습니다.")
        return 0

    print(f"\n{'='*70}")
    print(f"RunPod 배치 처리")
    print(f"{'='*70}")
    print(f"입력: {input_dir}")
    print(f"출력: {output_dir}")
    print(f"프리셋: {args.preset}")
    print(f"동시 작업: {args.max_workers}")
    print(f"처리할 파일: {len(pdf_files)}개")
    print(f"{'='*70}")

    # 설정 로드
    config = load_config(preset=args.preset)
    config.output_dir = str(output_dir)
    config.image_output_dir = str(output_dir / "cropped_images")
    config.validate()

    # 처리 시작
    start_time = time.time()
    results = []

    if args.max_workers == 1:
        # 순차 처리
        for pdf_path in pdf_files:
            result = process_single_pdf(pdf_path, output_dir, config)
            results.append(result)
    else:
        # 병렬 처리 (GPU 메모리 충분시)
        print(f"\n⚠️  병렬 처리 모드 ({args.max_workers} workers)")
        print(f"⚠️  GPU 메모리가 부족하면 OOM 에러가 발생할 수 있습니다.")

        with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {
                executor.submit(process_single_pdf, pdf, output_dir, config): pdf
                for pdf in pdf_files
            }

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

    # 전체 결과 요약
    total_elapsed = time.time() - start_time
    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = len(results) - success_count

    print(f"\n{'='*70}")
    print(f"배치 처리 완료")
    print(f"{'='*70}")
    print(f"총 처리 시간: {total_elapsed/60:.1f}분")
    print(f"성공: {success_count}/{len(results)}")
    print(f"실패: {failed_count}/{len(results)}")

    if success_count > 0:
        avg_time = sum(r["elapsed"] for r in results if r["status"] == "success") / success_count
        print(f"평균 처리 시간: {avg_time/60:.1f}분/문서")

    # 결과 상세
    print(f"\n상세 결과:")
    for result in results:
        status_icon = "✅" if result["status"] == "success" else "❌"
        print(f"{status_icon} {result['pdf']}: {result.get('elapsed', 0)/60:.1f}분")
        if result["status"] == "failed":
            print(f"   에러: {result.get('error', 'Unknown')}")

    # 결과 저장
    summary_file = output_dir / "batch_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_files": len(pdf_files),
            "success": success_count,
            "failed": failed_count,
            "total_time": total_elapsed,
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n결과 요약 저장: {summary_file}")
    print(f"{'='*70}")

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
