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
            return 0.1  # assume very fragile when authorship data missing
        diversity = clamp(unique_authors / 5.0)
        activity = clamp(context.commit_total / 40.0)
        balance = safe_div(unique_authors, context.commit_total, default=1.0)
        score = 0.6 * diversity + 0.3 * activity + 0.1 * clamp(balance)
        return clamp(score)


__all__ = ["BusFactorMetric"]
