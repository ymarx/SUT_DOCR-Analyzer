#!/usr/bin/env python3
"""vLLM 모델 아키텍처 import 및 등록 검증"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_model_import():
    """모델 클래스 import 테스트"""
    print("="*70)
    print("1. 모델 클래스 import 테스트")
    print("="*70)

    try:
        from deepseek_ocr.vllm_model import DeepseekOCRForCausalLM
        print("✅ DeepseekOCRForCausalLM import 성공")
        print(f"   클래스 위치: {DeepseekOCRForCausalLM.__module__}")
        return True
    except ImportError as e:
        print(f"❌ Import 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_model_registration():
    """모델 등록 테스트"""
    print("\n" + "="*70)
    print("2. vLLM ModelRegistry 등록 테스트")
    print("="*70)

    try:
        from vllm.model_executor.models.registry import ModelRegistry
        from deepseek_ocr.vllm_model import DeepseekOCRForCausalLM

        # Configure before registration
        print("   설정 값: image_size=640, base_size=1024, crop_mode=True")
        DeepseekOCRForCausalLM.configure_globals(
            image_size=640, base_size=1024, crop_mode=True
        )

        # Register
        ModelRegistry.register_model("DeepseekOCRForCausalLM", DeepseekOCRForCausalLM)
        print("✅ ModelRegistry 등록 성공")

        # Verify
        registered_models = list(ModelRegistry._registry.keys())
        if "DeepseekOCRForCausalLM" in registered_models:
            print("✅ 등록 확인: DeepseekOCRForCausalLM in registry")
            print(f"   전체 등록된 모델 수: {len(registered_models)}")
            return True
        else:
            print("❌ 등록 실패: 모델이 registry에 없음")
            return False

    except Exception as e:
        print(f"❌ 등록 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_deepencoder():
    """Vision encoder import 테스트"""
    print("\n" + "="*70)
    print("3. Vision Encoder 모듈 import 테스트")
    print("="*70)

    try:
        from deepseek_ocr.vllm_model.deepencoder import (
            build_sam_vit_b, build_clip_l, MlpProjector
        )
        print("✅ SAM encoder import 성공")
        print("✅ CLIP encoder import 성공")
        print("✅ MLP projector import 성공")
        return True
    except ImportError as e:
        print(f"❌ Import 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_image_processor():
    """Image processor import 테스트"""
    print("\n" + "="*70)
    print("4. Image Processor import 테스트")
    print("="*70)

    try:
        from deepseek_ocr.engine.image_processor import DeepseekOCRProcessor, count_tiles
        print("✅ DeepseekOCRProcessor import 성공")
        print("✅ count_tiles import 성공")
        return True
    except ImportError as e:
        print(f"❌ Import 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    results = []

    results.append(test_model_import())
    results.append(test_model_registration())
    results.append(test_deepencoder())
    results.append(test_image_processor())

    print("\n" + "="*70)
    print("검증 결과 요약")
    print("="*70)

    passed = sum(results)
    total = len(results)

    print(f"통과: {passed}/{total}")

    if all(results):
        print("✅ 모든 검증 통과: vLLM 모델 통합 성공")
        print("\n다음 단계: RunPod에서 실제 PDF 처리 테스트")
        print("  python runpod/process.py --input pdfs/ --output outputs/ --preset rtx4090")
        sys.exit(0)
    else:
        print("❌ 일부 검증 실패: 위 오류 메시지 확인 필요")
        sys.exit(1)
