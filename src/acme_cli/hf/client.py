"""Thin wrapper around the Hugging Face Hub API with caching helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from huggingface_hub import HfApi, snapshot_download
from huggingface_hub.hf_api import DatasetInfo, ModelInfo, RepoFile

from acme_cli.types import DatasetMetadata, ModelMetadata
from acme_cli.types import RepoFile as RepoFileMetadata


@dataclass(slots=True)
class HuggingFaceConfig:
    """Configuration for :class:`HfClient`."""

    token: str | None = None
    endpoint: str | None = None


class HfClient:
    """A convenience wrapper that exposes just the calls we need."""

    def __init__(self, config: HuggingFaceConfig | None = None) -> None:
        config = config or HuggingFaceConfig(
            token=os.getenv("HUGGINGFACEHUB_API_TOKEN") or os.getenv("HF_API_TOKEN"),
            endpoint=os.getenv("HUGGINGFACEHUB_ENDPOINT"),
        )
        self._api = (
            HfApi(token=config.token, endpoint=config.endpoint)
            if config.endpoint
            else HfApi(token=config.token)
        )

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _convert_files(files: Iterable[RepoFile]) -> list[RepoFileMetadata]:
        return [
            RepoFileMetadata(path=file.rfilename, size_bytes=file.size)
            for file in files
        ]

    @staticmethod
    def _convert_model_info(info: ModelInfo) -> ModelMetadata:
        card_data = {}
        if getattr(info, "cardData", None):
            card_data_obj = info.cardData
            if hasattr(card_data_obj, "to_dict"):
                card_data = card_data_obj.to_dict()  # type: ignore[call-arg]
            else:
                card_data = dict(getattr(card_data_obj, "data", card_data_obj))
        return ModelMetadata(
            repo_id=info.modelId,
            display_name=info.modelId.split("/")[-1],
            card_data=card_data,
            downloads=getattr(info, "downloads", None),
            likes=getattr(info, "likes", None),
            last_modified=getattr(info, "lastModified", None),
            tags=list(info.tags or []),
            files=HfClient._convert_files(info.siblings or []),
            pipeline_tag=getattr(info, "pipeline_tag", None),
            library_name=getattr(info, "library_name", None),
        )

    @staticmethod
    def _convert_dataset_info(info: DatasetInfo) -> DatasetMetadata:
        card_data = {}
        if getattr(info, "cardData", None):
            card_data_obj = info.cardData
            if hasattr(card_data_obj, "to_dict"):
                card_data = card_data_obj.to_dict()  # type: ignore[call-arg]
            else:
                card_data = dict(getattr(card_data_obj, "data", card_data_obj))
        return DatasetMetadata(
            repo_id=info.id,
            card_data=card_data,
            last_modified=getattr(info, "lastModified", None),
            size_bytes=getattr(info, "size", None),
            citation=card_data.get("citation"),
            tags=list(info.tags or []),
            license=card_data.get("license") or getattr(info, "license", None),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_model(self, repo_id: str) -> ModelMetadata | None:
        try:
            info = self._api.model_info(repo_id)
        except Exception:  # noqa: BLE001 - propagate as soft failure
            return None
        return self._convert_model_info(info)

    def get_dataset(self, repo_id: str) -> DatasetMetadata | None:
        try:
            info = self._api.dataset_info(repo_id)
        except Exception:  # noqa: BLE001 - propagate as soft failure
            return None
        return self._convert_dataset_info(info)

    def list_commit_authors(
        self, repo_id: str, repo_type: str = "model", limit: int = 50
    ) -> tuple[list[str], int]:
        try:
            commits = self._api.list_repo_commits(
                repo_id, repo_type=repo_type, formatted=True
            )
        except Exception:  # noqa: BLE001
            return ([], 0)
        authors: list[str] = []
        for commit in commits[:limit]:
            if isinstance(commit, dict):
                primary = commit.get("author") or {}
                name = primary.get("name") or primary.get("email")
                if name:
                    authors.append(str(name))
                continue
            commit_authors = getattr(commit, "authors", None)
            if commit_authors:
                for author in commit_authors:
                    name = getattr(author, "name", None) or getattr(
                        author, "email", None
                    )
                    if name:
                        authors.append(str(name))
                        break
        return (authors, len(commits))

    def list_repo_files(self, repo_id: str, repo_type: str = "model") -> list[str]:
        try:
            files = self._api.list_repo_files(repo_id=repo_id, repo_type=repo_type)
        except Exception:  # noqa: BLE001
            return []
        return list(files)

    def snapshot_download(self, repo_id: str, repo_type: str = "model", cache_dir: Optional[str] = None) -> str | None:
        """Download a snapshot of the repo and return the local path to it.

        Wraps `huggingface_hub.snapshot_download` and forwards the client's
        token. Returns `None` on failure to allow callers to handle errors
        without raising during diagnostic runs.
        """
        try:
            path = snapshot_download(
                repo_id,
                repo_type=repo_type,
                cache_dir=cache_dir,
                token=(self._api.token if hasattr(self._api, "token") else None),
            )
            return path
        except Exception:  # noqa: BLE001
            return None


__all__ = ["HfClient", "HuggingFaceConfig"]
