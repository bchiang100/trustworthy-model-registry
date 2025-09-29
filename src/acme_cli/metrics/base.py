"""Metric interfaces and shared helpers."""
from __future__ import annotations

from abc import ABC, abstractmethod

from acme_cli.types import MetricResult, ModelContext
from acme_cli.utils import timed_operation


class Metric(ABC):
    """Abstract base class every metric implements."""

    name: str

    @abstractmethod
    def compute(self, context: ModelContext) -> float | dict[str, float]:
        """Compute the metric value for *context*."""

    def evaluate(self, context: ModelContext) -> MetricResult:
        with timed_operation() as elapsed:
            value = self.compute(context)
        return MetricResult(name=self.name, value=value, latency_ms=elapsed())


