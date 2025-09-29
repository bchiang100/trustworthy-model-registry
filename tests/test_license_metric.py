from datetime import datetime, timezone

from acme_cli.metrics.license import LicenseMetric
from acme_cli.types import ModelContext, ModelMetadata, RepoFile, ScoreTarget


def _context_with_license(license_value) -> ModelContext:
    metadata = ModelMetadata(
        repo_id="model",
        display_name="model",
        card_data={"license": license_value},
        downloads=None,
        likes=None,
        last_modified=datetime.now(timezone.utc),
        tags=[],
        files=[RepoFile(path="README.md", size_bytes=10)],
        pipeline_tag=None,
        library_name=None,
    )
    return ModelContext(
        target=ScoreTarget(model_url="model"),
        model_metadata=metadata,
        dataset_metadata=None,
        local_repo=None,
        dataset_local_repo=None,
        readme_text="",
        dataset_readme_text=None,
        commit_authors=[],
        commit_total=0,
    )


def test_license_metric_permissive() -> None:
    context = _context_with_license("mit")
    assert LicenseMetric().compute(context) == 1.0


def test_license_metric_weak_copyleft() -> None:
    context = _context_with_license({"id": "lgpl-3.0"})
    assert LicenseMetric().compute(context) == 0.7


def test_license_metric_restrictive() -> None:
    context = _context_with_license([{"id": "gpl-3.0"}])
    assert LicenseMetric().compute(context) == 0.2


def test_license_metric_unknown() -> None:
    context = _context_with_license("custom")
    assert LicenseMetric().compute(context) == 0.4
