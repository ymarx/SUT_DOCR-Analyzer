"""
DeepSeek-OCR vLLM engine for 2-Pass Hybrid pipeline.

Key features:
- vLLM LLM() for fast batch inference
- 2-Pass strategy: Pass 1 (structure) + Pass 2 (element analysis)
- Batch processing for parallel execution
- Memory-efficient with PagedAttention
"""

import os
import json
import torch
from typing import List, Dict, Any, Optional
from PIL import Image
from vllm import LLM, SamplingParams
from vllm.model_executor.models.registry import ModelRegistry
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

# Import our custom processors
from .image_processor import DeepseekOCRProcessor
from .logits_processor import NoRepeatNGramLogitsProcessor
from ..core.config import Config
from ..core.types import PageStructure, ElementDetection, ElementAnalysis, ElementType, BoundingBox
from .prompts import STRUCTURE_ANALYSIS_PROMPT, get_element_prompt


class DeepSeekVLLMEngine:
    """
    DeepSeek-OCR vLLM inference engine for 2-Pass Hybrid pipeline.

    Pass 1: Batch structure analysis (all pages simultaneously)
    Pass 2: Batch element analysis (all elements simultaneously)

    Optimized for RTX 4090 (24GB) with high concurrency.
    """

    def __init__(self, config: Config):
        """
        Initialize DeepSeek-OCR vLLM engine.

        Args:
            config: Configuration with vLLM settings
        """
        self.config = config
        self.llm = None
        self.processor = None
        self.sampling_params = None
        self._device = None

    def _load_model(self) -> None:
        """Lazy load vLLM model and processor."""
        if self.llm is not None:
            return

        print(f"Loading DeepSeek-OCR vLLM model from {self.config.cache_dir}...")

        # Register DeepSeek-OCR model architecture
        try:
            from deepseek_ocr import DeepseekOCRForCausalLM
            ModelRegistry.register_model("DeepseekOCRForCausalLM", DeepseekOCRForCausalLM)
        except ImportError:
            print("⚠️ Warning: deepseek_ocr module not found. Using default registration.")

        # Set CUDA environment
        if self.config.device == "cuda":
            os.environ["CUDA_VISIBLE_DEVICES"] = "0"
            os.environ["VLLM_USE_V1"] = "0"
            if torch.version.cuda == "11.8":
                os.environ["TRITON_PTXAS_PATH"] = "/usr/local/cuda-11.8/bin/ptxas"

        # Initialize vLLM LLM
        self.llm = LLM(
            model=self.config.model_name,
            hf_overrides={"architectures": ["DeepseekOCRForCausalLM"]},
            block_size=256,
            enforce_eager=False,
            trust_remote_code=True,
            max_model_len=8192,
            swap_space=0,
            max_num_seqs=self.config.max_num_seqs,  # RTX 4090: 100, RTX 4060: 10
            tensor_parallel_size=1,
            gpu_memory_utilization=self.config.gpu_memory_utilization,  # 0.9 for 4090
            disable_mm_preprocessor_cache=True,
            download_dir=self.config.cache_dir,
        )

        # Initialize processor
        self.processor = DeepseekOCRProcessor(
            tokenizer=None,  # vLLM handles tokenization internally
            image_size=self.config.image_size,
            base_size=self.config.base_size,
            min_crops=2,
            max_crops=6,
        )

        # Setup sampling parameters
        logits_processors = [
            NoRepeatNGramLogitsProcessor(
                ngram_size=20,
                window_size=50,
                whitelist_token_ids={128821, 128822},  # <td>, </td>
            )
        ]

        self.sampling_params = SamplingParams(
            temperature=0.0,  # Greedy decoding for consistency
            max_tokens=8192,
            logits_processors=logits_processors,
            skip_special_tokens=False,
            include_stop_str_in_output=True,
        )

        self._device = self.config.device
        print(f"✅ vLLM model loaded on {self._device} with {self.config.dtype}")
        print(f"   max_num_seqs={self.config.max_num_seqs}, gpu_utilization={self.config.gpu_memory_utilization}")

    def _preprocess_image(self, image: Image.Image, prompt: str) -> Dict[str, Any]:
        """
        Preprocess single image for vLLM.

        Args:
            image: PIL Image
            prompt: Prompt string with <image> placeholder

        Returns:
            Dict with prompt and multi_modal_data
        """
        # Use processor to tokenize image
        processed_data = self.processor.tokenize_with_images(
            images=[image],
            prompt=prompt,
            bos=True,
            eos=True,
            cropping=self.config.crop_mode,
        )

        return {
            "prompt": prompt,
            "multi_modal_data": {"image": processed_data},
        }

    def infer_batch(
        self,
        images: List[Image.Image],
        prompts: List[str],
        num_workers: int = None,
    ) -> List[str]:
        """
        Batch inference with parallel preprocessing.

        Args:
            images: List of PIL Images
            prompts: List of prompt strings (one per image)
            num_workers: Number of preprocessing workers (default: config.num_workers)

        Returns:
            List of response strings
        """
        self._load_model()

        if num_workers is None:
            num_workers = getattr(self.config, "num_workers", 64)

        # Parallel preprocessing
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            batch_inputs = list(
                tqdm(
                    executor.map(
                        lambda img_prompt: self._preprocess_image(*img_prompt),
                        zip(images, prompts),
                    ),
                    total=len(images),
                    desc="Preprocessing images",
                )
            )

        # vLLM batch inference (single call for all images)
        print(f"Running vLLM batch inference ({len(batch_inputs)} images)...")

        try:
            outputs = self.llm.generate(batch_inputs, self.sampling_params)
        except RuntimeError as e:
            if "out of memory" in str(e).lower() or "oom" in str(e).lower():
                print(f"⚠️ OOM Error during batch inference. Try reducing max_num_seqs or batch size.")
                print(f"   Current: max_num_seqs={self.config.max_num_seqs}, batch_size={len(batch_inputs)}")
                raise RuntimeError(
                    f"vLLM OOM: {len(batch_inputs)} images exceeded GPU memory. "
                    f"Reduce max_num_seqs (current: {self.config.max_num_seqs}) or process fewer images."
                ) from e
            else:
                print(f"❌ vLLM inference error: {e}")
                raise RuntimeError(f"vLLM batch inference failed: {e}") from e
        except Exception as e:
            print(f"❌ Unexpected error during vLLM inference: {type(e).__name__}: {e}")
            raise RuntimeError(f"vLLM batch inference failed unexpectedly: {e}") from e

        # Extract responses
        responses = []
        for output in outputs:
            try:
                response = output.outputs[0].text

                # Clean up response (remove special tokens if needed)
                if "<｜end▁of▁sentence｜>" in response:
                    response = response.replace("<｜end▁of▁sentence｜>", "")

                responses.append(response)
            except (IndexError, AttributeError) as e:
                print(f"⚠️ Warning: Failed to extract response from output: {e}")
                responses.append("")  # Empty response as fallback

        # Clear CUDA cache
        if self._device == "cuda":
            torch.cuda.empty_cache()

        return responses

    def infer(self, image: Image.Image, prompt: str) -> str:
        """
        Single image inference (uses batch inference internally).

        Args:
            image: PIL Image
            prompt: Prompt string

        Returns:
            Response string
        """
        responses = self.infer_batch([image], [prompt])
        return responses[0]

    def infer_structure_batch(
        self, page_images: List[Image.Image], page_nums: List[int]
    ) -> List[PageStructure]:
        """
        Pass 1: Batch analyze page structure with <|grounding|> mode.

        Detects all elements with bounding boxes and types for multiple pages.

        Args:
            page_images: List of PIL Images (one per page)
            page_nums: List of page numbers (1-indexed)

        Returns:
            List of PageStructure with detected elements
        """
        print(f"  Pass 1: Analyzing {len(page_images)} pages structure (batch)...")

        # Same prompt for all pages (official grounding prompt)
        prompts = [STRUCTURE_ANALYSIS_PROMPT] * len(page_images)

        # Batch inference
        responses = self.infer_batch(page_images, prompts)

        # Parse responses
        structures = []
        for page_num, response in zip(page_nums, responses):
            try:
                # For now, return raw response (will be parsed by markdown_parser later)
                # This maintains compatibility with 2-Pass Hybrid strategy
                structures.append(
                    PageStructure(
                        page_num=page_num, elements=[], raw_response=response
                    )
                )
            except Exception as e:
                print(f"⚠️ Warning: Failed to process page {page_num}: {e}")
                structures.append(
                    PageStructure(page_num=page_num, elements=[], raw_response=response)
                )

        print(
            f"  ✅ Batch structure analysis complete ({len(structures)} pages processed)"
        )
        return structures

    def infer_structure(self, page_image: Image.Image, page_num: int) -> PageStructure:
        """
        Pass 1: Single page structure analysis (uses batch internally).

        Args:
            page_image: PIL Image of the page
            page_num: Page number (1-indexed)

        Returns:
            PageStructure with detected elements
        """
        structures = self.infer_structure_batch([page_image], [page_num])
        return structures[0]

    def infer_element_batch(
        self,
        cropped_images: List[Image.Image],
        element_types: List[str],
        element_ids: List[str],
        contexts: List[str],
    ) -> List[ElementAnalysis]:
        """
        Pass 2: Batch analyze specific elements in detail.

        Extracts [항목], [키워드], [자연어 요약] for multiple elements.

        Args:
            cropped_images: List of cropped PIL Images
            element_types: List of element type strings ('table', 'graph', etc.)
            element_ids: List of unique element identifiers
            contexts: List of surrounding text contexts

        Returns:
            List of ElementAnalysis with extracted data
        """
        print(
            f"  Pass 2: Analyzing {len(cropped_images)} elements in detail (batch)..."
        )

        # Generate element-specific prompts
        prompts = [
            get_element_prompt(elem_type, context)
            for elem_type, context in zip(element_types, contexts)
        ]

        # Batch inference
        responses = self.infer_batch(cropped_images, prompts)

        # Parse responses
        analyses = []
        for elem_id, elem_type, response in zip(element_ids, element_types, responses):
            try:
                # Try to parse as JSON
                result = json.loads(response)
                analysis = ElementAnalysis(
                    element_id=elem_id,
                    element_type=ElementType(elem_type),
                    items=result.get("items", []),
                    keywords=result.get("keywords", []),
                    summary=result.get("summary"),
                    structured_data=result,
                    raw_response=response,
                )
            except json.JSONDecodeError as e:
                print(f"⚠️ Warning: Failed to parse Pass 2 JSON for {elem_id}: {e}")
                analysis = ElementAnalysis(
                    element_id=elem_id,
                    element_type=ElementType(elem_type),
                    raw_response=response,
                )
            analyses.append(analysis)

        print(f"  ✅ Batch element analysis complete ({len(analyses)} elements processed)")
        return analyses

    def infer_element(
        self,
        cropped_image: Image.Image,
        element_type: str,
        element_id: str,
        context: str = "",
    ) -> ElementAnalysis:
        """
        Pass 2: Single element analysis (uses batch internally).

        Args:
            cropped_image: Cropped PIL Image of the element
            element_type: Element type string ('table', 'graph', etc.)
            element_id: Unique element identifier
            context: Surrounding text context

        Returns:
            ElementAnalysis with extracted data
        """
        analyses = self.infer_element_batch(
            [cropped_image], [element_type], [element_id], [context]
        )
        return analyses[0]

    def unload(self) -> None:
        """Unload model to free memory."""
        if self.llm is not None:
            del self.llm
            del self.processor
            del self.sampling_params
            self.llm = None
            self.processor = None
            self.sampling_params = None

            if self._device == "cuda":
                torch.cuda.empty_cache()

            print("✅ vLLM model unloaded and CUDA cache cleared")
