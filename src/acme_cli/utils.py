"""Utility helpers shared across the project."""

from __future__ import annotations

import re
import time
from contextlib import contextmanager
from typing import Callable, Iterable, Iterator


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    """Clamp *value* into the inclusive range ``[lower, upper]``."""
    return max(lower, min(upper, value))


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Return ``numerator / denominator`` guarding against division by zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def word_count(text: str | None) -> int:
    """Compute a simple word count for *text*."""
    if not text:
        return 0
    return len(re.findall(r"\b\w+\b", text))


def count_code_fences(text: str | None) -> int:
    """Count Markdown code fences in *text* (````` or indented blocks)."""
    if not text:
        return 0
    return text.count("```")


@contextmanager
def timed_operation() -> Iterator[Callable[[], int]]:
    """Context manager returning a callable that yields elapsed milliseconds."""
    start = time.perf_counter()

    def _elapsed() -> int:
        return int((time.perf_counter() - start) * 1000)

    try:
        yield _elapsed
    finally:
        pass


def contains_keywords(text: str | None, keywords: Iterable[str]) -> int:
    """Count occurrences of any *keywords* inside *text* (case-insensitive)."""
    if not text:
        return 0
    lowered = text.lower()
    return sum(lowered.count(keyword.lower()) for keyword in keywords)
