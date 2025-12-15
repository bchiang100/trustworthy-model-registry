"""Performance claims metric using LLM assistance."""

from __future__ import annotations

from acme_cli.llm import LlmEvaluator, LlmUnavailable
from acme_cli.metrics.base import Metric
from acme_cli.types import ModelContext
from acme_cli.utils import clamp, contains_keywords


class PerformanceClaimsMetric(Metric):
    name = "performance_claims"

    def __init__(self, llm: LlmEvaluator | None = None) -> None:
        self._llm = llm or LlmEvaluator()

    def compute(self, context: ModelContext) -> float:
        readme = context.readme_text
        if not readme:
            return 0.0
        heuristic = self._heuristic_score(readme)
        llm_score = None
        try:
            llm_score = self._llm.score_performance_claims(readme)
        except LlmUnavailable:
            llm_score = None
        if llm_score is None:
            return heuristic
        return clamp(0.4 * heuristic + 0.6 * llm_score)

    @staticmethod
    def _heuristic_score(readme: str) -> float:
        keywords = [
            "accuracy",
            "f1",
            "precision",
            "recall",
            "benchmark",
            "eval",
            "evaluation",
            "leaderboard",
            "performance",
            "score",
            "metric",
            "test",
            "validation",
        ]
        count = contains_keywords(readme, keywords)
        # More generous scoring: 5 keywords = 1.0 score instead of 10
        return clamp(count / 5.0)


__all__ = ["PerformanceClaimsMetric"]
