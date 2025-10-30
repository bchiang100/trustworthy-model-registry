from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import acme_cli.scoring as scoring
from acme_cli.scoring_engine import ScoreSummary
from acme_cli.types import (EvaluationOutcome, LocalRepository, MetricResult,
                            ModelContext, ModelMetadata, RepoFile, ScoreTarget)


class _ModelScorerStub:
    def __init__(self, context_builder) -> None:  # noqa: D401
        self._builder = context_builder

    def score(self, target: ScoreTarget) -> ScoreSummary:
        metadata = ModelMetadata(
            repo_id="acme/model",
            display_name="model",
            card_data={"license": "mit"},
            downloads=100,
            likes=10,
            last_modified=datetime.now(timezone.utc),
            tags=["demo"],
            files=[RepoFile(path="model.safetensors", size_bytes=1024)],
            pipeline_tag="text-generation",
            library_name="transformers",
        )
        context = ModelContext(
            target=target,
            model_metadata=metadata,
            dataset_metadata=None,
            local_repo=LocalRepository(
                repo_id="acme/model", repo_type="model", path=None
            ),
            dataset_local_repo=None,
            readme_text="README",
            dataset_readme_text=None,
            commit_authors=["Alice"],
            commit_total=5,
        )
        metrics = {
            "ramp_up_time": MetricResult("ramp_up_time", 0.8, 11),
            "bus_factor": MetricResult("bus_factor", 0.6, 9),
            "performance_claims": MetricResult("performance_claims", 0.7, 8),
            "license": MetricResult("license", 1.0, 3),
            "size_score": MetricResult(
                "size_score",
                {
                    "raspberry_pi": 0.9,
                    "jetson_nano": 0.8,
                    "desktop_pc": 0.7,
                    "aws_server": 0.6,
                },
                5,
            ),
            "dataset_and_code_score": MetricResult("dataset_and_code_score", 0.5, 4),
            "dataset_quality": MetricResult("dataset_quality", 0.4, 4),
            "code_quality": MetricResult("code_quality", 0.9, 6),
        }
        outcome = EvaluationOutcome(metrics=metrics, failures=[])
        return ScoreSummary(context=context, outcome=outcome)


def test_score_file_emits_ndjson(tmp_path: Path, monkeypatch, capsys) -> None:
    url_file = tmp_path / "urls.txt"
    url_file.write_text("https://huggingface.co/acme/model\n")
    log_path = tmp_path / "log.txt"
    monkeypatch.setenv("LOG_FILE", str(log_path))

    monkeypatch.setattr(scoring, "ModelScorer", _ModelScorerStub)

    # Reset logger handlers to avoid cross-test pollution
    for handler in list(scoring.LOGGER.handlers):
        scoring.LOGGER.removeHandler(handler)

    scoring.score_file(url_file, [])

    output = capsys.readouterr().out.strip()
    data = json.loads(output)
    assert data["name"] == "model"
    assert data["category"] == "MODEL"
    assert "net_score" in data
    assert "size_score" in data and isinstance(data["size_score"], dict)
    assert data["size_score_latency"] > 0

    log_contents = log_path.read_text()
    assert "INFO" in log_contents


class _FailingScorer:
    def __init__(self, context_builder) -> None:  # noqa: D401
        pass

    def score(self, target: ScoreTarget) -> ScoreSummary:  # noqa: D401
        raise RuntimeError("boom")


def test_score_file_handles_failures(tmp_path: Path, monkeypatch, capsys) -> None:
    url_file = tmp_path / "urls.txt"
    url_file.write_text("https://huggingface.co/acme/model\n")
    log_path = tmp_path / "log.txt"
    monkeypatch.setenv("LOG_FILE", str(log_path))

    monkeypatch.setattr(scoring, "ModelScorer", _FailingScorer)

    for handler in list(scoring.LOGGER.handlers):
        scoring.LOGGER.removeHandler(handler)

    scoring.score_file(url_file, [])
    output = capsys.readouterr().out.strip()
    data = json.loads(output)
    assert data["error"]
    assert data["net_score"] == 0.0
