#!/usr/bin/env python3
"""
Example demonstrating the Reproducibility metric.

This script shows how to use the Reproducibility metric to evaluate
whether a model's example code can be extracted and executed successfully.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime

from acme_cli.metrics.reproducibility import Reproducibility
from acme_cli.types import (
    LocalRepository,
    ModelContext,
    ModelMetadata,
    RepoFile,
    ScoreTarget,
)


def main():
    """Demonstrate the reproducibility metric."""
    metric = Reproducibility()

    # Example 1: Model with code in README that runs successfully
    print("=" * 60)
    print("Example 1: Model with working example code in README")
    print("=" * 60)

    with TemporaryDirectory() as tmp_dir:
        repo_path = Path(tmp_dir)

        # Create a README with example code
        readme = """# My Awesome Model

This is a great model for image classification.

## Usage

Here's how to use it:

```python
# Simple prediction example
result = 2 + 2
print(f"Calculation result: {result}")
```

You can also use it with:

```python
import json
data = {"name": "model", "version": "1.0"}
print(json.dumps(data, indent=2))
```
"""
        (repo_path / "README.md").write_text(readme, encoding="utf-8")

        context = ModelContext(
            target=ScoreTarget(model_url="https://huggingface.co/example/model"),
            model_metadata=ModelMetadata(
                repo_id="example/model",
                display_name="Example Model",
                card_data={},
                downloads=1000,
                likes=50,
                last_modified=datetime.now(),
                tags=["classification"],
                files=[RepoFile(path="README.md", size_bytes=500)],
                pipeline_tag="image-classification",
                library_name="transformers",
            ),
            dataset_metadata=None,
            local_repo=LocalRepository(
                repo_id="example/model",
                repo_type="model",
                path=repo_path,
            ),
            dataset_local_repo=None,
            readme_text=readme,
            dataset_readme_text=None,
            commit_authors=["alice", "bob"],
            commit_total=42,
        )

        score = metric.compute(context)
        print(f"\nReproducibility Score: {score}")
        print(f"Expected: 1.0 (code exists and runs without LLM debugging)")
        print(f"Result: {'✓ PASS' if score == 1.0 else '✗ FAIL'}")

    # Example 2: Model with no example code
    print("\n" + "=" * 60)
    print("Example 2: Model with no example code")
    print("=" * 60)

    with TemporaryDirectory() as tmp_dir:
        repo_path = Path(tmp_dir)

        readme = """# My Model

This model does something.
No examples provided.
"""
        (repo_path / "README.md").write_text(readme, encoding="utf-8")

        context = ModelContext(
            target=ScoreTarget(model_url="https://huggingface.co/example/model2"),
            model_metadata=None,
            dataset_metadata=None,
            local_repo=LocalRepository(
                repo_id="example/model2",
                repo_type="model",
                path=repo_path,
            ),
            dataset_local_repo=None,
            readme_text=readme,
            dataset_readme_text=None,
            commit_authors=[],
            commit_total=0,
        )

        score = metric.compute(context)
        print(f"\nReproducibility Score: {score}")
        print(f"Expected: 0.0 (no code found)")
        print(f"Result: {'✓ PASS' if score == 0.0 else '✗ FAIL'}")

    # Example 3: Model with example Python file
    print("\n" + "=" * 60)
    print("Example 3: Model with example Python file")
    print("=" * 60)

    with TemporaryDirectory() as tmp_dir:
        repo_path = Path(tmp_dir)

        # Create an example.py file
        (repo_path / "example.py").write_text(
            """# Example script
numbers = [1, 2, 3, 4, 5]
total = sum(numbers)
print(f"Sum of {numbers}: {total}")
""",
            encoding="utf-8",
        )

        context = ModelContext(
            target=ScoreTarget(model_url="https://huggingface.co/example/model3"),
            model_metadata=None,
            dataset_metadata=None,
            local_repo=LocalRepository(
                repo_id="example/model3",
                repo_type="model",
                path=repo_path,
            ),
            dataset_local_repo=None,
            readme_text=None,
            dataset_readme_text=None,
            commit_authors=[],
            commit_total=0,
        )

        score = metric.compute(context)
        print(f"\nReproducibility Score: {score}")
        print(f"Expected: 1.0 (code from file runs successfully)")
        print(f"Result: {'✓ PASS' if score == 1.0 else '✗ FAIL'}")

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
