from __future__ import annotations

from acme_cli.metrics.base import Metric
from acme_cli.scoring_engine import ModelScorer, ScoreSummary
from acme_cli.types import EvaluationOutcome, LocalRepository, MetricResult, ModelContext, ModelMetadata, RepoFile, ScoreTarget


class _StubBuilder:
    def build(self, target: ScoreTarget) -> ModelContext:  # noqa: D401
        return ModelContext(
            target=target,
            model_metadata=ModelMetadata(
                repo_id="model",
                display_name="model",
                card_data={},
                downloads=None,
                likes=None,
                last_modified=None,
                tags=[],
                files=[RepoFile(path="README.md", size_bytes=10)],
                pipeline_tag=None,
                library_name=None,
            ),
            dataset_metadata=None,
            local_repo=LocalRepository(repo_id="model", repo_type="model", path=None),
            dataset_local_repo=None,
            readme_text="",
            dataset_readme_text=None,
            commit_authors=[],
            commit_total=0,
        )


class _StubMetric(Metric):
    name = "stub"

    def compute(self, context: ModelContext):  # noqa: D401
        return 1.0


def test_model_scorer_uses_builder() -> None:
    scorer = ModelScorer(context_builder=_StubBuilder(), metrics=[_StubMetric()])
    summary = scorer.score(ScoreTarget(model_url="model"))
    assert isinstance(summary, ScoreSummary)
    assert summary.outcome.metrics["stub"].value == 1.0
