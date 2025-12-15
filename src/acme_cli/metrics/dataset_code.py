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
            score += 0.8
            if dataset_metadata.citation:
                score += 0.3
            if word_count(context.dataset_readme_text) > 200:
                score += 0.3
        elif dataset_urls:
            # Give higher scores for quality dataset platforms
            dataset_score = 0.0
            for url in dataset_urls:
                parsed = parse_artifact_url(url)
                if parsed.platform == "huggingface":
                    dataset_score = max(dataset_score, 1.0)  # Higher for HF datasets
                elif parsed.platform in {"github", "gitlab"}:
                    dataset_score = max(dataset_score, 0.7)
                else:
                    dataset_score = max(dataset_score, 0.5)
            score += dataset_score

        if code_urls:
            quality_bonus = 0.0
            for url in code_urls:
                parsed = parse_artifact_url(url)
                if parsed.platform in {"github", "gitlab"}:
                    quality_bonus = max(quality_bonus, 0.7)  # Higher for git repos
                elif parsed.platform == "huggingface":
                    quality_bonus = max(quality_bonus, 0.6)  # Higher for HF repos
                else:
                    quality_bonus = max(quality_bonus, 0.4)  # Higher for others
            score += quality_bonus

        # Additional boost points for comprehensive artifact availability
        bonus_points = 0.0

        # Boost for having both datasets and code
        if (dataset_metadata or dataset_urls) and code_urls:
            bonus_points += 0.2

        # Boost for multiple code repositories (shows maturity)
        if code_urls and len(code_urls) > 1:
            bonus_points += 0.1

        # Boost for multiple dataset sources (shows thoroughness)
        if dataset_urls and len(dataset_urls) > 1:
            bonus_points += 0.1

        # Boost for having model documentation
        if context.readme_text and len(context.readme_text.strip()) > 100:
            bonus_points += 0.15

        score += bonus_points
        return clamp(score)


__all__ = ["DatasetAndCodeMetric"]
