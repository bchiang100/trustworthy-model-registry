"""
Build rich contexts for metric evaluation in ACME Registry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from acme_cli.hf.client import HfClient
from acme_cli.hf.local_cache import RepositoryCache
from acme_cli.types import (
    DatasetMetadata,
    LocalRepository,
    ModelContext,
    ModelMetadata,
    ScoreTarget,
)
from acme_cli.urls import parse_artifact_url


class ContextBuilder:
    """
    Constructs ModelContext instances used by metrics.
    Builds context from ScoreTarget, fetching metadata and repositories.
    """

    def __init__(
        self,
        hf_client: HfClient | None = None,
        repo_cache: RepositoryCache | None = None,
    ) -> None:
        self._hf = hf_client or HfClient()
        self._cache = repo_cache or RepositoryCache()

    def build(self, target: ScoreTarget) -> ModelContext:
        """
        Build a ModelContext for the given ScoreTarget.
        Fetches model, dataset, and code metadata as needed.
        """
        parsed_model = parse_artifact_url(target.model_url)
        model_metadata: ModelMetadata | None = None
        dataset_metadata: DatasetMetadata | None = None
        local_repo: LocalRepository | None = None
        dataset_repo: LocalRepository | None = None
        readme_text: str | None = None
        dataset_readme_text: str | None = None
        commit_authors: list[str] = []
        commit_total = 0

        if parsed_model.repo_id:
            model_metadata = self._hf.get_model(parsed_model.repo_id)
            commit_authors, commit_total = self._hf.list_commit_authors(
                parsed_model.repo_id, repo_type="model"
            )
            if model_metadata:
                local_repo = self._cache.ensure_local(
                    parsed_model.repo_id,
                    repo_type="model",
                    allow_patterns=[
                        "README.*",
                        "*.md",
                        "*.json",
                        "*.py",
                        "*.txt",
                        "*.yaml",
                        "*.yml",
                        "*.cfg",
                        "*.ini",
                        "*.pyi",
                    ],
                )
                readme_text = _load_readme(local_repo.path)

        dataset_repo_id = _first_hf_dataset_id(target.dataset_urls)
        if dataset_repo_id:
            dataset_metadata = self._hf.get_dataset(dataset_repo_id)
            try:
                dataset_repo = self._cache.ensure_local(
                    dataset_repo_id,
                    repo_type="dataset",
                    allow_patterns=["README.*", "*.md", "dataset_info.json"],
                )
                dataset_readme_text = _load_readme(dataset_repo.path)
            except Exception:  # noqa: BLE001
                dataset_repo = None
                dataset_readme_text = None

        return ModelContext(
            target=target,
            model_metadata=model_metadata,
            dataset_metadata=dataset_metadata,
            local_repo=local_repo,
            dataset_local_repo=dataset_repo,
            readme_text=readme_text,
            dataset_readme_text=dataset_readme_text,
            commit_authors=commit_authors,
            commit_total=commit_total,
        )


def _first_hf_dataset_id(urls: Iterable[str]) -> str | None:
    for url in urls:
        parsed = parse_artifact_url(url)
        if (
            parsed.platform == "huggingface"
            and parsed.kind == "dataset"
            and parsed.repo_id
        ):
            return parsed.repo_id
    return None


def _load_readme(repo_path: Path | None) -> str | None:
    if not repo_path:
        return None
    for name in ("README.md", "README.MD", "README.txt", "README.rst", "README"):
        candidate = repo_path / name
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return candidate.read_text(encoding="latin-1")
    return None


__all__ = ["ContextBuilder"]
