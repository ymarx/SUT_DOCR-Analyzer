"""
DeepSeek-OCR image preprocessing for vLLM.

Based on official DeepSeek-OCR-vllm/process/image_process.py
Adapted for our 2-Pass pipeline architecture.
"""

import math
from typing import List, Tuple, Optional
import torch
import torchvision.transforms as T
from PIL import Image, ImageOps
from transformers import AutoTokenizer, ProcessorMixin

# Default configuration (can be overridden by Config)
DEFAULT_IMAGE_SIZE = 640
DEFAULT_BASE_SIZE = 1024
DEFAULT_MIN_CROPS = 2
DEFAULT_MAX_CROPS = 6
DEFAULT_IMAGE_MEAN = (0.5, 0.5, 0.5)
DEFAULT_IMAGE_STD = (0.5, 0.5, 0.5)


def find_closest_aspect_ratio(
    aspect_ratio: float,
    target_ratios: List[Tuple[int, int]],
    width: int,
    height: int,
    image_size: int,
) -> Tuple[int, int]:
    """
    Find the closest aspect ratio from target ratios.

    Args:
        aspect_ratio: Original image aspect ratio (width / height)
        target_ratios: List of candidate (width_tiles, height_tiles)
        width: Original image width
        height: Original image height
        image_size: Crop tile size (e.g., 640)

    Returns:
        Best matching (width_tiles, height_tiles)
    """
    best_ratio_diff = float("inf")
    best_ratio = (1, 1)
    area = width * height

    for ratio in target_ratios:
        target_aspect_ratio = ratio[0] / ratio[1]
        ratio_diff = abs(aspect_ratio - target_aspect_ratio)

        if ratio_diff < best_ratio_diff:
            best_ratio_diff = ratio_diff
            best_ratio = ratio
        elif ratio_diff == best_ratio_diff:
            # If aspect ratio is similar, prefer the one that covers more area
            if area > 0.5 * image_size * image_size * ratio[0] * ratio[1]:
                best_ratio = ratio

    return best_ratio


def count_tiles(
    orig_width: int,
    orig_height: int,
    min_num: int = DEFAULT_MIN_CROPS,
    max_num: int = DEFAULT_MAX_CROPS,
    image_size: int = DEFAULT_IMAGE_SIZE,
    use_thumbnail: bool = False,
) -> Tuple[int, int]:
    """
    Calculate optimal tile configuration for image.

    Args:
        orig_width: Original image width
        orig_height: Original image height
        min_num: Minimum number of tiles
        max_num: Maximum number of tiles
        image_size: Crop tile size
        use_thumbnail: Whether to add thumbnail

    Returns:
        (width_tiles, height_tiles)
    """
    aspect_ratio = orig_width / orig_height

    # Generate all valid tile configurations
    target_ratios = set(
        (i, j)
        for n in range(min_num, max_num + 1)
        for i in range(1, n + 1)
        for j in range(1, n + 1)
        if i * j <= max_num and i * j >= min_num
    )
    target_ratios = sorted(target_ratios, key=lambda x: x[0] * x[1])

    return find_closest_aspect_ratio(
        aspect_ratio, target_ratios, orig_width, orig_height, image_size
    )


def dynamic_preprocess(
    image: Image.Image,
    min_num: int = DEFAULT_MIN_CROPS,
    max_num: int = DEFAULT_MAX_CROPS,
    image_size: int = DEFAULT_IMAGE_SIZE,
    use_thumbnail: bool = False,
) -> Tuple[List[Image.Image], Tuple[int, int]]:
    """
    Dynamic preprocessing: crop image into tiles based on aspect ratio.

    Official "Gundam mode" - resizes image to tile grid and crops into tiles.

    Args:
        image: PIL Image
        min_num: Minimum number of tiles
        max_num: Maximum number of tiles
        image_size: Crop tile size (e.g., 640)
        use_thumbnail: Whether to add thumbnail

    Returns:
        (List of cropped images, (width_tiles, height_tiles))
    """
    orig_width, orig_height = image.size
    aspect_ratio = orig_width / orig_height

    # Generate all valid tile configurations
    target_ratios = set(
        (i, j)
        for n in range(min_num, max_num + 1)
        for i in range(1, n + 1)
        for j in range(1, n + 1)
        if i * j <= max_num and i * j >= min_num
    )
    target_ratios = sorted(target_ratios, key=lambda x: x[0] * x[1])

    # Find closest aspect ratio
    target_aspect_ratio = find_closest_aspect_ratio(
        aspect_ratio, target_ratios, orig_width, orig_height, image_size
    )

    # Calculate target dimensions
    target_width = image_size * target_aspect_ratio[0]
    target_height = image_size * target_aspect_ratio[1]
    blocks = target_aspect_ratio[0] * target_aspect_ratio[1]

    # Resize image to tile grid
    resized_img = image.resize((target_width, target_height))

    # Crop into tiles
    processed_images = []
    for i in range(blocks):
        box = (
            (i % (target_width // image_size)) * image_size,
            (i // (target_width // image_size)) * image_size,
            ((i % (target_width // image_size)) + 1) * image_size,
            ((i // (target_width // image_size)) + 1) * image_size,
        )
        split_img = resized_img.crop(box)
        processed_images.append(split_img)

    assert len(processed_images) == blocks

    # Add thumbnail if requested
    if use_thumbnail and len(processed_images) != 1:
        thumbnail_img = image.resize((image_size, image_size))
        processed_images.append(thumbnail_img)

    return processed_images, target_aspect_ratio


class ImageTransform:
    """
    Image transformation pipeline for DeepSeek-OCR.

    Applies ToTensor + Normalize (optional).
    """

    def __init__(
        self,
        mean: Tuple[float, float, float] = DEFAULT_IMAGE_MEAN,
        std: Tuple[float, float, float] = DEFAULT_IMAGE_STD,
        normalize: bool = True,
    ):
        self.mean = mean
        self.std = std
        self.normalize = normalize

        transform_pipelines = [T.ToTensor()]

        if normalize:
            transform_pipelines.append(T.Normalize(mean, std))

        self.transform = T.Compose(transform_pipelines)

    def __call__(self, pil_img: Image.Image) -> torch.Tensor:
        """Transform PIL Image to normalized tensor."""
        return self.transform(pil_img)


class DeepseekOCRProcessor(ProcessorMixin):
    """
    DeepSeek-OCR image processor for vLLM.

    Handles:
    - Dynamic preprocessing (cropping into tiles)
    - Image tokenization with <image> placeholders
    - Spatial crop ratio calculation
    - Multi-modal data preparation for vLLM
    """

    tokenizer_class = ("LlamaTokenizer", "LlamaTokenizerFast")
    attributes = ["tokenizer"]

    def __init__(
        self,
        tokenizer: Optional[AutoTokenizer] = None,
        image_size: int = DEFAULT_IMAGE_SIZE,
        base_size: int = DEFAULT_BASE_SIZE,
        min_crops: int = DEFAULT_MIN_CROPS,
        max_crops: int = DEFAULT_MAX_CROPS,
        patch_size: int = 16,
        downsample_ratio: int = 4,
        image_mean: Tuple[float, float, float] = DEFAULT_IMAGE_MEAN,
        image_std: Tuple[float, float, float] = DEFAULT_IMAGE_STD,
        normalize: bool = True,
        image_token: str = "<image>",
        pad_token: str = "<｜▁pad▁｜>",
        ignore_id: int = -100,
        **kwargs,
    ):
        """
        Initialize DeepSeek-OCR processor.

        Args:
            tokenizer: LlamaTokenizer instance (optional, can be None for vLLM)
            image_size: Crop tile size (640 for Gundam mode)
            base_size: Global view size (1024 for Gundam mode)
            min_crops: Minimum number of tiles
            max_crops: Maximum number of tiles
            patch_size: Vision encoder patch size (16)
            downsample_ratio: Downsampling ratio (4)
            image_mean: Normalization mean
            image_std: Normalization std
            normalize: Whether to normalize
            image_token: Image placeholder token
            pad_token: Padding token
            ignore_id: Ignore ID for labels (-100)
        """
        self.image_size = image_size
        self.base_size = base_size
        self.min_crops = min_crops
        self.max_crops = max_crops
        self.patch_size = patch_size
        self.downsample_ratio = downsample_ratio
        self.image_mean = image_mean
        self.image_std = image_std
        self.normalize = normalize
        self.image_token = image_token
        self.pad_token = pad_token
        self.ignore_id = ignore_id

        self.image_transform = ImageTransform(
            mean=image_mean, std=image_std, normalize=normalize
        )

        # Tokenizer setup (can be None for vLLM)
        self.tokenizer = tokenizer
        if self.tokenizer is not None:
            self.tokenizer.padding_side = "left"

            # Add pad token if missing
            if self.tokenizer.pad_token is None:
                self.tokenizer.add_special_tokens({"pad_token": pad_token})

            self.image_token_id = self.tokenizer.vocab.get(image_token)
        else:
            # For vLLM, we don't need tokenizer in preprocessing
            self.image_token_id = None

        super().__init__(tokenizer, **kwargs)

    @property
    def bos_id(self):
        return self.tokenizer.bos_token_id if self.tokenizer else None

    @property
    def eos_id(self):
        return self.tokenizer.eos_token_id if self.tokenizer else None

    @property
    def pad_id(self):
        return self.tokenizer.pad_token_id if self.tokenizer else None

    def tokenize_with_images(
        self,
        images: List[Image.Image],
        prompt: str = "<image>\n<|grounding|>Convert the document to markdown.",
        bos: bool = True,
        eos: bool = True,
        cropping: bool = True,
    ):
        """
        Tokenize prompt with images for vLLM.

        This is the core preprocessing method that prepares multi-modal data
        for vLLM's LLM.generate() call.

        Args:
            images: List of PIL Images
            prompt: Prompt string with <image> placeholders
            bos: Add BOS token
            eos: Add EOS token
            cropping: Enable dynamic preprocessing (Gundam mode)

        Returns:
            List of tuples: [
                (
                    input_ids,           # torch.LongTensor
                    pixel_values,        # torch.FloatTensor (global views)
                    images_crop,         # torch.FloatTensor (cropped tiles)
                    images_seq_mask,     # torch.BoolTensor
                    images_spatial_crop, # torch.LongTensor (crop ratios)
                    num_image_tokens,    # List[int]
                    image_shapes         # List[Tuple[int, int]]
                )
            ]
        """
        assert prompt.count(self.image_token) == len(
            images
        ), f"Number of <image> tokens ({prompt.count(self.image_token)}) != number of images ({len(images)})"

        text_splits = prompt.split(self.image_token)
        images_list = []  # Global views
        images_crop_list = []  # Cropped tiles
        images_seq_mask = []  # Mask for image tokens
        images_spatial_crop = []  # (width_tiles, height_tiles) for each image
        image_shapes = []  # Original image shapes
        num_image_tokens = []  # Number of tokens per image
        tokenized_str = []  # Token IDs

        for text_sep, image in zip(text_splits, images):
            # Encode text before <image>
            if self.tokenizer:
                tokenized_sep = self.tokenizer.encode(
                    text_sep, add_special_tokens=False
                )
                tokenized_str += tokenized_sep
                images_seq_mask += [False] * len(tokenized_sep)

            image_shapes.append(image.size)

            # Determine crop strategy
            if image.size[0] <= 640 and image.size[1] <= 640:
                # Small image: no cropping
                crop_ratio = [1, 1]
            else:
                if cropping:
                    # Large image: dynamic preprocessing (Gundam mode)
                    images_crop_raw, crop_ratio = dynamic_preprocess(
                        image,
                        min_num=self.min_crops,
                        max_num=self.max_crops,
                        image_size=self.image_size,
                    )
                else:
                    crop_ratio = [1, 1]

            # Process global view (base_size x base_size)
            if self.image_size <= 640 and not cropping:
                # Directly resize small images
                image = image.resize((self.image_size, self.image_size))

            global_view = ImageOps.pad(
                image,
                (self.base_size, self.base_size),
                color=tuple(int(x * 255) for x in self.image_transform.mean),
            )
            images_list.append(self.image_transform(global_view))

            # Record spatial crop ratio
            num_width_tiles, num_height_tiles = crop_ratio
            images_spatial_crop.append([num_width_tiles, num_height_tiles])

            # Process cropped tiles (if any)
            if num_width_tiles > 1 or num_height_tiles > 1:
                for cropped_img in images_crop_raw:
                    images_crop_list.append(self.image_transform(cropped_img))

            # Add image tokens
            num_queries = math.ceil(
                (self.image_size // self.patch_size) / self.downsample_ratio
            )
            num_queries_base = math.ceil(
                (self.base_size // self.patch_size) / self.downsample_ratio
            )

            # Global view tokens
            if self.image_token_id:
                tokenized_image = (
                    [self.image_token_id] * num_queries_base + [self.image_token_id]
                ) * num_queries_base
                tokenized_image += [self.image_token_id]

                # Cropped tiles tokens
                if num_width_tiles > 1 or num_height_tiles > 1:
                    tokenized_image += (
                        [self.image_token_id] * (num_queries * num_width_tiles)
                        + [self.image_token_id]
                    ) * (num_queries * num_height_tiles)

                tokenized_str += tokenized_image
                images_seq_mask += [True] * len(tokenized_image)
                num_image_tokens.append(len(tokenized_image))

        # Process last text split (after last <image>)
        if self.tokenizer:
            tokenized_sep = self.tokenizer.encode(
                text_splits[-1], add_special_tokens=False
            )
            tokenized_str += tokenized_sep
            images_seq_mask += [False] * len(tokenized_sep)

            # Add BOS/EOS tokens
            if bos:
                tokenized_str = [self.bos_id] + tokenized_str
                images_seq_mask = [False] + images_seq_mask
            if eos:
                tokenized_str = tokenized_str + [self.eos_id]
                images_seq_mask = images_seq_mask + [False]

            # Prepare input_ids and target_ids
            masked_tokenized_str = [
                token if token != self.image_token_id else self.ignore_id
                for token in tokenized_str
            ]

            input_ids = torch.LongTensor(tokenized_str)
            target_ids = torch.LongTensor(masked_tokenized_str)
            images_seq_mask_tensor = torch.tensor(images_seq_mask, dtype=torch.bool)

            # Set ignore_id for image tokens
            target_ids[
                (input_ids < 0) | (input_ids == self.image_token_id)
            ] = self.ignore_id
            input_ids[input_ids < 0] = self.pad_id

            # Remove ending EOS for inference
            if eos:
                assert input_ids[-1] == self.eos_id
                input_ids = input_ids[:-1]
                target_ids = target_ids[:-1]
                images_seq_mask_tensor = images_seq_mask_tensor[:-1]

            input_ids = input_ids.unsqueeze(0)
        else:
            # For vLLM without tokenizer
            input_ids = None
            images_seq_mask_tensor = torch.tensor(images_seq_mask, dtype=torch.bool)

        # Stack pixel values
        if len(images_list) == 0:
            pixel_values = torch.zeros((1, 3, self.base_size, self.base_size))
            images_spatial_crop = torch.zeros((1, 2), dtype=torch.long)
            images_crop = torch.zeros((1, 3, self.image_size, self.image_size)).unsqueeze(
                0
            )
        else:
            pixel_values = torch.stack(images_list, dim=0)
            images_spatial_crop = torch.tensor(images_spatial_crop, dtype=torch.long)
            if images_crop_list:
                images_crop = torch.stack(images_crop_list, dim=0).unsqueeze(0)
            else:
                images_crop = torch.zeros(
                    (1, 3, self.image_size, self.image_size)
                ).unsqueeze(0)

        return [
            [
                input_ids,
                pixel_values,
                images_crop,
                images_seq_mask_tensor,
                images_spatial_crop,
                num_image_tokens,
                image_shapes,
            ]
        ]

    def __call__(
        self,
        *,
        prompt: str,
        images: List[Image.Image],
        cropping: bool = True,
        **kwargs,
    ):
        """
        Process images and prompt for vLLM.

        Wrapper around tokenize_with_images() for compatibility.
        """
        return self.tokenize_with_images(
            images=images, prompt=prompt, cropping=cropping
        )
