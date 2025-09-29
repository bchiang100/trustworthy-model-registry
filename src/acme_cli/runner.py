"""Top-level command handlers for the ACME CLI."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"


class CommandError(RuntimeError):
    """Raised when a subprocess command fails."""


def run_install(extra_args: Sequence[str] | None = None) -> int:
    """Install project dependencies into the user's site-packages."""
    args: list[str] = [sys.executable, "-m", "pip", "install", "--user", ".[dev]"]
    if extra_args:
        args.extend(extra_args)
    return _checked_run(args)


def run_tests(pytest_args: Sequence[str] | None = None) -> int:
    """Execute the test suite with coverage enabled."""
    args: list[str] = [
        sys.executable,
        "-m",
        "pytest",
        "--cov=acme_cli",
        "--cov-report=term-missing",
    ]
    if pytest_args:
        args.extend(pytest_args)
    return _checked_run(args)


def run_score(url_file: Path, cli_args: Sequence[str] | None = None) -> int:
    """Score the models referenced in *url_file*.

    The heavy lifting lives in :mod:`acme_cli.scoring`. This thin wrapper merely
    ensures the package is importable without installation by augmenting
    ``sys.path`` to include ``src/`` when running from the repo root.
    """
    sys.path.insert(0, str(SRC_ROOT))
    from acme_cli.scoring import score_file  # pylint: disable=import-error

    score_file(url_file, cli_args or [])
    return 0


def _checked_run(cmd: Sequence[str]) -> int:
    """Run *cmd* and raise :class:`CommandError` on failure."""
    try:
        subprocess.run(cmd, check=True)  # noqa: S603, S607
    except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive
        raise CommandError(str(exc)) from exc
    return 0


__all__ = ["CommandError", "run_install", "run_tests", "run_score"]
