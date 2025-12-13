"""User-facing scoring pipeline producing NDJSON output."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from acme_cli.context import ContextBuilder
from acme_cli.input_loader import parse_url_file
from acme_cli.net_score import compute_net_score
from acme_cli.scoring_engine import ModelScorer
from acme_cli.types import MetricResult, ScoreTarget
from acme_cli.utils import clamp

LOGGER = logging.getLogger("acme_cli")


def score_file(url_file: Path, cli_args: Sequence[str]) -> None:
    """Score every model referenced in *url_file* and emit NDJSON to stdout."""
    _configure_logging()
    targets = parse_url_file(url_file)
    if not targets:
        LOGGER.warning("No model URLs found in input file %s", url_file)
        return

    context_builder = ContextBuilder()
    scorer = ModelScorer(context_builder=context_builder)

    for target in targets:
        record = _score_target(scorer, target)
        LOGGER.info("Scored model %s", target.model_url)
        print(json.dumps(record, ensure_ascii=False))


def _score_target(scorer: ModelScorer, target: ScoreTarget) -> dict[str, Any]:
    try:
        summary = scorer.score(target)
        outcome = summary.outcome
        net_metric = compute_net_score(outcome)
        outcome.metrics[net_metric.name] = net_metric
        record = _build_record(
            summary.context.target.model_url, summary.context, outcome
        )
        if outcome.failures:
            for failure in outcome.failures:
                LOGGER.warning("Metric %s failed: %s", failure.name, failure.message)
        return record
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Failed to score %s", target.model_url)
        return _empty_record(target.model_url, error=str(exc))


def _build_record(model_url: str, context, outcome) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    model_name = _derive_model_name(model_url, context.model_metadata)
    record: dict[str, Any] = {
        "name": model_name,
        "category": "MODEL",
    }
    record.update(_metric_field(outcome, "net_score", 0.0))
    record.update(_metric_field(outcome, "ramp_up_time", 0.0))
    record.update(_metric_field(outcome, "bus_factor", 0.0))
    record.update(_metric_field(outcome, "performance_claims", 0.0))
    record.update(_metric_field(outcome, "license", 0.0))
    record.update(_metric_field(outcome, "dataset_and_code_score", 0.0))
    record.update(_metric_field(outcome, "dataset_quality", 0.0))
    record.update(_metric_field(outcome, "code_quality", 0.0))
    size_value, size_latency = _metric_value(outcome, "size_score", {})
    if not size_value:
        size_value = {
            "raspberry_pi": 0.0,
            "jetson_nano": 0.0,
            "desktop_pc": 0.0,
            "aws_server": 0.0,
        }
    record["size_score"] = size_value
    record["size_score_latency"] = size_latency
    return record


def _metric_field(outcome, name: str, default: float) -> Mapping[str, Any]:  # type: ignore[no-untyped-def]
    value, latency = _metric_value(outcome, name, default)
    return {name: value, f"{name}_latency": latency}


def _metric_value(outcome, name: str, default):  # type: ignore[no-untyped-def]
    metric: MetricResult | None = outcome.metrics.get(name)
    if metric is None:
        return default, 0
    value = metric.value
    if isinstance(value, Mapping):
        return dict(value), metric.latency_ms
    return clamp(float(value)), metric.latency_ms


def _derive_model_name(model_url: str, metadata) -> str:  # type: ignore[no-untyped-def]
    if metadata and getattr(metadata, "display_name", None):
        return metadata.display_name
    if metadata and getattr(metadata, "repo_id", None):
        return metadata.repo_id
    return model_url


def _empty_record(model_url: str, error: str | None = None) -> dict[str, Any]:
    record = {
        "name": model_url,
        "category": "MODEL",
        "net_score": 0.0,
        "net_score_latency": 0,
        "ramp_up_time": 0.0,
        "ramp_up_time_latency": 0,
        "bus_factor": 0.0,
        "bus_factor_latency": 0,
        "performance_claims": 0.0,
        "performance_claims_latency": 0,
        "license": 0.0,
        "license_latency": 0,
        "size_score": {
            "raspberry_pi": 0.0,
            "jetson_nano": 0.0,
            "desktop_pc": 0.0,
            "aws_server": 0.0,
        },
        "size_score_latency": 0,
        "dataset_and_code_score": 0.0,
        "dataset_and_code_score_latency": 0,
        "dataset_quality": 0.0,
        "dataset_quality_latency": 0,
        "code_quality": 0.0,
        "code_quality_latency": 0,
    }
    if error:
        record["error"] = error
    return record


def _configure_logging() -> None:
    if LOGGER.handlers:
        return
    log_file = os.getenv("LOG_FILE")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler: logging.Handler
    if log_file:
        handler = logging.FileHandler(log_file)
    else:
        handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    LOGGER.addHandler(handler)
    LOGGER.setLevel(os.getenv("ACME_LOG_LEVEL", "INFO"))


__all__ = ["score_file"]
