"""
DeepSeek-OCR engine wrapper with RTX 4060 8GB optimization.

Critical features:
- float16 dtype for 50% memory reduction
- @torch.no_grad() decorators to disable gradients
- Explicit CUDA cache clearing after inference
- Pass 1 (structure) and Pass 2 (element) inference methods
"""

import json
import torch
from PIL import Image
from typing import Dict, Any, Optional
from transformers import AutoModel, AutoTokenizer

from ..core.config import Config
from ..core.types import PageStructure, ElementDetection, ElementAnalysis, ElementType, BoundingBox
from .prompts import STRUCTURE_ANALYSIS_PROMPT, get_element_prompt


class DeepSeekEngine:
    """
    DeepSeek-OCR inference engine.

    Optimized for RTX 4060 8GB:
    - Loads model with float16 dtype
    - Uses @torch.no_grad() to prevent gradient computation
    - Clears CUDA cache after each inference
    - Supports lazy loading (model loaded on first use)
    """

    def __init__(self, config: Config):
        """
        Initialize DeepSeek-OCR engine.

        Args:
            config: Configuration with model settings
        """
        self.config = config
        self.model = None
        self.tokenizer = None
        self._device = None

    def _load_model(self) -> None:
        """Lazy load model and tokenizer."""
        if self.model is not None:
            return

        print(f"Loading DeepSeek-OCR model from {self.config.cache_dir}...")

        # Determine torch dtype
        dtype_map = {
            "float16": torch.float16,
            "float32": torch.float32,
            "bfloat16": torch.bfloat16,
        }
        torch_dtype = dtype_map.get(self.config.dtype, torch.float16)

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_name,
            cache_dir=self.config.cache_dir,
            trust_remote_code=True,
        )

        # Load model with memory optimization
        self.model = AutoModel.from_pretrained(
            self.config.model_name,
            cache_dir=self.config.cache_dir,
            torch_dtype=torch_dtype,
            device_map={"": 0} if self.config.device == "cuda" else None,
            trust_remote_code=True,
            low_cpu_mem_usage=self.config.low_cpu_mem_usage,
        )

        # Set to eval mode
        self.model.eval()

        # Move to device if not using device_map
        if self.config.device == "cuda" and not hasattr(self.model, "hf_device_map"):
            self.model = self.model.cuda()
        elif self.config.device == "cpu":
            self.model = self.model.cpu()

        self._device = self.config.device

        print(f"✅ Model loaded on {self._device} with dtype={self.config.dtype}")

    @torch.no_grad()
    def infer(
        self,
        image: Image.Image,
        prompt: str,
    ) -> str:
        """
        Generic inference using official DeepSeek-OCR API.

        Args:
            image: PIL Image
            prompt: Prompt string from prompts.py (already correctly formatted)
                    e.g., "<image>\n<|grounding|>Analyze this document..."

        Returns:
            Model response string

        Note:
            The official infer() method handles all preprocessing internally:
            1. Creates conversation format with role/content/images
            2. Calls format_messages() to convert to DeepSeek format
            3. Calls load_pil_images() to extract/load images
            4. Calls dynamic_preprocess() for image preprocessing
            5. Performs model inference

            We simply pass the prompt as-is from prompts.py.
        """
        self._load_model()

        try:
            # Use official API - prompt is already correctly formatted in prompts.py
            # The official infer() method handles all internal formatting and preprocessing
            response = self.model.infer(
                tokenizer=self.tokenizer,
                prompt=prompt,  # ✅ Use original prompt (no manual formatting!)
                image_file=image,  # PIL Image (official API accepts this)
                base_size=self.config.base_size,
                image_size=self.config.image_size,
                crop_mode=self.config.crop_mode,
            )

            return response

        finally:
            # Clear CUDA cache to free memory
            if self._device == "cuda":
                torch.cuda.empty_cache()

    @torch.no_grad()
    def infer_structure(self, page_image: Image.Image, page_num: int) -> PageStructure:
        """
        Pass 1: Analyze page structure with <|grounding|> mode.

        Detects all elements with bounding boxes and types.

        Args:
            page_image: PIL Image of the page
            page_num: Page number (1-indexed)

        Returns:
            PageStructure with detected elements
        """
        print(f"  Pass 1: Analyzing page {page_num} structure...")

        # Run inference with structure analysis prompt
        response = self.infer(page_image, STRUCTURE_ANALYSIS_PROMPT)

        # Parse JSON response
        try:
            result = json.loads(response)
        except json.JSONDecodeError as e:
            print(f"⚠️ Warning: Failed to parse Pass 1 JSON response: {e}")
            print(f"Raw response: {response[:500]}...")
            return PageStructure(page_num=page_num, elements=[], raw_response=response)

        # Convert to ElementDetection objects
        elements = []
        for idx, elem_data in enumerate(result.get("elements", [])):
            try:
                element_type = ElementType(elem_data["element_type"])
                bbox_coords = elem_data["bbox"]

                detection = ElementDetection(
                    element_id=elem_data.get("element_id", f"e{idx}"),
                    element_type=element_type,
                    bbox=BoundingBox(
                        x1=bbox_coords[0],
                        y1=bbox_coords[1],
                        x2=bbox_coords[2],
                        y2=bbox_coords[3],
                        page=page_num,
                    ),
                    confidence=elem_data.get("confidence", 1.0),
                    text_preview=elem_data.get("text_preview"),
                )
                elements.append(detection)
            except (KeyError, ValueError) as e:
                print(f"⚠️ Warning: Skipping invalid element {idx}: {e}")
                continue

        print(f"  ✅ Detected {len(elements)} elements on page {page_num}")

        return PageStructure(
            page_num=page_num,
            elements=elements,
            raw_response=response,
        )

    @torch.no_grad()
    def infer_element(
        self,
        cropped_image: Image.Image,
        element_type: str,
        element_id: str,
        context: str = "",
    ) -> ElementAnalysis:
        """
        Pass 2: Analyze specific element in detail.

        Extracts [항목], [키워드], [자연어 요약] for the element.

        Args:
            cropped_image: Cropped PIL Image of the element
            element_type: Element type string ('table', 'graph', etc.)
            element_id: Unique element identifier
            context: Surrounding text context

        Returns:
            ElementAnalysis with extracted data
        """
        # Get element-specific prompt
        prompt = get_element_prompt(element_type, context)

        # Run inference
        response = self.infer(cropped_image, prompt)

        # Parse JSON response
        try:
            result = json.loads(response)
        except json.JSONDecodeError as e:
            print(f"⚠️ Warning: Failed to parse Pass 2 JSON for {element_id}: {e}")
            print(f"Raw response: {response[:500]}...")
            return ElementAnalysis(
                element_id=element_id,
                element_type=ElementType(element_type),
                raw_response=response,
            )

        # Extract common fields
        analysis = ElementAnalysis(
            element_id=element_id,
            element_type=ElementType(element_type),
            items=result.get("items", []),
            keywords=result.get("keywords", []),
            summary=result.get("summary"),
            structured_data=result,  # Store full result for type-specific data
            raw_response=response,
        )

        return analysis

    def unload(self) -> None:
        """Unload model to free memory."""
        if self.model is not None:
            del self.model
            del self.tokenizer
            self.model = None
            self.tokenizer = None

            if self._device == "cuda":
                torch.cuda.empty_cache()

            print("✅ Model unloaded and CUDA cache cleared")
