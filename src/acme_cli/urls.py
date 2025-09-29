"""Utilities for parsing and classifying artifact URLs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse


@dataclass(slots=True)
class ParsedUrl:
    """Structured representation of an artifact URL."""

    raw: str
    platform: Literal["huggingface", "github", "gitlab", "other"]
    kind: Literal["model", "dataset", "code", "unknown"]
    repo_id: str | None


_HF_HOSTS = {"huggingface.co"}
_GITHUB_HOSTS = {"github.com"}
_GITLAB_HOSTS = {"gitlab.com"}


def parse_artifact_url(url: str) -> ParsedUrl:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")

    if host in _HF_HOSTS:
        parts = path.split("/")
        if not parts or parts == ['']:
            return ParsedUrl(url, "huggingface", "unknown", None)
        if parts[0] == "datasets" and len(parts) >= 3:
            repo_id = f"{parts[1]}/{parts[2]}"
            return ParsedUrl(url, "huggingface", "dataset", repo_id)
        if parts[0] == "datasets" and len(parts) == 2:
            repo_id = parts[1]
            return ParsedUrl(url, "huggingface", "dataset", repo_id)
        if parts[0] == "models" and len(parts) >= 3:
            repo_id = f"{parts[1]}/{parts[2]}"
            return ParsedUrl(url, "huggingface", "model", repo_id)
        if len(parts) >= 2:
            repo_id = f"{parts[0]}/{parts[1]}"
            return ParsedUrl(url, "huggingface", "model", repo_id)
        if len(parts) == 1:
            return ParsedUrl(url, "huggingface", "model", parts[0])
        return ParsedUrl(url, "huggingface", "unknown", None)

    if host in _GITHUB_HOSTS:
        parts = path.split("/")
        if len(parts) >= 2:
            repo_id = f"{parts[0]}/{parts[1]}"
            return ParsedUrl(url, "github", "code", repo_id)
        return ParsedUrl(url, "github", "code", None)

    if host in _GITLAB_HOSTS:
        parts = path.split("/")
        if len(parts) >= 2:
            repo_id = f"{parts[0]}/{parts[1]}"
            return ParsedUrl(url, "gitlab", "code", repo_id)
        return ParsedUrl(url, "gitlab", "code", None)

    return ParsedUrl(url, "other", "unknown", None)


def is_model_url(url: str) -> bool:
    return parse_artifact_url(url).kind == "model"


def is_dataset_url(url: str) -> bool:
    return parse_artifact_url(url).kind == "dataset"


def is_code_url(url: str) -> bool:
    parsed = parse_artifact_url(url)
    return parsed.kind == "code" or parsed.platform in {"github", "gitlab"}


__all__ = [
    "ParsedUrl",
    "parse_artifact_url",
    "is_model_url",
    "is_dataset_url",
    "is_code_url",
]
