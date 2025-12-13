"""Score registry for storing and retrieving cached model evaluation scores."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Mapping, Optional

from acme_cli.types import MetricResult

logger = logging.getLogger(__name__)


class ScoreRegistry(ABC):
    """Abstract interface for storing and retrieving model scores."""

    @abstractmethod
    def get_score(self, repo_id: str) -> Mapping[str, MetricResult] | None:
        """Get cached scores for a model.

        Args:
            repo_id: The model repository ID

        Returns:
            Dictionary mapping metric names to MetricResult, or None if not cached
        """

    @abstractmethod
    def save_score(self, repo_id: str, scores: Mapping[str, MetricResult]) -> None:
        """Save scores for a model.

        Args:
            repo_id: The model repository ID
            scores: Dictionary mapping metric names to MetricResult
        """

    @abstractmethod
    def has_score(self, repo_id: str) -> bool:
        """Check if scores are cached for a model.

        Args:
            repo_id: The model repository ID

        Returns:
            True if scores are cached
        """


class FileSystemScoreRegistry(ScoreRegistry):
    """Simple file system-based score registry."""

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        """Initialize the registry.

        Args:
            cache_dir: Directory to store cached scores. If None, uses ~/.cache/trustworthy-registry
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "trustworthy-registry" / "scores"
        else:
            cache_dir = Path(cache_dir)

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, repo_id: str) -> Path:
        """Get the cache file path for a repository."""
        safe_name = repo_id.replace("/", "__")
        return self.cache_dir / f"{safe_name}.json"

    def get_score(self, repo_id: str) -> Mapping[str, MetricResult] | None:
        """Get cached scores for a model."""
        cache_path = self._get_cache_path(repo_id)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Reconstruct MetricResult objects
            results = {}
            for name, value_data in data.get("metrics", {}).items():
                results[name] = MetricResult(
                    name=name,
                    value=value_data["value"],
                    latency_ms=value_data.get("latency_ms", 0),
                )

            return results
        except Exception as e:
            logger.warning(f"Failed to load scores for {repo_id}: {e}")
            return None

    def save_score(self, repo_id: str, scores: Mapping[str, MetricResult]) -> None:
        """Save scores for a model."""
        cache_path = self._get_cache_path(repo_id)

        try:
            data = {
                "repo_id": repo_id,
                "metrics": {},
            }

            for name, result in scores.items():
                data["metrics"][name] = {
                    "value": result.value,
                    "latency_ms": result.latency_ms,
                }

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save scores for {repo_id}: {e}")

    def has_score(self, repo_id: str) -> bool:
        """Check if scores are cached for a model."""
        return self._get_cache_path(repo_id).exists()

    def clear(self) -> None:
        """Clear all cached scores."""
        if self.cache_dir.exists():
            import shutil

            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)


class InMemoryScoreRegistry(ScoreRegistry):
    """In-memory score registry for testing and transient caching."""

    def __init__(self) -> None:
        """Initialize the in-memory registry."""
        self._scores: dict[str, Mapping[str, MetricResult]] = {}

    def get_score(self, repo_id: str) -> Mapping[str, MetricResult] | None:
        """Get cached scores for a model."""
        return self._scores.get(repo_id)

    def save_score(self, repo_id: str, scores: Mapping[str, MetricResult]) -> None:
        """Save scores for a model."""
        self._scores[repo_id] = scores

    def has_score(self, repo_id: str) -> bool:
        """Check if scores are cached for a model."""
        return repo_id in self._scores

    def clear(self) -> None:
        """Clear all cached scores."""
        self._scores.clear()


__all__ = [
    "ScoreRegistry",
    "FileSystemScoreRegistry",
    "InMemoryScoreRegistry",
]
