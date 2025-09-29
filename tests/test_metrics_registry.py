from __future__ import annotations

from acme_cli.metrics.base import Metric
from acme_cli.metrics.registry import build_metrics, evaluate_metrics
from acme_cli.types import EvaluationOutcome, LocalRepository, ModelContext, ModelMetadata, RepoFile, ScoreTarget


class _ZeroMetric(Metric):
    name = "zero"

    def compute(self, context: ModelContext):  # noqa: D401
        return 0.0


class _FailMetric(Metric):
    name = "fail"

    def compute(self, context: ModelContext):  # noqa: D401
        raise RuntimeError("boom")


def _context() -> ModelContext:
    return ModelContext(
        target=ScoreTarget(model_url="model"),
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


def test_build_metrics_returns_expected_count() -> None:
    metrics = build_metrics()
    assert len(metrics) >= 6


def test_evaluate_metrics_captures_failures() -> None:
    context = _context()
    outcome = evaluate_metrics(context, [_ZeroMetric(), _FailMetric()])
    assert isinstance(outcome, EvaluationOutcome)
    assert outcome.metrics["zero"].value == 0.0
    assert outcome.failures and outcome.failures[0].name == "fail"
