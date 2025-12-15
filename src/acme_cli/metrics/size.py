"""Model size compatibility metric."""

from __future__ import annotations

import logging
from pathlib import Path

from acme_cli.metrics.base import Metric
from acme_cli.types import ModelContext, RepoFile

logger = logging.getLogger(__name__)

_THRESHOLDS = {
    "raspberry_pi": (500 * 1024 * 1024, 2 * 1024 * 1024 * 1024),  # 500MB - 2GB
    "jetson_nano": (2 * 1024 * 1024 * 1024, 8 * 1024 * 1024 * 1024),  # 2GB - 8GB
    "desktop_pc": (8 * 1024 * 1024 * 1024, 32 * 1024 * 1024 * 1024),  # 8GB - 32GB
    "aws_server": (32 * 1024 * 1024 * 1024, 100 * 1024 * 1024 * 1024),  # 32GB - 100GB
}

_WEIGHT_EXTENSIONS = (".bin", ".safetensors", ".pt", ".onnx", ".gguf", ".ggml")


class SizeMetric(Metric):
    name = "size_score"

    def compute(self, context: ModelContext) -> dict[str, float]:
        local_repo = context.local_repo
        total_bytes = 0

        # Try to get size from local files first
        if local_repo and local_repo.path:
            total_bytes = self._collect_weight_bytes(local_repo.path)

        # Try to get size from model metadata
        if total_bytes == 0 and context.model_metadata:
            total_bytes = self._collect_metadata_bytes(context.model_metadata.files)

        # Try to get size directly from Hugging Face API if we have a model URL
        if total_bytes == 0:
            total_bytes = self._get_hf_model_size(context)

        if total_bytes == 0:
            # Improved fallback logic based on model characteristics
            model_url = context.target.model_url or ""
            model_name = model_url.split("/")[-1].lower() if model_url else ""

            # Smart fallback based on model naming patterns
            if any(keyword in model_name for keyword in ["tiny", "small", "mini", "micro", "test"]):
                # Assume small test models are ~100MB - good for all hardware
                estimated_bytes = 100 * 1024 * 1024
            elif any(keyword in model_name for keyword in ["base", "medium"]):
                # Medium models ~1GB - good for jetson_nano and above
                estimated_bytes = 1 * 1024 * 1024 * 1024
            elif any(keyword in model_name for keyword in ["large", "xl"]):
                # Large models ~5GB - good for desktop and servers
                estimated_bytes = 5 * 1024 * 1024 * 1024
            else:
                # Unknown models - conservative estimate ~2GB
                estimated_bytes = 2 * 1024 * 1024 * 1024

            return {
                hardware: self._hardware_score(estimated_bytes, limits)
                for hardware, limits in _THRESHOLDS.items()
            }
        return {
            hardware: self._hardware_score(total_bytes, limits)
            for hardware, limits in _THRESHOLDS.items()
        }

    @staticmethod
    def _collect_weight_bytes(path: Path) -> int:
        total = 0
        for ext in _WEIGHT_EXTENSIONS:
            for file in path.rglob(f"*{ext}"):
                try:
                    total += file.stat().st_size
                except OSError:
                    continue
        return total

    @staticmethod
    def _hardware_score(total_bytes: int, limits: tuple[int, int]) -> float:
        sweet_spot, upper_bound = limits
        if total_bytes <= sweet_spot:
            return 1.0
        if total_bytes <= upper_bound:
            return 0.8
        if total_bytes <= upper_bound * 1.5:
            return 0.7
        if total_bytes <= upper_bound * 3.0:
            return 0.6
        return 0.5  # Default worst case score

    @staticmethod
    def _collect_metadata_bytes(files: list[RepoFile]) -> int:
        total = 0
        for file in files:
            if any(file.path.endswith(ext) for ext in _WEIGHT_EXTENSIONS):
                if file.size_bytes:
                    total += file.size_bytes
        return total

    def _get_hf_model_size(self, context: ModelContext) -> int:
        """Get model size directly from Hugging Face API."""
        try:
            # Extract model ID from the target URL
            model_url = context.target.model_url
            if not model_url or "huggingface.co" not in model_url:
                return 0

            # Parse the model ID from URL like https://huggingface.co/microsoft/DialoGPT-medium
            parts = model_url.split("/")
            if len(parts) < 2:
                return 0
            model_id = "/".join(parts[-2:])  # Get last two parts (org/model)

            # Use Hugging Face API to get model info
            from huggingface_hub import HfApi
            api = HfApi()

            try:
                # Use repo_info with files_metadata=True to get actual file sizes (instead of api.model_info(model_id)) didnt include file sizes beforei
                model_info = api.repo_info(model_id, files_metadata=True)
                total_size = 0

                for sibling in model_info.siblings:
                    if sibling.size and any(sibling.rfilename.endswith(ext) for ext in _WEIGHT_EXTENSIONS):
                        total_size += sibling.size

                return total_size

            except Exception:
                return 0

        except Exception:
            return 0


__all__ = ["SizeMetric"]
