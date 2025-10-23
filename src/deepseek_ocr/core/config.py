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
    DeepSeek-OCR configuration.

    RTX 4060 8GB optimizations:
    - dtype: float16 (50% memory reduction)
    - batch_size: 1 (process one image at a time)
    - max_memory: 7.5GB (reserve 500MB buffer)
    """

    # Model configuration
    model_name: str = "deepseek-ai/DeepSeek-OCR"
    cache_dir: str = "./models/deepseek-ocr"
    device: str = "cuda"
    dtype: str = "float16"  # RTX 4060: float16 | RTX 4090: bfloat16

    # Inference settings
    batch_size: int = 1
    base_size: int = 1024  # Resolution mode: 512/640/1024/1280
    image_size: int = 640  # Crop size for Pass 2
    crop_mode: bool = True  # Enable Gundam mode (base_size + crop)

    # Memory optimization (RTX 4060 8GB)
    max_memory: Dict[str, str] = field(default_factory=lambda: {"cuda:0": "7.5GB"})
    low_cpu_mem_usage: bool = True

    # Generation settings
    max_new_tokens: int = 512
    temperature: float = 0.1  # Low temperature for deterministic output
    top_p: float = 0.9
    do_sample: bool = False  # Greedy decoding for consistency

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


# Preset configurations
RTX_4060_CONFIG = Config(
    device="cuda",
    dtype="float16",
    batch_size=1,
    base_size=1024,
    image_size=640,
    max_memory={"cuda:0": "7.5GB"},
)

RTX_4090_CONFIG = Config(
    device="cuda",
    dtype="bfloat16",
    batch_size=1,
    base_size=1280,
    image_size=1024,
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
