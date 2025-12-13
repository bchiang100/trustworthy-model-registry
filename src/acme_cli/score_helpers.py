"""Helpers to compute and cache full model scores for lineage/tree computations.

Provides a factory that returns a `score_fn(repo_id) -> float` which will
check a `ScoreRegistry` for cached metric results, and if missing will run
the standard scoring pipeline (via ModelScorer), persist the results, and
return an averaged numeric score in [0, 1].
"""

from __future__ import annotations

import logging
from typing import Callable, Mapping

from acme_cli.score_registry import (
    FileSystemScoreRegistry,
    InMemoryScoreRegistry,
    ScoreRegistry,
)
from acme_cli.scoring_engine import ModelScorer
from acme_cli.types import MetricResult, ScoreTarget

logger = logging.getLogger(__name__)


def _average_metric_results(results: Mapping[str, MetricResult]) -> float:
    """Average metric values from a MetricResult mapping.

    Mirrors the averaging behavior used by the TreeScoreMetric.
    """
    numeric_scores: list[float] = []
    for r in results.values():
        v = r.value
        if isinstance(v, dict):
            for sub in v.values():
                if isinstance(sub, (int, float)):
                    numeric_scores.append(float(sub))
        elif isinstance(v, (int, float)):
            numeric_scores.append(float(v))

    if not numeric_scores:
        return 0.5
    return sum(numeric_scores) / len(numeric_scores)


def make_score_fn(
    registry: ScoreRegistry | None = None,
    scorer: ModelScorer | None = None,
) -> Callable[[str], float]:
    """Create a scoring function usable by TreeScoreMetric.

    The returned function will:
      - Check `registry` for cached scores and return the averaged score if present.
      - Otherwise, run the full scoring pipeline via `scorer` for the repo_id,
        save the resulting MetricResult mapping into the registry, and return
        the averaged numeric score.

    Args:
        registry: Optional ScoreRegistry to persist scores. Defaults to a
                  filesystem-backed registry under the user's cache dir.
        scorer: Optional ModelScorer instance. If omitted, a new ModelScorer
                will be constructed on each call (cheap for re-use in most
                environments) but callers are encouraged to pass a shared
                ModelScorer for performance.
    """
    reg = registry or FileSystemScoreRegistry()
    shared_scorer = scorer or ModelScorer()

    def score_fn(repo_id: str) -> float:
        try:
            if reg.has_score(repo_id):
                cached = reg.get_score(repo_id)
                if cached:
                    return _average_metric_results(cached)

            # Compute scores on-demand
            target = ScoreTarget(model_url=f"https://huggingface.co/{repo_id}")
            summary = shared_scorer.score(target)
            outcome = summary.outcome

            # Persist results (outcome.metrics is dict[str, MetricResult])
            reg.save_score(repo_id, outcome.metrics)

            return _average_metric_results(outcome.metrics)
        except Exception as e:  # noqa: BLE001 - return conservative value on failure
            logger.warning(f"Failed to compute/cache score for {repo_id}: {e}")
            return 0.5

    return score_fn


__all__ = ["make_score_fn", "_average_metric_results"]
