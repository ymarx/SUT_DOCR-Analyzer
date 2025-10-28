"""
Configuration for DeepSeek-OCR processing pipeline.

Optimized for RTX 4060 8GB with float16 and batch_size=1.
"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, Optional
import yaml


@dataclass
class Config:
    """
    DeepSeek-OCR configuration for vLLM engine.

    vLLM optimizations:
    - PagedAttention for memory efficiency
    - Batch processing with dynamic scheduling
    - Parallel image preprocessing
    """

    # Engine type
    engine_type: str = "vllm"  # "vllm" or "hf" (HuggingFace Transformers)

    # Model configuration
    model_name: str = "deepseek-ai/DeepSeek-OCR"
    cache_dir: str = "./models/DeepSeek-OCR"
    device: str = "cuda"
    dtype: str = "bfloat16"  # RTX 4090: bfloat16 | RTX 4060: float16

    # vLLM-specific settings
    max_num_seqs: int = 100  # Concurrent sequences (RTX 4090: 100, RTX 4060: 10)
    gpu_memory_utilization: float = 0.9  # GPU memory usage (RTX 4090: 0.9, RTX 4060: 0.75)
    block_size: int = 256  # PagedAttention block size
    tensor_parallel_size: int = 1  # Tensor parallelism (1 for single GPU)

    # Preprocessing workers
    num_workers: int = 64  # Parallel image preprocessing workers

    # Image processing settings
    batch_size: int = 1  # Deprecated for vLLM (use max_num_seqs instead)
    base_size: int = 1024  # Global view size (Gundam mode)
    image_size: int = 640  # Crop tile size (Gundam mode)
    crop_mode: bool = True  # Enable dynamic preprocessing (Gundam mode)
    min_crops: int = 2  # Minimum crop tiles
    max_crops: int = 6  # Maximum crop tiles (reduce for low memory)

    # Memory optimization (deprecated for vLLM)
    max_memory: Dict[str, str] = field(default_factory=lambda: {"cuda:0": "23GB"})
    low_cpu_mem_usage: bool = True

    # Generation settings (deprecated for vLLM - use SamplingParams)
    max_new_tokens: int = 8192  # Max tokens for vLLM
    temperature: float = 0.0  # Greedy decoding (vLLM default)
    top_p: float = 1.0
    do_sample: bool = False

    # Pipeline settings
    pdf_dpi: int = 200  # PDF to image DPI (200 recommended, 300 for high quality)
    save_images: bool = True  # Save cropped element images
    output_dir: str = "./outputs"
    image_output_dir: str = "./outputs/cropped_images"

    # Element complexity thresholds
    table_complexity_threshold: float = 0.3  # >30% merged cells → complex_image
    diagram_complexity_threshold: int = 10  # >10 components → complex_image

    # Keyword extraction
    max_keywords: int = 10
    min_keyword_length: int = 2

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create Config from dictionary."""
        return cls(**data)

    def save_yaml(self, path: str) -> None:
        """Save configuration to YAML file."""
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, allow_unicode=True)

    @classmethod
    def load_yaml(cls, path: str) -> "Config":
        """Load configuration from YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)

    def validate(self) -> None:
        """Validate configuration settings."""
        # Device validation
        if self.device not in ["cuda", "cpu"]:
            raise ValueError(f"Invalid device: {self.device}. Must be 'cuda' or 'cpu'.")

        # Dtype validation
        valid_dtypes = ["float16", "float32", "bfloat16"]
        if self.dtype not in valid_dtypes:
            raise ValueError(f"Invalid dtype: {self.dtype}. Must be one of {valid_dtypes}.")

        # Memory validation
        if self.device == "cuda" and self.dtype == "float32":
            print("⚠️ Warning: float32 on CUDA may cause OOM on RTX 4060 8GB. Consider using float16.")

        # Resolution validation
        valid_base_sizes = [512, 640, 1024, 1280]
        if self.base_size not in valid_base_sizes:
            print(f"⚠️ Warning: base_size {self.base_size} is non-standard. Recommended: {valid_base_sizes}")

        # DPI validation
        if self.pdf_dpi < 150:
            print(f"⚠️ Warning: pdf_dpi {self.pdf_dpi} is low. May affect OCR quality. Recommended: 200-300")

        # Create output directories
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        if self.save_images:
            Path(self.image_output_dir).mkdir(parents=True, exist_ok=True)
            for subdir in ["graph", "table", "diagram", "complex_image"]:
                (Path(self.image_output_dir) / subdir).mkdir(parents=True, exist_ok=True)


# Preset configurations for vLLM
RTX_4060_CONFIG = Config(
    engine_type="vllm",
    device="cuda",
    dtype="float16",
    base_size=1024,
    image_size=640,
    max_num_seqs=10,  # Limited concurrency for 8GB VRAM
    gpu_memory_utilization=0.75,
    num_workers=32,  # Fewer preprocessing workers
    max_crops=4,  # Reduced for memory
    max_memory={"cuda:0": "7.5GB"},
)

RTX_4090_CONFIG = Config(
    engine_type="vllm",
    device="cuda",
    dtype="bfloat16",
    base_size=1024,
    image_size=640,
    max_num_seqs=100,  # High concurrency for 24GB VRAM
    gpu_memory_utilization=0.9,
    num_workers=64,
    max_crops=6,
    max_memory={"cuda:0": "23GB"},
)

CPU_CONFIG = Config(
    device="cpu",
    dtype="float32",
    batch_size=1,
    base_size=640,  # Smaller for CPU performance
    image_size=512,
    max_memory={},
)


def load_config(path: Optional[str] = None, preset: Optional[str] = None) -> Config:
    """
    Load configuration from file or preset.

    Args:
        path: Path to YAML config file
        preset: Preset name ('rtx4060', 'rtx4090', 'cpu')

    Returns:
        Config instance

    Examples:
        >>> config = load_config(preset='rtx4060')
        >>> config = load_config(path='configs/custom.yaml')
    """
    if path:
        return Config.load_yaml(path)
    elif preset:
        presets = {
            "rtx4060": RTX_4060_CONFIG,
            "rtx4090": RTX_4090_CONFIG,
            "cpu": CPU_CONFIG,
        }
        if preset.lower() not in presets:
            raise ValueError(f"Unknown preset: {preset}. Available: {list(presets.keys())}")
        return presets[preset.lower()]
    else:
        return Config()  # Default config
