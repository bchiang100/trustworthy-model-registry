"""Bus factor metric based on commit authorship data."""

from __future__ import annotations

from acme_cli.metrics.base import Metric
from acme_cli.types import ModelContext
from acme_cli.utils import clamp, safe_div


class BusFactorMetric(Metric):
    name = "bus_factor"

    def compute(self, context: ModelContext) -> float:
        unique_authors = len({author.lower() for author in context.commit_authors})

        if unique_authors == 0:
            fallback_score = 0.2  # base fallback

            # Check for organization indicators
            readme_text = context.readme_text.lower() if context.readme_text else ""
            model_metadata = context.model_metadata
            model_name = ""
            if model_metadata:
                try:
                    model_name = getattr(model_metadata, "id", "").lower()
                except:
                    model_name = ""

            # High reputation organizations
            if any(
                org in readme_text + " " + model_name
                for org in [
                    "anthropic",
                    "openai",
                    "google",
                    "microsoft",
                    "meta",
                    "huggingface",
                ]
            ):
                fallback_score = 0.6
            # Medium reputation organizations
            elif any(
                org in readme_text + " " + model_name
                for org in ["deepseek", "alibaba", "tongyi", "mistral", "cohere"]
            ):
                fallback_score = 0.5
            # Research institutions or quality indicators
            elif any(
                indicator in readme_text
                for indicator in [
                    "stanford",
                    "mit",
                    "berkeley",
                    "research",
                    "university",
                    "institute",
                ]
            ):
                fallback_score = 0.4
            # Popular models based on downloads/likes
            elif model_metadata and (
                getattr(model_metadata, "downloads", 0) > 10000
                or getattr(model_metadata, "likes", 0) > 100
            ):
                fallback_score = 0.3

            return fallback_score

        # Original calculation when commit data is available
        diversity = clamp(unique_authors / 5.0)
        activity = clamp(context.commit_total / 40.0)
        balance = safe_div(unique_authors, context.commit_total, default=1.0)
        score = 0.6 * diversity + 0.3 * activity + 0.1 * clamp(balance)
        return clamp(score)


__all__ = ["BusFactorMetric"]
