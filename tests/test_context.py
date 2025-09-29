from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from acme_cli.context import ContextBuilder
from acme_cli.types import DatasetMetadata, LocalRepository, ModelMetadata, RepoFile, ScoreTarget


class _StubHfClient:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path

    def get_model(self, repo_id: str) -> ModelMetadata:
        return ModelMetadata(
            repo_id=repo_id,
            display_name="demo",
            card_data={},
            downloads=100,
            likes=10,
        last_modified=datetime.now(UTC),
            tags=["demo"],
            files=[RepoFile(path="README.md", size_bytes=10)],
            pipeline_tag="text-generation",
            library_name="transformers",
        )

    def list_commit_authors(self, repo_id: str, repo_type: str = "model", limit: int = 50) -> tuple[list[str], int]:
        return (["Alice", "Bob"], 4)

    def get_dataset(self, repo_id: str) -> DatasetMetadata:
        return DatasetMetadata(
            repo_id=repo_id,
            card_data={"license": "cc-by-4.0"},
        last_modified=datetime.now(UTC),
            size_bytes=1024,
            citation="Paper",
            tags=["demo"],
            license="cc-by-4.0",
        )


class _StubRepoCache:
    def __init__(self, repo_dir: Path, dataset_dir: Path) -> None:
        self.repo_dir = repo_dir
        self.dataset_dir = dataset_dir

    def ensure_local(self, repo_id: str, repo_type: str = "model", allow_patterns=None) -> LocalRepository:  # noqa: D401
        if repo_type == "dataset":
            return LocalRepository(repo_id=repo_id, repo_type=repo_type, path=self.dataset_dir)
        return LocalRepository(repo_id=repo_id, repo_type=repo_type, path=self.repo_dir)


def test_context_builder_populates_fields(tmp_path: Path) -> None:
    repo_dir = tmp_path / "model"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("# Model\n", encoding="utf-8")
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    (dataset_dir / "README.md").write_text("Dataset", encoding="utf-8")

    builder = ContextBuilder(hf_client=_StubHfClient(tmp_path), repo_cache=_StubRepoCache(repo_dir, dataset_dir))
    target = ScoreTarget(
        model_url="https://huggingface.co/demo/model",
        dataset_urls=["https://huggingface.co/datasets/demo/dataset"],
        code_urls=[],
    )

    context = builder.build(target)

    assert context.model_metadata is not None
    assert context.dataset_metadata is not None
    assert context.local_repo and context.local_repo.path == repo_dir
    assert context.dataset_local_repo and context.dataset_local_repo.path == dataset_dir
    assert context.readme_text is not None
    assert context.dataset_readme_text is not None
    assert context.commit_authors == ["Alice", "Bob"]
