"""
Client for interacting with Hugging Face Hub in ACME Registry.
"""
"""Thin wrapper around the Hugging Face Hub API with caching helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from huggingface_hub import HfApi, snapshot_download
from huggingface_hub.hf_api import DatasetInfo, ModelInfo, RepoFile
from huggingface_hub import hf_hub_url
import boto3

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

    def choose_preferred_file(self, files: list[RepoFile]) -> str | None:
        """Choose the best candidate file to download from a repo.

        Preference is given to known model weight extensions and filenames
        (e.g., 'pytorch_model.bin', '.safetensors', 'flax_model.msgpack'),
        otherwise the largest file is chosen.
        """
        if not files:
            return None

        preferred_patterns = [
            "pytorch_model.bin",
            ".safetensors",
            "flax_model.msgpack",
            ".msgpack",
            ".bin",
            ".pt",
            ".ckpt",
            ".h5",
            ".onnx",
        ]

        # match any preferred patterns
        matches = [f for f in files if any(p in f.path for p in preferred_patterns)]
        candidates = matches if matches else files

        # choose the file with largest size (None treated as 0)
        best = max(candidates, key=lambda f: (f.size_bytes or 0))
        return best.path

    def hf_hub_download(self, repo_id: str, filename: str, repo_type: str = "model", cache_dir: Optional[str] = None) -> str | None:
        """Download a single file from a repo and return the local path.

        Returns `None` on failure instead of raising to allow callers to
        gracefully fallback to other download strategies.
        """
        try:
            from huggingface_hub import hf_hub_download

            path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                repo_type=repo_type,
                cache_dir=cache_dir,
                token=(self._api.token if hasattr(self._api, "token") else None),
            )
            return path
        except Exception:  # noqa: BLE001
            return None

    def stream_file_to_s3(
        self,
        repo_id: str,
        filename: str,
        bucket: str,
        key: str,
        repo_type: str = "model",
        timeout: int = 60,
        s3_client: Optional[object] = None,
        chunk_size: int = 8 * 1024 * 1024,
    ) -> bool:
        """Stream a single file from the HF repo directly into S3.

        Returns True on success, False on any failure. This avoids writing
        the file to disk on the local host by streaming HTTP chunks and
        using S3 multipart upload.
        """
        token = getattr(self._api, "token", None)
        url = hf_hub_url(repo_id=repo_id, filename=filename, repo_type=repo_type)
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        s3 = s3_client or boto3.client("s3")
        upload_id = None
        try:
            import httpx

            with httpx.Client(timeout=timeout) as client:
                with client.stream("GET", url, headers=headers) as resp:
                    resp.raise_for_status()

                    # Start multipart upload
                    mp = s3.create_multipart_upload(Bucket=bucket, Key=key)
                    upload_id = mp["UploadId"]
                    parts: list[dict] = []
                    part_no = 1

                    for chunk in resp.iter_bytes(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        r = s3.upload_part(
                            Bucket=bucket,
                            Key=key,
                            PartNumber=part_no,
                            UploadId=upload_id,
                            Body=chunk,
                        )
                        parts.append({"ETag": r["ETag"], "PartNumber": part_no})
                        part_no += 1

                    # Complete multipart
                    s3.complete_multipart_upload(
                        Bucket=bucket,
                        Key=key,
                        UploadId=upload_id,
                        MultipartUpload={"Parts": parts},
                    )
            return True
        except Exception:  # noqa: BLE001 - callers will fallback on failure
            try:
                if upload_id:
                    s3.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
            except Exception:
                pass
            return False

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
