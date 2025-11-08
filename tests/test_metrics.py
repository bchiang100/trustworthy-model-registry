from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from acme_cli.llm import LlmUnavailable
from acme_cli.metrics.bus_factor import BusFactorMetric
from acme_cli.metrics.code_quality import CodeQualityMetric
from acme_cli.metrics.dataset_code import DatasetAndCodeMetric
from acme_cli.metrics.dataset_quality import DatasetQualityMetric
from acme_cli.metrics.license import LicenseMetric
from acme_cli.metrics.performance import PerformanceClaimsMetric
from acme_cli.metrics.ramp_up import RampUpMetric
from acme_cli.metrics.size import SizeMetric
from acme_cli.types import (
    DatasetMetadata,
    EvaluationOutcome,
    LocalRepository,
    MetricResult,
    ModelContext,
    ModelMetadata,
    RepoFile,
    ScoreTarget,
)


@dataclass
class _StubLlm:
    clarity: float = 0.8
    claims: float = 0.9

    def score_clarity(self, readme_text: str) -> float:  # noqa: D401
        return self.clarity

    def score_performance_claims(self, readme_text: str) -> float:  # noqa: D401
        return self.claims


class _FailingLlm:
    def score_clarity(self, readme_text: str) -> float:  # noqa: D401
        raise LlmUnavailable("offline")

    def score_performance_claims(self, readme_text: str) -> float:  # noqa: D401
        raise LlmUnavailable("offline")


def _context(tmp_path: Path) -> ModelContext:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "README.md").write_text(
        """# Demo\n\n## Installation\n````code````\n""", encoding="utf-8"
    )
    (repo_path / "tests").mkdir()
    (repo_path / "pyproject.toml").write_text("[tool.demo]\n", encoding="utf-8")
    weight_path = repo_path / "model.safetensors"
    weight_path.write_bytes(b"0" * 1024 * 1024)  # 1 MiB

    dataset_path = tmp_path / "dataset"
    dataset_path.mkdir()
    (dataset_path / "README.md").write_text(
        "Dataset documentation" * 50, encoding="utf-8"
    )

    model_metadata = ModelMetadata(
        repo_id="acme/model",
        display_name="model",
        card_data={"license": "apache-2.0"},
        downloads=1000,
        likes=50,
        last_modified=datetime.now(timezone.utc),
        tags=["text-generation", "demo"],
        files=[
            RepoFile(path="model.safetensors", size_bytes=weight_path.stat().st_size)
        ],
        pipeline_tag="text-generation",
        library_name="transformers",
    )
    dataset_metadata = DatasetMetadata(
        repo_id="acme/dataset",
        card_data={"license": "cc-by-4.0", "citation": "arXiv"},
        last_modified=datetime.now(timezone.utc),
        size_bytes=5 * 1024 * 1024,
        citation="Paper",
        tags=["nlp"],
        license="cc-by-4.0",
    )
    return ModelContext(
        target=ScoreTarget(
            model_url="https://huggingface.co/acme/model",
            dataset_urls=["https://huggingface.co/datasets/acme/dataset"],
            code_urls=["https://github.com/acme/repo"],
        ),
        model_metadata=model_metadata,
        dataset_metadata=dataset_metadata,
        local_repo=LocalRepository(
            repo_id="acme/model", repo_type="model", path=repo_path
        ),
        dataset_local_repo=LocalRepository(
            repo_id="acme/dataset", repo_type="dataset", path=dataset_path
        ),
        readme_text=(repo_path / "README.md").read_text(encoding="utf-8"),
        dataset_readme_text=(dataset_path / "README.md").read_text(encoding="utf-8"),
        commit_authors=["Alice", "Bob", "Charlie"],
        commit_total=15,
    )


def test_ramp_up_metric_uses_llm(tmp_path: Path) -> None:
    context = _context(tmp_path)
    metric = RampUpMetric(llm=_StubLlm(clarity=0.7))
    value = metric.compute(context)
    assert 0 < value <= 1


def test_ramp_up_metric_falls_back_when_llm_unavailable(tmp_path: Path) -> None:
    context = _context(tmp_path)
    metric = RampUpMetric(llm=_FailingLlm())
    value = metric.compute(context)
    assert value > 0  # heuristic still applies


def test_performance_claims_metric(tmp_path: Path) -> None:
    context = _context(tmp_path)
    metric = PerformanceClaimsMetric(llm=_StubLlm(claims=0.85))
    value = metric.compute(context)
    assert 0 < value <= 1


def test_bus_factor_metric(tmp_path: Path) -> None:
    context = _context(tmp_path)
    metric = BusFactorMetric()
    value = metric.compute(context)
    assert 0 < value <= 1


def test_license_metric(tmp_path: Path) -> None:
    context = _context(tmp_path)
    metric = LicenseMetric()
    value = metric.compute(context)
    assert value == 1.0


def test_size_metric(tmp_path: Path) -> None:
    context = _context(tmp_path)
    metric = SizeMetric()
    values = metric.compute(context)
    assert set(values) == {"raspberry_pi", "jetson_nano", "desktop_pc", "aws_server"}
    assert all(0 <= score <= 1 for score in values.values())


def test_dataset_and_code_metric(tmp_path: Path) -> None:
    context = _context(tmp_path)
    metric = DatasetAndCodeMetric()
    value = metric.compute(context)
    assert 0 < value <= 1


def test_dataset_quality_metric(tmp_path: Path) -> None:
    context = _context(tmp_path)
    metric = DatasetQualityMetric()
    value = metric.compute(context)
    assert 0 < value <= 1


def test_code_quality_metric(tmp_path: Path) -> None:
    context = _context(tmp_path)
    metric = CodeQualityMetric()
    value = metric.compute(context)
    assert 0 < value <= 1


def test_size_metric_handles_missing_repo() -> None:
    metric = SizeMetric()
    context = ModelContext(
        target=ScoreTarget(model_url="model"),
        model_metadata=None,
        dataset_metadata=None,
        local_repo=None,
        dataset_local_repo=None,
        readme_text=None,
        dataset_readme_text=None,
        commit_authors=[],
        commit_total=0,
    )
    values = metric.compute(context)
    assert all(score == 0.0 for score in values.values())


def test_size_metric_uses_metadata(tmp_path: Path) -> None:
    metadata = ModelMetadata(
        repo_id="model",
        display_name="model",
        card_data={},
        downloads=None,
        likes=None,
        last_modified=datetime.now(timezone.utc),
        tags=[],
        files=[RepoFile(path="pytorch_model.bin", size_bytes=1024 * 1024)],
        pipeline_tag=None,
        library_name=None,
    )
    context = ModelContext(
        target=ScoreTarget(model_url="model"),
        model_metadata=metadata,
        dataset_metadata=None,
        local_repo=None,
        dataset_local_repo=None,
        readme_text=None,
        dataset_readme_text=None,
        commit_authors=[],
        commit_total=0,
    )
    metric = SizeMetric()
    result = metric.compute(context)
    assert result["raspberry_pi"] == 1.0


def test_dataset_quality_handles_license_list(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context.dataset_metadata.license = ["CC-BY-4.0"]  # type: ignore[assignment]
    metric = DatasetQualityMetric()
    value = metric.compute(context)
    assert value > 0
