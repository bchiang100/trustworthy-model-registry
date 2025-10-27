"""Dataset quality metric implementation."""

from __future__ import annotations

import math

from acme_cli.metrics.base import Metric
from acme_cli.types import ModelContext
from acme_cli.utils import clamp, word_count

_PERMISSIVE_DATASET_LICENSES = {
    "cc-by-4.0",
    "cc0-1.0",
    "odc-by",
    "odc-odbl",
    "mit",
    "apache-2.0",
}


class DatasetQualityMetric(Metric):
    name = "dataset_quality"

    def compute(self, context: ModelContext) -> float:
        metadata = context.dataset_metadata
        if not metadata:
            return 0.0

        size_component = self._size_component(metadata.size_bytes)
        documentation_component = clamp(word_count(context.dataset_readme_text) / 1500)
        governance_component = 0.0
        license_values: list[str] = []
        if metadata.license:
            if isinstance(metadata.license, list):
                license_values = [str(value).lower() for value in metadata.license]
            else:
                license_values = [str(metadata.license).lower()]
        if any(value in _PERMISSIVE_DATASET_LICENSES for value in license_values):
            governance_component += 0.5
        if metadata.citation:
            governance_component += 0.3
        if metadata.tags:
            governance_component += min(0.2, len(metadata.tags) * 0.02)

        governance_component = clamp(governance_component)
        score = (
            0.4 * size_component
            + 0.3 * documentation_component
            + 0.3 * governance_component
        )
        return clamp(score)

    @staticmethod
    def _size_component(size_bytes: int | None) -> float:
        if not size_bytes:
            return 0.2
        # Encourage datasets between 10MB and 10GB
        log_size = math.log10(size_bytes)
        if log_size < 6:  # < 1MB
            return 0.1
        if 6 <= log_size <= 8:
            return 0.6
        if 8 < log_size <= 10.5:
            return 0.9
        return 0.5


__all__ = ["DatasetQualityMetric"]
