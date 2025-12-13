"""Typed data structures used across the ACME CLI implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Mapping, MutableMapping

ModelCategory = Literal["MODEL", "DATASET", "CODE"]


@dataclass(slots=True)
class ScoreTarget:
    """Represents a model entry to score along with auxiliary artifacts."""

    model_url: str
    dataset_urls: list[str] = field(default_factory=list)
    code_urls: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RepoFile:
    """Metadata describing a file stored inside a Hugging Face repository."""

    path: str
    size_bytes: int | None


@dataclass(slots=True)
class ModelMetadata:
    """Subset of Hugging Face model metadata required for scoring."""

    repo_id: str
    display_name: str
    card_data: MutableMapping[str, Any]
    downloads: int | None
    likes: int | None
    last_modified: datetime | None
    tags: list[str]
    files: list[RepoFile]
    pipeline_tag: str | None
    library_name: str | None


@dataclass(slots=True)
class DatasetMetadata:
    """Relevant subset of Hugging Face dataset metadata."""

    repo_id: str
    card_data: MutableMapping[str, Any]
    last_modified: datetime | None
    size_bytes: int | None
    citation: str | None
    tags: list[str]
    license: str | None


@dataclass(slots=True)
class LocalRepository:
    """Represents a lazily-downloaded clone of a Hugging Face repository."""

    repo_id: str
    repo_type: Literal["model", "dataset", "space"]
    path: Path | None = None


@dataclass(slots=True)
class ModelContext:
    """Aggregated information available to metrics about a model."""

    target: ScoreTarget
    model_metadata: ModelMetadata | None
    dataset_metadata: DatasetMetadata | None
    local_repo: LocalRepository | None
    dataset_local_repo: LocalRepository | None
    readme_text: str | None
    dataset_readme_text: str | None
    commit_authors: list[str]
    commit_total: int


@dataclass(slots=True)
class MetricResult:
    """Result of evaluating a single metric."""

    name: str
    value: float | Mapping[str, float]
    latency_ms: int


@dataclass(slots=True)
class MetricFailure:
    """Represents a metric failure captured without aborting the run."""

    name: str
    message: str


@dataclass(slots=True)
class EvaluationOutcome:
    """Holds the collection of metric results and failures for a model."""

    metrics: dict[str, MetricResult]
    failures: list[MetricFailure]
