"""
Local cache for Hugging Face repositories in ACME Registry.
"""
"""Local repository download helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from huggingface_hub import snapshot_download

from acme_cli.types import LocalRepository


class RepositoryCache:
    """Manages local snapshots of Hugging Face repositories."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        base = cache_dir or Path(
            os.getenv("ACME_CACHE_DIR", Path.home() / ".cache" / "acme_cli")
        )
        self.cache_dir = base
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def ensure_local(
        self,
        repo_id: str,
        repo_type: str = "model",
        allow_patterns: Iterable[str] | None = None,
    ) -> LocalRepository:
        local_path = snapshot_download(
            repo_id,
            repo_type=repo_type,
            cache_dir=str(self.cache_dir),
            local_files_only=False,
            allow_patterns=list(allow_patterns) if allow_patterns else None,
            max_workers=4,
        )
        return LocalRepository(
            repo_id=repo_id, repo_type=repo_type, path=Path(local_path)
        )


__all__ = ["RepositoryCache"]
