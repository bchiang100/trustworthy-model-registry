"""
Core scoring workflow that orchestrates data gathering and metrics in ACME Registry.
"""

"""Core scoring workflow that orchestrates data gathering and metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from acme_cli.context import ContextBuilder
from acme_cli.metrics.base import Metric
from acme_cli.metrics.registry import build_metrics, evaluate_metrics
from acme_cli.types import EvaluationOutcome, MetricResult, ModelContext, ScoreTarget


@dataclass(slots=True)
class ScoreSummary:
    context: ModelContext
    outcome: EvaluationOutcome


class ModelScorer:
    """
    Coordinates context building and metric evaluation.
    Uses ContextBuilder and Metric implementations to score models.
    """

    def __init__(
        self,
        context_builder: ContextBuilder | None = None,
        metrics: Iterable[Metric] | None = None,
    ):
        self._context_builder = context_builder or ContextBuilder()
        self._metrics = list(metrics) if metrics else build_metrics()

    def score(self, target: ScoreTarget) -> ScoreSummary:
        """
        Score a model target by building its context and evaluating all metrics.
        Returns a ScoreSummary with context and evaluation outcome.
        """
        context = self._context_builder.build(target)
        outcome = evaluate_metrics(context, self._metrics)
        return ScoreSummary(context=context, outcome=outcome)


def get_metric_value(outcome: EvaluationOutcome, name: str) -> MetricResult | None:
    """
    Retrieve a metric value by name from an EvaluationOutcome.
    Returns the MetricResult or None if not found.
    """
    return outcome.metrics.get(name)


__all__ = ["ModelScorer", "ScoreSummary", "get_metric_value"]
