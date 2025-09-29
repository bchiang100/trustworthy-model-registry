"""Utilities to derive the aggregated net score."""
from __future__ import annotations

from typing import Mapping

from acme_cli.types import EvaluationOutcome, MetricResult
from acme_cli.utils import clamp, safe_div, timed_operation


MetricWeights = Mapping[str, float]

_DEFAULT_WEIGHTS: dict[str, float] = {
    "ramp_up_time": 0.15,
    "bus_factor": 0.1,
    "performance_claims": 0.15,
    "license": 0.1,
    "size_score": 0.1,
    "dataset_and_code_score": 0.1,
    "dataset_quality": 0.15,
    "code_quality": 0.15,
}


def compute_net_score(outcome: EvaluationOutcome, weights: MetricWeights | None = None) -> MetricResult:
    weights = dict(weights or _DEFAULT_WEIGHTS)
    with timed_operation() as elapsed:
        score = 0.0
        for metric_name, weight in weights.items():
            metric = outcome.metrics.get(metric_name)
            if not metric:
                continue
            metric_value = _scalar_metric_value(metric)
            score += weight * clamp(metric_value)
        score = clamp(score)
    return MetricResult(name="net_score", value=score, latency_ms=elapsed())


def _scalar_metric_value(metric: MetricResult) -> float:
    value = metric.value
    if isinstance(value, Mapping):
        if not value:
            return 0.0
        total = sum(value.values())
        return clamp(safe_div(total, len(value)))
    return float(value)


__all__ = ["compute_net_score", "_DEFAULT_WEIGHTS"]
