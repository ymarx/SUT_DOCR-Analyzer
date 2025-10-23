#!/bin/bash
# RunPod Setup Script for SUT Preprocessing with DeepSeek-OCR
# GPU Required: NVIDIA RTX 3090/4090 or A100 (VRAM >= 12GB)

set -e  # Exit on error

echo "========================================"
echo "SUT Preprocessing - RunPod Setup"
echo "========================================"

# 1. System Info
echo ""
echo "[1/7] System Information"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
python --version

# 2. Update system packages
echo ""
echo "[2/7] Updating system packages..."
apt-get update -qq
apt-get install -y poppler-utils wget git

# 3. Create workspace
echo ""
echo "[3/7] Setting up workspace..."
WORKSPACE="/workspace/sut-preprocess"
mkdir -p $WORKSPACE
cd $WORKSPACE

# 4. Clone project (if not already present)
echo ""
echo "[4/7] Setting up project..."
if [ ! -d "$WORKSPACE/.git" ]; then
    echo "Cloning project repository..."
    # Replace with your actual git repository
    # git clone https://github.com/your-repo/sut-preprocess.git .
    echo "⚠️ Manual project upload required"
else
    echo "✅ Project already exists"
fi

# 5. Install Python dependencies
echo ""
echo "[5/7] Installing Python dependencies..."
pip install --upgrade pip
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install transformers==4.46.3 tokenizers==0.20.3
pip install pymupdf pdf2image pillow
pip install addict einops easydict
pip install gradio  # Optional: for web UI

# 6. Download DeepSeek-OCR model
echo ""
echo "[6/7] Downloading DeepSeek-OCR model (~12GB)..."
python << 'PYTHON'
from transformers import AutoModel, AutoTokenizer
import torch

model_name = "deepseek-ai/DeepSeek-OCR"
cache_dir = "./models/deepseek-ocr"

print("Downloading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(
    model_name,
    trust_remote_code=True,
    cache_dir=cache_dir
)

print("Downloading model (this may take 5-10 minutes)...")
model = AutoModel.from_pretrained(
    model_name,
    trust_remote_code=True,
    cache_dir=cache_dir,
    torch_dtype=torch.bfloat16,
    device_map="cuda"
)

print(f"✅ Model downloaded to {cache_dir}")
PYTHON

# 7. Verify CUDA setup
echo ""
echo "[7/7] Verifying CUDA setup..."
python << 'PYTHON'
import torch
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA version: {torch.version.cuda}")
print(f"GPU count: {torch.cuda.device_count()}")
if torch.cuda.is_available():
    print(f"GPU name: {torch.cuda.get_device_name(0)}")
    print(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
PYTHON

echo ""
echo "========================================"
echo "✅ RunPod setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Upload your PDF files to /workspace/sut-preprocess/test_samples/"
echo "2. Run: python runpod_test.py"
echo ""
