"""Dataset and code availability metric."""

from __future__ import annotations

from acme_cli.metrics.base import Metric
from acme_cli.types import ModelContext
from acme_cli.urls import parse_artifact_url
from acme_cli.utils import clamp, word_count


class DatasetAndCodeMetric(Metric):
    name = "dataset_and_code_score"

    def compute(self, context: ModelContext) -> float:
        score = 0.0
        dataset_metadata = context.dataset_metadata
        dataset_urls = context.target.dataset_urls
        code_urls = context.target.code_urls

        if dataset_metadata:
            score += 0.6
            if dataset_metadata.citation:
                score += 0.2
            if word_count(context.dataset_readme_text) > 200:
                score += 0.2
        elif dataset_urls:
            score += 0.3  # at least referenced even if not on Hugging Face

        if code_urls:
            quality_bonus = 0.0
            for url in code_urls:
                parsed = parse_artifact_url(url)
                if parsed.platform in {"github", "gitlab"}:
                    quality_bonus = max(quality_bonus, 0.4)
                elif parsed.platform == "huggingface":
                    quality_bonus = max(quality_bonus, 0.3)
                else:
                    quality_bonus = max(quality_bonus, 0.2)
            score += quality_bonus

        return clamp(score)


__all__ = ["DatasetAndCodeMetric"]
