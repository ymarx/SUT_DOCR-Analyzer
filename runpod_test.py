"""
RunPod Test Script for DeepSeek-OCR on Scanned Documents
Tests OCR capabilities on TP-030-030-030.pdf
"""

import sys
from pathlib import Path
import time
import torch
from transformers import AutoModel, AutoTokenizer
from PIL import Image
import fitz  # PyMuPDF
from pdf2image import convert_from_path

print("="*70)
print("RunPod DeepSeek-OCR Test - Scanned Document Processing")
print("="*70)

# Configuration
PDF_PATH = "test_samples/TP-030-030-030 노열관리 및 보상기준.pdf"
OUTPUT_DIR = Path("runpod_outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

MODEL_NAME = "deepseek-ai/DeepSeek-OCR"
CACHE_DIR = "./models/deepseek-ocr"

# Device setup
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.bfloat16 if device == "cuda" else torch.float32

print(f"\n🖥️ Device: {device}")
print(f"🔢 Dtype: {dtype}")

if device == "cuda":
    print(f"🎮 GPU: {torch.cuda.get_device_name(0)}")
    print(f"💾 VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

# Load model
print(f"\n📥 Loading DeepSeek-OCR from {CACHE_DIR}...")
start = time.time()

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME,
    trust_remote_code=True,
    cache_dir=CACHE_DIR
)

model = AutoModel.from_pretrained(
    MODEL_NAME,
    trust_remote_code=True,
    cache_dir=CACHE_DIR,
    torch_dtype=dtype,
    device_map=device if device == "cuda" else None
)

if device == "cuda":
    model = model.cuda()

model = model.eval()

load_time = time.time() - start
print(f"✅ Model loaded in {load_time:.1f} seconds")

# Convert PDF to images
print(f"\n📄 Converting PDF to images...")
pdf_path = Path(PDF_PATH)

if not pdf_path.exists():
    print(f"❌ PDF not found: {PDF_PATH}")
    print(f"Please upload your PDF to: {pdf_path.absolute()}")
    sys.exit(1)

# Get page count
doc = fitz.open(pdf_path)
num_pages = len(doc)
doc.close()

print(f"📊 Total pages: {num_pages}")

# Convert first page for testing
print(f"\n🖼️ Converting first page to image (DPI=200)...")
images = convert_from_path(
    pdf_path,
    dpi=200,
    first_page=1,
    last_page=1
)

test_image = images[0]
test_image_path = OUTPUT_DIR / "test_page_1.png"
test_image.save(test_image_path)

print(f"✅ Image saved: {test_image_path}")
print(f"   Size: {test_image.size[0]}x{test_image.size[1]}px")

# Test 1: Free OCR (Extract all text)
print("\n" + "="*70)
print("TEST 1: Free OCR - Extract All Text")
print("="*70)

prompt1 = "<image>\nFree OCR. "
output_path1 = str(OUTPUT_DIR / "test1_free_ocr")

print(f"\n🔍 Running inference...")
start = time.time()

result1 = model.infer(
    tokenizer,
    prompt=prompt1,
    image_file=str(test_image_path),
    output_path=output_path1,
    base_size=1024,
    image_size=640,
    crop_mode=True,
    save_results=True,
    test_compress=True
)

elapsed1 = time.time() - start

print(f"\n✅ Inference completed in {elapsed1:.1f} seconds")
print(f"\n📝 OCR Output Preview (first 500 chars):")
print("-" * 70)
print(result1[:500])
if len(result1) > 500:
    print(f"... ({len(result1) - 500} more characters)")
print("-" * 70)

# Save full output
output_txt1 = OUTPUT_DIR / "test1_free_ocr.txt"
output_txt1.write_text(result1, encoding='utf-8')
print(f"\n💾 Full output saved: {output_txt1}")

# Test 2: Convert to Markdown
print("\n" + "="*70)
print("TEST 2: Convert Document to Markdown")
print("="*70)

prompt2 = "<image>\n<|grounding|>Convert the document to markdown. "
output_path2 = str(OUTPUT_DIR / "test2_markdown")

print(f"\n🔍 Running inference...")
start = time.time()

result2 = model.infer(
    tokenizer,
    prompt=prompt2,
    image_file=str(test_image_path),
    output_path=output_path2,
    base_size=1024,
    image_size=640,
    crop_mode=True,
    save_results=True,
    test_compress=True
)

elapsed2 = time.time() - start

print(f"\n✅ Inference completed in {elapsed2:.1f} seconds")
print(f"\n📝 Markdown Output Preview (first 500 chars):")
print("-" * 70)
print(result2[:500])
if len(result2) > 500:
    print(f"... ({len(result2) - 500} more characters)")
print("-" * 70)

# Save full output
output_txt2 = OUTPUT_DIR / "test2_markdown.md"
output_txt2.write_text(result2, encoding='utf-8')
print(f"\n💾 Full output saved: {output_txt2}")

# Test 3: Structured Analysis (Custom Prompt)
print("\n" + "="*70)
print("TEST 3: Structured Analysis with Custom Prompt")
print("="*70)

prompt3 = """<image>
<|grounding|>Analyze this Korean steel mill technical document and extract:

1. **Document Title** (문서 제목)
2. **Main Topics** (주요 항목) - list all section headings
3. **Key Technical Terms** (주요 기술 용어) - extract 10 important keywords
4. **Summary** (요약) - summarize the content in 3-4 sentences in Korean

Format the output clearly with headers."""

output_path3 = str(OUTPUT_DIR / "test3_structured")

print(f"\n🔍 Running inference...")
start = time.time()

result3 = model.infer(
    tokenizer,
    prompt=prompt3,
    image_file=str(test_image_path),
    output_path=output_path3,
    base_size=1024,
    image_size=640,
    crop_mode=True,
    save_results=True,
    test_compress=True
)

elapsed3 = time.time() - start

print(f"\n✅ Inference completed in {elapsed3:.1f} seconds")
print(f"\n📝 Structured Analysis Output:")
print("-" * 70)
print(result3)
print("-" * 70)

# Save full output
output_txt3 = OUTPUT_DIR / "test3_structured.txt"
output_txt3.write_text(result3, encoding='utf-8')
print(f"\n💾 Full output saved: {output_txt3}")

# Performance Summary
print("\n" + "="*70)
print("Performance Summary")
print("="*70)
print(f"\nTest 1 (Free OCR):        {elapsed1:.1f}s")
print(f"Test 2 (Markdown):        {elapsed2:.1f}s")
print(f"Test 3 (Structured):      {elapsed3:.1f}s")
print(f"\nAverage time per page:    {(elapsed1 + elapsed2 + elapsed3) / 3:.1f}s")
print(f"Estimated time for 5 pages: {((elapsed1 + elapsed2 + elapsed3) / 3) * 5 / 60:.1f} minutes")

# Output files summary
print("\n" + "="*70)
print("Output Files")
print("="*70)
print(f"\n📁 Output directory: {OUTPUT_DIR.absolute()}")
print(f"\nGenerated files:")
print(f"  - test_page_1.png           (input image)")
print(f"  - test1_free_ocr.txt        (raw OCR text)")
print(f"  - test2_markdown.md         (markdown format)")
print(f"  - test3_structured.txt      (custom analysis)")

print("\n" + "="*70)
print("✅ All tests completed successfully!")
print("="*70)

print(f"""
Next Steps:
1. Review output files in {OUTPUT_DIR.absolute()}
2. Adjust prompts in this script for your specific needs
3. Process all 5 pages by modifying first_page/last_page parameters
4. Integrate with your pipeline in src/mypkg/components/vlm_analyzer.py
""")
