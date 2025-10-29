"""
Figure Classification Test - "figure" label 세부 분류 테스트

공식 vLLM이 <|ref|>figure<|/ref|>를 사용할 때,
실제로 graph, diagram, complex_image 중 무엇인지 판별합니다.

Pass 2 프롬프트를 각각 시도하여 어느 프롬프트가 가장 적합한지 확인합니다.

Usage:
    python tests/test_figure_classification.py --image chart.jpg
    python tests/test_figure_classification.py --pdf doc.pdf --page 5 --element 2
"""

import re
import sys
import json
import argparse
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from deepseek_ocr.core.config import Config
from deepseek_ocr.core.types import BoundingBox
from deepseek_ocr.core.utils import crop_bbox
from deepseek_ocr.engine.deepseek_vllm_engine import DeepSeekVLLMEngine
from deepseek_ocr.engine.prompts import (
    GRAPH_ANALYSIS_PROMPT,
    DIAGRAM_ANALYSIS_PROMPT,
    COMPLEX_IMAGE_PROMPT,
)
from deepseek_ocr.pipeline.pdf_parser import PDFParser


def extract_figure_elements(markdown_text: str) -> List[Tuple[str, str, int]]:
    """
    Extract all "figure" labeled elements from markdown.

    Args:
        markdown_text: Raw markdown with grounding tags

    Returns:
        List of (label, bbox_str, index) tuples for figure elements
    """
    pattern = re.compile(r"<\|ref\|>(.*?)<\|/ref\|><\|det\|>(.*?)<\|/det\|>", re.DOTALL)
    matches = pattern.findall(markdown_text)

    figure_elements = []
    for idx, (label, bbox) in enumerate(matches):
        label_clean = label.strip().lower()
        if 'figure' in label_clean or 'fig' in label_clean:
            figure_elements.append((label.strip(), bbox.strip(), idx))

    return figure_elements


def parse_bbox(bbox_str: str, image_width: int, image_height: int) -> Optional[BoundingBox]:
    """
    Parse bbox string to BoundingBox object.

    Args:
        bbox_str: e.g., "[[100,200,800,600]]" or "[100,200,800,600]"
        image_width: Image width for normalization
        image_height: Image height for normalization

    Returns:
        BoundingBox object or None if parsing fails
    """
    try:
        # Evaluate as Python literal
        coords_list = eval(bbox_str)

        # Handle nested list
        if isinstance(coords_list, list) and len(coords_list) > 0:
            if isinstance(coords_list[0], list):
                coords_list = coords_list[0]

        if len(coords_list) < 4:
            return None

        x1, y1, x2, y2 = coords_list[:4]

        # Normalize from 0-999 to pixel coordinates
        x1_px = int((x1 / 999.0) * image_width)
        y1_px = int((y1 / 999.0) * image_height)
        x2_px = int((x2 / 999.0) * image_width)
        y2_px = int((y2 / 999.0) * image_height)

        return BoundingBox(x1=x1_px, y1=y1_px, x2=x2_px, y2=y2_px, page=1)

    except Exception as e:
        print(f"⚠️ Warning: Failed to parse bbox '{bbox_str}': {e}")
        return None


def test_figure_with_prompts(
    cropped_image: Image.Image,
    element_label: str,
    engine: DeepSeekVLLMEngine,
) -> dict:
    """
    Test a figure element with all 3 prompts to determine best classification.

    Args:
        cropped_image: Cropped element image
        element_label: Original label (e.g., "figure")
        engine: vLLM engine instance

    Returns:
        Analysis results for each prompt type
    """
    results = {}

    # Test 1: Graph prompt
    print("\n  🔵 Testing with GRAPH prompt...")
    graph_prompt = GRAPH_ANALYSIS_PROMPT.format(context="No context available")
    try:
        graph_response = engine.infer(cropped_image, graph_prompt)
        graph_json = extract_json(graph_response)
        results['graph'] = {
            'response': graph_response,
            'json': graph_json,
            'success': graph_json is not None,
            'has_graph_type': bool(graph_json and 'graph_data' in graph_json),
        }
        print(f"    ✅ Graph analysis {'succeeded' if results['graph']['success'] else 'failed'}")
    except Exception as e:
        results['graph'] = {'error': str(e), 'success': False}
        print(f"    ❌ Graph analysis error: {e}")

    # Test 2: Diagram prompt
    print("  🔵 Testing with DIAGRAM prompt...")
    diagram_prompt = DIAGRAM_ANALYSIS_PROMPT.format(context="No context available")
    try:
        diagram_response = engine.infer(cropped_image, diagram_prompt)
        diagram_json = extract_json(diagram_response)
        results['diagram'] = {
            'response': diagram_response,
            'json': diagram_json,
            'success': diagram_json is not None,
            'has_diagram_type': bool(diagram_json and 'diagram_data' in diagram_json),
        }
        print(f"    ✅ Diagram analysis {'succeeded' if results['diagram']['success'] else 'failed'}")
    except Exception as e:
        results['diagram'] = {'error': str(e), 'success': False}
        print(f"    ❌ Diagram analysis error: {e}")

    # Test 3: Complex image prompt
    print("  🔵 Testing with COMPLEX_IMAGE prompt...")
    complex_prompt = COMPLEX_IMAGE_PROMPT.format(context="No context available")
    try:
        complex_response = engine.infer(cropped_image, complex_prompt)
        complex_json = extract_json(complex_response)
        results['complex_image'] = {
            'response': complex_response,
            'json': complex_json,
            'success': complex_json is not None,
            'underlying_type': complex_json.get('complexity_data', {}).get('underlying_type') if complex_json else None,
        }
        print(f"    ✅ Complex image analysis {'succeeded' if results['complex_image']['success'] else 'failed'}")
    except Exception as e:
        results['complex_image'] = {'error': str(e), 'success': False}
        print(f"    ❌ Complex image analysis error: {e}")

    return results


def extract_json(response: str) -> Optional[dict]:
    """
    Extract JSON object from response text.

    Args:
        response: Response text containing JSON

    Returns:
        Parsed JSON dict or None
    """
    # Try to find JSON block
    json_pattern = re.compile(r'\{[^}]*\}', re.DOTALL)
    matches = json_pattern.findall(response)

    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    return None


def determine_best_classification(results: dict) -> str:
    """
    Determine which classification is best based on results.

    Args:
        results: Analysis results from all 3 prompts

    Returns:
        Best classification: 'graph', 'diagram', or 'complex_image'
    """
    scores = {'graph': 0, 'diagram': 0, 'complex_image': 0}

    # Score based on successful parsing
    for prompt_type in ['graph', 'diagram', 'complex_image']:
        if results.get(prompt_type, {}).get('success'):
            scores[prompt_type] += 1

    # Bonus score for type-specific fields
    if results.get('graph', {}).get('has_graph_type'):
        scores['graph'] += 2

    if results.get('diagram', {}).get('has_diagram_type'):
        scores['diagram'] += 2

    # Complex image is fallback (lower priority)
    scores['complex_image'] -= 1

    # Return highest scoring type
    return max(scores.items(), key=lambda x: x[1])[0]


def test_figure_classification(image_path: str, element_index: int, config: Config):
    """
    Test figure classification on a specific image.

    Args:
        image_path: Path to image file
        element_index: Which figure element to test (0-indexed)
        config: Config instance
    """
    print("\n" + "="*70)
    print(f"Figure Classification Test: {Path(image_path).name}")
    print("="*70)

    # Load image
    image = Image.open(image_path).convert("RGB")
    print(f"✅ Image loaded: {image.size}")

    # Initialize engine
    print("\nInitializing vLLM engine...")
    engine = DeepSeekVLLMEngine(config)

    try:
        # Run Pass 1 to find figure elements
        print("\nPass 1: Finding figure elements...")
        prompt = "<image>\n<|grounding|>Convert the document to markdown."
        response = engine.infer(image, prompt)

        figure_elements = extract_figure_elements(response)

        if not figure_elements:
            print("❌ No figure elements found in this image")
            return

        print(f"✅ Found {len(figure_elements)} figure element(s)")

        if element_index >= len(figure_elements):
            print(f"❌ Element index {element_index} out of range (0-{len(figure_elements)-1})")
            return

        # Get target figure
        label, bbox_str, idx = figure_elements[element_index]
        print(f"\n🎯 Testing element {element_index}: <|ref|>{label}<|/ref|>")
        print(f"   Bounding box: {bbox_str}")

        # Parse bbox and crop
        bbox = parse_bbox(bbox_str, image.width, image.height)
        if not bbox:
            print("❌ Failed to parse bounding box")
            return

        cropped = crop_bbox(image, bbox)
        print(f"✅ Cropped image: {cropped.size}")

        # Test with all 3 prompts
        print("\n" + "-"*70)
        print("Testing with all 3 prompt types:")
        print("-"*70)

        results = test_figure_with_prompts(cropped, label, engine)

        # Determine best classification
        best_class = determine_best_classification(results)

        # Show results
        print("\n" + "="*70)
        print("CLASSIFICATION RESULTS")
        print("="*70)

        print(f"\n🎯 Original label: {label}")
        print(f"🎯 Recommended classification: {best_class.upper()}")

        print("\n📊 Detailed Analysis:")
        for prompt_type in ['graph', 'diagram', 'complex_image']:
            result = results.get(prompt_type, {})
            symbol = "✅" if result.get('success') else "❌"
            print(f"\n  {symbol} {prompt_type.upper()}:")

            if result.get('success'):
                json_data = result.get('json', {})
                print(f"     - Parsed JSON: Yes")
                if prompt_type == 'graph' and 'graph_data' in json_data:
                    print(f"     - Graph type: {json_data['graph_data'].get('graph_type', 'unknown')}")
                elif prompt_type == 'diagram' and 'diagram_data' in json_data:
                    print(f"     - Diagram type: {json_data['diagram_data'].get('diagram_type', 'unknown')}")
                elif prompt_type == 'complex_image':
                    print(f"     - Underlying type: {result.get('underlying_type', 'unknown')}")

                keywords = json_data.get('keywords', [])
                if keywords:
                    print(f"     - Keywords: {', '.join(keywords[:5])}")
            else:
                error = result.get('error', 'Unknown error')
                print(f"     - Error: {error}")

        print("\n" + "="*70)
        print("RECOMMENDATION")
        print("="*70)
        print(f"\n⭐ For label '{label}', use: ElementType.{best_class.upper()}")
        print(f"\nUpdate LABEL_MAPPING in markdown_parser.py:")
        print(f'  "{label.lower()}": ElementType.{best_class.upper()},')

    finally:
        engine.unload()


def main():
    parser = argparse.ArgumentParser(description="Test figure classification")
    parser.add_argument("--image", type=str, required=True, help="Path to image file")
    parser.add_argument("--element", type=int, default=0, help="Figure element index (0-indexed)")
    parser.add_argument("--preset", type=str, default="rtx4090",
                       choices=["rtx4060", "rtx4090", "cpu"],
                       help="Hardware preset")

    args = parser.parse_args()

    # Load config
    from deepseek_ocr.core.config import load_config
    config = load_config(preset=args.preset)

    print("\n" + "="*70)
    print("Figure Classification Test")
    print("="*70)
    print(f"Hardware preset: {args.preset}")

    test_figure_classification(args.image, args.element, config)


if __name__ == "__main__":
    main()
