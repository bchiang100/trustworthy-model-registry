"""Model size compatibility metric."""

from __future__ import annotations

from pathlib import Path

from acme_cli.metrics.base import Metric
from acme_cli.types import ModelContext, RepoFile

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
        if local_repo and local_repo.path:
            total_bytes = self._collect_weight_bytes(local_repo.path)
        if total_bytes == 0 and context.model_metadata:
            total_bytes = self._collect_metadata_bytes(context.model_metadata.files)
        if total_bytes == 0:
            return {key: 0.2 for key in _THRESHOLDS}  # worst case (if size unknown)
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
            return 0.7
        if total_bytes <= upper_bound * 1.5:
            return 0.4
        if total_bytes <= upper_bound * 3.0:
            return 0.2
        return 0.1  # Default worst case score

    @staticmethod
    def _collect_metadata_bytes(files: list[RepoFile]) -> int:
        total = 0
        for file in files:
            if any(file.path.endswith(ext) for ext in _WEIGHT_EXTENSIONS):
                if file.size_bytes:
                    total += file.size_bytes
        return total


__all__ = ["SizeMetric"]
