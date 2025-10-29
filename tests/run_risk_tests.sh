#!/bin/bash
# Risk Validation Test Runner
# vLLM nightly 마이그레이션 전 리스크 검증 테스트

set -e  # 에러 발생 시 중단

echo "============================================================"
echo "vLLM Migration Risk Validation Tests"
echo "============================================================"
echo ""

# 설정
PRESET="${1:-rtx4090}"  # 기본값: rtx4090
TEST_IMAGE="${2}"
TEST_PDF="${3}"
TEST_PAGE="${4:-1}"

echo "Configuration:"
echo "  Hardware preset: $PRESET"
echo "  Test image: ${TEST_IMAGE:-Not provided}"
echo "  Test PDF: ${TEST_PDF:-Not provided}"
echo "  Test page: $TEST_PAGE"
echo ""

# 스크립트 디렉토리
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# 가상환경 확인
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Virtual environment not activated"
    echo "   Attempting to activate .venv..."
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
        echo "✅ Virtual environment activated"
    else
        echo "❌ Virtual environment not found. Please run:"
        echo "   source .venv/bin/activate"
        exit 1
    fi
fi

echo ""
echo "============================================================"
echo "Test 1: Label Detection Test"
echo "============================================================"
echo ""
echo "Purpose: Verify which labels official vLLM uses"
echo "Risk: Unknown labels may not map to our 7 categories"
echo ""

if [ -n "$TEST_IMAGE" ]; then
    python tests/test_label_detection.py --image "$TEST_IMAGE" --preset "$PRESET"
elif [ -n "$TEST_PDF" ]; then
    python tests/test_label_detection.py --pdf "$TEST_PDF" --page "$TEST_PAGE" --preset "$PRESET"
else
    echo "⚠️  Skipped: No test image or PDF provided"
    echo "   Usage: ./tests/run_risk_tests.sh rtx4090 path/to/image.jpg"
    echo "      or: ./tests/run_risk_tests.sh rtx4090 \"\" path/to/doc.pdf 1"
fi

echo ""
echo "============================================================"
echo "Test 2: Figure Classification Test"
echo "============================================================"
echo ""
echo "Purpose: Determine if 'figure' label should map to graph/diagram/complex_image"
echo "Risk: Wrong classification leads to incorrect Pass 2 prompts"
echo ""

if [ -n "$TEST_IMAGE" ]; then
    echo "Testing figure classification (if any figures detected)..."
    python tests/test_figure_classification.py --image "$TEST_IMAGE" --element 0 --preset "$PRESET" || echo "⚠️  No figure elements found or test failed"
else
    echo "⚠️  Skipped: No test image provided"
fi

echo ""
echo "============================================================"
echo "Test 3: Text Preview Quality Test"
echo "============================================================"
echo ""
echo "Purpose: Verify Pass 2 has sufficient context from Pass 1"
echo "Risk: Insufficient context degrades Pass 2 analysis quality"
echo ""

if [ -n "$TEST_IMAGE" ]; then
    python tests/test_text_preview.py --image "$TEST_IMAGE" --preset "$PRESET"
elif [ -n "$TEST_PDF" ]; then
    python tests/test_text_preview.py --pdf "$TEST_PDF" --page "$TEST_PAGE" --preset "$PRESET"
else
    echo "⚠️  Skipped: No test image or PDF provided"
fi

echo ""
echo "============================================================"
echo "Risk Validation Tests Complete"
echo "============================================================"
echo ""
echo "📋 Next Steps:"
echo "  1. Review test results above"
echo "  2. Update LABEL_MAPPING if unknown labels found"
echo "  3. Adjust figure classification if needed"
echo "  4. Consider increasing text_preview length if insufficient"
echo "  5. Proceed with vLLM nightly migration"
echo ""
echo "============================================================"
