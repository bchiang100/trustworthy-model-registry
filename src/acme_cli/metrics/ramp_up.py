"""Ramp-up metric implementation."""

from __future__ import annotations

from acme_cli.llm import LlmEvaluator, LlmUnavailable
from acme_cli.metrics.base import Metric
from acme_cli.types import ModelContext
from acme_cli.utils import clamp, contains_keywords, count_code_fences, word_count


class RampUpMetric(Metric):
    name = "ramp_up_time"

    def __init__(self, llm: LlmEvaluator | None = None) -> None:
        self._llm = llm or LlmEvaluator()

    def compute(self, context: ModelContext) -> float:
        readme = context.readme_text
        if not readme:
            return 0.0

        heuristic_score = self._heuristic_score(readme)
        llm_score = None
        try:
            llm_score = self._llm.score_clarity(readme)
        except LlmUnavailable:
            llm_score = None

        if llm_score is None:
            return heuristic_score
        return clamp(0.5 * heuristic_score + 0.5 * llm_score)

    @staticmethod
    def _heuristic_score(readme: str) -> float:
        wc = word_count(readme)
        richness = clamp(wc / 1000.0)
        keyword_bonus = (
            0.1
            if contains_keywords(
                readme, ["installation", "usage", "quickstart", "example"]
            )
            else 0.0
        )
        code_bonus = min(0.2, count_code_fences(readme) * 0.05)
        return clamp(richness + keyword_bonus + code_bonus)


__all__ = ["RampUpMetric"]
