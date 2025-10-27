"""Static code quality heuristic based on local repository contents."""

from __future__ import annotations

from pathlib import Path

from acme_cli.metrics.base import Metric
from acme_cli.types import ModelContext
from acme_cli.utils import clamp, word_count


class CodeQualityMetric(Metric):
    name = "code_quality"

    def compute(self, context: ModelContext) -> float:
        repo = context.local_repo
        if not repo or not repo.path:
            return 0.0
        path = repo.path
        py_files = list(path.rglob("*.py"))
        py_count_score = clamp(len(py_files) / 15.0)
        doc_score = clamp(word_count(context.readme_text) / 2000)
        test_score = 0.0
        if any(
            (path / candidate).exists() for candidate in ("tests", "test", "unit_tests")
        ):
            test_score = 1.0
        lint_score = 0.0
        if any(
            (path / candidate).exists()
            for candidate in ("pyproject.toml", "setup.cfg", "ruff.toml", "mypy.ini")
        ):
            lint_score = 0.7
        typing_score = 0.0
        if any(file.suffix == ".pyi" for file in path.rglob("*.pyi")):
            typing_score = 0.5

        score = (
            0.4 * py_count_score
            + 0.3 * doc_score
            + 0.2 * test_score
            + 0.1 * max(lint_score, typing_score)
        )
        return clamp(score)


__all__ = ["CodeQualityMetric"]
