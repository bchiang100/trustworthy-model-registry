from __future__ import annotations

from datetime import datetime, timezone

from acme_cli.hf.client import HfClient, HuggingFaceConfig


class _ModelInfo:
    def __init__(self) -> None:
        self.modelId = "acme/model"
        self.cardData = {"license": "mit"}
        self.downloads = 100
        self.likes = 5
        self.lastModified = datetime.now(timezone.utc)
        self.tags = ["demo"]
        self.siblings = []
        self.pipeline_tag = "text-generation"
        self.library_name = "transformers"


class _DatasetInfo:
    def __init__(self) -> None:
        self.id = "acme/dataset"
        self.cardData = {"license": "cc-by-4.0", "citation": "Paper"}
        self.lastModified = datetime.now(timezone.utc)
        self.size = 1024
        self.tags = ["demo"]
        self.license = "cc-by-4.0"


class _Author:
    def __init__(self, name: str | None = None, email: str | None = None) -> None:
        self.name = name
        self.email = email


class _Commit:
    def __init__(self, authors: list[_Author]) -> None:
        self.authors = authors


class _StubApi:
    def model_info(self, repo_id: str) -> _ModelInfo:  # noqa: D401
        return _ModelInfo()

    def dataset_info(self, repo_id: str) -> _DatasetInfo:  # noqa: D401
        return _DatasetInfo()

    def list_repo_commits(self, repo_id, repo_type=None, formatted=False):  # noqa: D401
        return [
            {"author": {"name": "Alice"}},
            _Commit([_Author(email="carol@example.com")]),
        ]

    def list_repo_files(
        self, repo_id: str, repo_type: str = "model"
    ) -> list[str]:  # noqa: D401
        return ["README.md", "model.safetensors"]


def test_hf_client_conversions() -> None:
    client = HfClient(HuggingFaceConfig(token=None))
    client._api = _StubApi()  # type: ignore[attr-defined]

    model = client.get_model("acme/model")
    dataset = client.get_dataset("acme/dataset")
    authors, total = client.list_commit_authors("acme/model")
    files = client.list_repo_files("acme/model")

    assert model and model.repo_id == "acme/model"
    assert dataset and dataset.repo_id == "acme/dataset"
    assert authors == ["Alice", "carol@example.com"]
    assert total == 2
    assert files == ["README.md", "model.safetensors"]
