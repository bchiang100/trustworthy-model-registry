"""
Load and organize scoring targets from user-supplied URL files for ACME Registry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator

from acme_cli.types import ScoreTarget
from acme_cli.urls import is_code_url, is_dataset_url, is_model_url


def parse_url_file(path: Path) -> list[ScoreTarget]:
    """
    Parse a file at *path* into a list of ScoreTarget objects.
    Groups datasets and code URLs with their corresponding model URLs.
    """
    lines = [line.strip() for line in _iter_lines(path) if line.strip()]
    dataset_buffer: list[str] = []
    code_buffer: list[str] = []
    targets: list[ScoreTarget] = []

    for line in lines:
        if is_dataset_url(line):
            dataset_buffer.append(line)
            continue
        if is_code_url(line):
            code_buffer.append(line)
            continue
        if is_model_url(line):
            targets.append(
                ScoreTarget(
                    model_url=line,
                    dataset_urls=list(dataset_buffer),
                    code_urls=list(code_buffer),
                )
            )
            dataset_buffer.clear()
            code_buffer.clear()
            continue
        # Unknown URLs are treated as supporting material for the upcoming model.
        dataset_buffer.append(line)

    return targets


def _iter_lines(path: Path) -> Iterator[str]:
    with path.open("r", encoding="utf-8") as handle:
        yield from handle


__all__ = ["parse_url_file"]
