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
        # Conservative scoring - require substantial documentation for high scores
        # 500 words gets 0.5, 1000 words gets 0.75, 2000+ words gets 1.0
        if wc < 100:
            richness = clamp(wc / 500.0)  # Very conservative for short docs
        elif wc < 500:
            richness = clamp(wc / 1000.0)  # Need substantial content
        else:
            richness = clamp(0.5 + (wc - 500) / 3000.0)  # Gradual increase to 1.0

        # Require multiple helpful keywords for bonus
        helpful_keywords = ["installation", "usage", "quickstart", "example", "how to", "getting started"]
        keyword_count = sum(1 for kw in helpful_keywords if kw in readme.lower())
        keyword_bonus = min(0.15, keyword_count * 0.05)  # Max 0.15, need 3+ keywords

        # Conservative code bonus
        code_bonus = min(0.2, count_code_fences(readme) * 0.04)  # Reduced bonus

        return clamp(richness + keyword_bonus + code_bonus)


__all__ = ["RampUpMetric"]
