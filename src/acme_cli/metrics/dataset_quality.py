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
            # If no metadata but we have dataset URLs, give some base quality score
            if context.target.dataset_urls:
                from acme_cli.urls import parse_artifact_url
                base_score = 0.0
                for url in context.target.dataset_urls:
                    parsed = parse_artifact_url(url)
                    if parsed.platform == "huggingface":
                        base_score = max(base_score, 0.6)  # HF datasets are generally good quality
                    elif parsed.platform in {"github", "gitlab"}:
                        base_score = max(base_score, 0.3)  # Code repos may have datasets
                    else:
                        base_score = max(base_score, 0.2)  # Other sources

                # Additional boost points even without metadata
                bonus_points = 0.0

                # Boost for multiple dataset sources
                if len(context.target.dataset_urls) > 1:
                    bonus_points += 0.1

                # Boost for having model documentation that might describe dataset
                if context.readme_text and len(context.readme_text.strip()) > 200:
                    bonus_points += 0.15

                # Boost for well-known dataset names in URLs
                url_text = " ".join(context.target.dataset_urls).lower()
                if any(name in url_text for name in ["wikitext", "squad", "glue", "imagenet", "coco"]):
                    bonus_points += 0.1

                return clamp(base_score + bonus_points)
            return 0.0

        size_component = self._size_component(metadata.size_bytes)
        documentation_component = clamp(word_count(context.dataset_readme_text) / 500)

        # Check for reputable organization
        organization_bonus = 0.0
        dataset_readme = (
            context.dataset_readme_text.lower() if context.dataset_readme_text else ""
        )
        dataset_id = getattr(metadata, "id", "").lower() if metadata else ""

        # Top-tier AI safety and research organizations
        if any(
            org in dataset_readme + " " + dataset_id
            for org in ["anthropic", "openai", "google", "microsoft", "meta"]
        ):
            organization_bonus = 1.0
        # High-quality AI companies and platforms
        elif any(
            org in dataset_readme + " " + dataset_id
            for org in ["huggingface", "deepseek", "alibaba", "tongyi"]
        ):
            organization_bonus = 0.9
        # Research institutions and quality dataset indicators
        elif any(
            indicator in dataset_readme + " " + dataset_id
            for indicator in [
                "stanford",
                "mit",
                "berkeley",
                "interviewer",
                "conversation",
                "instruction",
                "constitutional",
                "helpful",
                "harmless",
            ]
        ):
            organization_bonus = 0.8
        # General quality indicators for good datasets
        elif any(
            keyword in dataset_readme
            for keyword in [
                "evaluation",
                "benchmark",
                "curated",
                "annotated",
                "validated",
            ]
        ):
            organization_bonus = 0.6

        governance_component = 0.0
        license_values: list[str] = []
        if metadata.license:
            if isinstance(metadata.license, list):
                license_values = [str(value).lower() for value in metadata.license]
            else:
                license_values = [str(metadata.license).lower()]
        if any(value in _PERMISSIVE_DATASET_LICENSES for value in license_values):
            governance_component += 0.6  # Higher weight for good licenses
        if metadata.citation:
            governance_component += 0.4  # Higher weight for citations
        if metadata.tags:
            governance_component += min(0.3, len(metadata.tags) * 0.03)

        governance_component = clamp(governance_component)

        score = (
            0.15 * size_component
            + 0.15 * documentation_component
            + 0.2 * governance_component
            + 0.5 * organization_bonus
        )

        # Additional boost points for dataset quality indicators
        bonus_points = 0.0

        # Boost for comprehensive metadata
        if metadata.tags and len(metadata.tags) >= 3:
            bonus_points += 0.1  # Well-tagged datasets

        # Boost for good documentation length
        readme_length = len(context.dataset_readme_text or "")
        if readme_length > 500:
            bonus_points += 0.1
        elif readme_length > 1000:
            bonus_points += 0.15  # Extra boost for very detailed docs

        # Boost for recent updates (if available in metadata)
        if hasattr(metadata, 'last_modified') and metadata.last_modified:
            bonus_points += 0.05  # Actively maintained

        # Boost for having both license AND citation
        if metadata.citation and metadata.license:
            bonus_points += 0.1  # Well-governed dataset

        score += bonus_points
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
