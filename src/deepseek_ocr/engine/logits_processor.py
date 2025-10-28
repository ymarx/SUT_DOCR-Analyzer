"""
NoRepeatNGramLogitsProcessor for DeepSeek-OCR vLLM.

Prevents repetitive n-gram patterns in generated output.
Based on official DeepSeek-OCR-vllm/process/ngram_norepeat.py
"""

from typing import List, Set
import torch
from transformers import LogitsProcessor


class NoRepeatNGramLogitsProcessor(LogitsProcessor):
    """
    Logits processor that prevents repetitive n-gram patterns.

    Critical for table generation to avoid infinite loops like:
    <td>data</td><td>data</td><td>data</td>...

    Whitelist tokens (e.g., <td>, </td>) are allowed to repeat.
    """

    def __init__(
        self,
        ngram_size: int,
        window_size: int = 100,
        whitelist_token_ids: Set[int] = None,
    ):
        """
        Initialize no-repeat n-gram processor.

        Args:
            ngram_size: Size of n-gram to check (e.g., 20)
            window_size: Sliding window size to search for repeats (e.g., 50)
            whitelist_token_ids: Token IDs allowed to repeat (e.g., {128821, 128822} for <td>, </td>)

        Raises:
            ValueError: If ngram_size or window_size is invalid
        """
        if not isinstance(ngram_size, int) or ngram_size <= 0:
            raise ValueError(
                f"`ngram_size` must be a strictly positive integer, got {ngram_size}"
            )
        if not isinstance(window_size, int) or window_size <= 0:
            raise ValueError(
                f"`window_size` must be a strictly positive integer, got {window_size}"
            )

        self.ngram_size = ngram_size
        self.window_size = window_size
        self.whitelist_token_ids = whitelist_token_ids or set()

    def __call__(
        self, input_ids: List[int], scores: torch.FloatTensor
    ) -> torch.FloatTensor:
        """
        Process logits to ban repetitive n-grams.

        Args:
            input_ids: List of generated token IDs so far
            scores: Logits tensor for next token prediction

        Returns:
            Modified logits with banned tokens set to -inf
        """
        # Not enough tokens to form n-gram
        if len(input_ids) < self.ngram_size:
            return scores

        # Current prefix: last (ngram_size - 1) tokens
        current_prefix = tuple(input_ids[-(self.ngram_size - 1) :])

        # Search window: last window_size tokens
        search_start = max(0, len(input_ids) - self.window_size)
        search_end = len(input_ids) - self.ngram_size + 1

        # Find all n-grams that match current prefix
        banned_tokens = set()
        for i in range(search_start, search_end):
            ngram = tuple(input_ids[i : i + self.ngram_size])
            if ngram[:-1] == current_prefix:
                # Ban the last token of matching n-gram
                banned_tokens.add(ngram[-1])

        # Remove whitelisted tokens from ban list
        banned_tokens = banned_tokens - self.whitelist_token_ids

        # Apply bans
        if banned_tokens:
            scores = scores.clone()
            for token in banned_tokens:
                scores[token] = -float("inf")

        return scores
