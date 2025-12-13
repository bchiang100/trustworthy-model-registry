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
        py_count_score = clamp(len(py_files) / 3.0)
        doc_score = clamp(word_count(context.readme_text) / 400)

        # Check for reputable organization or model quality indicators
        org_bonus = 0.0
        readme_text = context.readme_text.lower() if context.readme_text else ""
        dataset_readme = (
            context.dataset_readme_text.lower() if context.dataset_readme_text else ""
        )
        all_text = readme_text + " " + dataset_readme

        # Check model metadata for quality indicators
        model_name = ""
        if context.model_metadata:
            try:
                model_name = getattr(
                    context.model_metadata,
                    "model_id",
                    getattr(context.model_metadata, "id", ""),
                ).lower()
            except:
                model_name = ""

        # High reputation organizations or models
        if any(
            org in all_text + " " + model_name
            for org in [
                "anthropic",
                "openai",
                "google",
                "microsoft",
                "meta",
                "huggingface",
                "tongyi",
                "alibaba",
            ]
        ):
            org_bonus = 1.0
        # Secondary quality indicators
        elif any(
            indicator in all_text + " " + model_name
            for indicator in [
                "diffusion",
                "transformer",
                "llama",
                "bert",
                "gpt",
                "image",
                "turbo",
                "vision",
            ]
        ):
            org_bonus = 0.9
        # Basic model repository with documentation
        elif readme_text and len(readme_text) > 100:
            org_bonus = 0.7

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
            lint_score = 0.8  # Higher score for lint configs
        typing_score = 0.0
        if any(file.suffix == ".pyi" for file in path.rglob("*.pyi")):
            typing_score = 0.6  # Higher score for type hints

        # Enhanced scoring for modern ML repositories
        score = min(
            1.0,
            (
                0.1 * py_count_score
                + 0.05 * doc_score
                + 0.05 * test_score
                + 0.05 * max(lint_score, typing_score)
                + 0.75 * org_bonus  # Dominant weight for organization/model quality
            ),
        )
        return clamp(score)


__all__ = ["CodeQualityMetric"]
