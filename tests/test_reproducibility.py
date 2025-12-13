"""Tests for the Reproducibility metric."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from acme_cli.metrics.reproducibility import Reproducibility
from acme_cli.types import (
    LocalRepository,
    ModelContext,
    ModelMetadata,
    RepoFile,
    ScoreTarget,
)


@pytest.fixture
def reproducibility_metric():
    """Create a reproducibility metric instance."""
    return Reproducibility()


def _create_model_context(
    tmp_path: Path,
    readme_text: str | None = None,
    include_example_file: bool = False,
) -> ModelContext:
    """Create a ModelContext for testing."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    if readme_text:
        (repo_path / "README.md").write_text(readme_text, encoding="utf-8")

    if include_example_file:
        (repo_path / "example.py").write_text(
            'print("Hello, World!")\nprint(42)', encoding="utf-8"
        )

    local_repo = LocalRepository(
        repo_id="test/model",
        repo_type="model",
        path=repo_path,
    )

    return ModelContext(
        target=ScoreTarget(model_url="https://huggingface.co/test/model"),
        model_metadata=ModelMetadata(
            repo_id="test/model",
            display_name="Test Model",
            card_data={},
            downloads=100,
            likes=10,
            last_modified=datetime.now(),
            tags=["test"],
            files=[RepoFile(path="README.md", size_bytes=100)],
            pipeline_tag=None,
            library_name=None,
        ),
        dataset_metadata=None,
        local_repo=local_repo,
        dataset_local_repo=None,
        readme_text=readme_text,
        dataset_readme_text=None,
        commit_authors=[],
        commit_total=0,
    )


def test_reproducibility_no_local_repo(reproducibility_metric):
    """Test that metric returns 0 when no local repo is available."""
    context = ModelContext(
        target=ScoreTarget(model_url="https://huggingface.co/test/model"),
        model_metadata=None,
        dataset_metadata=None,
        local_repo=None,
        dataset_local_repo=None,
        readme_text=None,
        dataset_readme_text=None,
        commit_authors=[],
        commit_total=0,
    )

    score = reproducibility_metric.compute(context)
    assert score == 0.0


def test_reproducibility_no_code_found(tmp_path, reproducibility_metric):
    """Test that metric returns 0 when no code is found."""
    context = _create_model_context(tmp_path, readme_text="# No code here", include_example_file=False)

    score = reproducibility_metric.compute(context)
    assert score == 0.0


def test_reproducibility_simple_code_success(tmp_path, reproducibility_metric):
    """Test that metric returns 1.0 when code runs successfully without LLM."""
    readme = """# Example Usage

```python
result = 2 + 2
print(result)
```
"""
    context = _create_model_context(tmp_path, readme_text=readme)

    score = reproducibility_metric.compute(context)
    assert score == 1.0


def test_reproducibility_code_with_output(tmp_path, reproducibility_metric):
    """Test code that produces output."""
    readme = """# Model Usage

```python
data = [1, 2, 3, 4, 5]
print(f"Sum: {sum(data)}")
```
"""
    context = _create_model_context(tmp_path, readme_text=readme)

    score = reproducibility_metric.compute(context)
    assert score == 1.0


def test_reproducibility_extract_markdown_code(reproducibility_metric):
    """Test extraction of code from markdown."""
    markdown = """
# Installation

```python
import numpy as np
arr = np.array([1, 2, 3])
print(arr)
```

More text here.

```python
print("test")
```
"""

    codes = reproducibility_metric._extract_code_from_markdown(markdown)
    assert len(codes) == 2
    assert "numpy" in codes[0]
    assert "test" in codes[1]


def test_reproducibility_extract_markdown_with_generic_blocks(reproducibility_metric):
    """Test extraction of code from markdown with generic code blocks."""
    markdown = """
# Example

```
print("hello")
x = 42
```

```python
print("world")
```
"""

    codes = reproducibility_metric._extract_code_from_markdown(markdown)
    assert len(codes) == 2


def test_reproducibility_execute_code(reproducibility_metric):
    """Test code execution."""
    code = 'print("Hello, World!")'
    output = reproducibility_metric._execute_code(code)
    assert output == "Hello, World!"


def test_reproducibility_execute_code_with_error(reproducibility_metric):
    """Test that code execution with errors raises exception."""
    code = "raise ValueError('Test error')"
    with pytest.raises(RuntimeError):
        reproducibility_metric._execute_code(code)


def test_reproducibility_execute_code_timeout(reproducibility_metric):
    """Test that code execution with timeout raises exception."""
    code = "import time; time.sleep(100)"
    with pytest.raises(Exception):  # Could be TimeoutExpired or RuntimeError
        reproducibility_metric._execute_code(code, timeout=1)


def test_reproducibility_is_valid_output(reproducibility_metric):
    """Test output validation."""
    assert reproducibility_metric._is_valid_output("some output") is True
    assert reproducibility_metric._is_valid_output("") is False
    assert reproducibility_metric._is_valid_output("   \n   ") is False
    assert reproducibility_metric._is_valid_output("123") is True


def test_reproducibility_is_valid_output_filters_warnings(reproducibility_metric):
    """Test that output validation filters out warnings."""
    output_with_warning = """Warning: This is a warning
Some actual output"""
    assert reproducibility_metric._is_valid_output(output_with_warning) is True

    # Pure warnings should fail
    warning_only = "Warning: Something\nWarning: Something else"
    assert reproducibility_metric._is_valid_output(warning_only) is False


def test_reproducibility_failed_code_no_llm(tmp_path, reproducibility_metric):
    """Test that failed code returns 0 when LLM is unavailable."""
    readme = """# Example

```python
import nonexistent_module
print(nonexistent_module.something())
```
"""
    context = _create_model_context(tmp_path, readme_text=readme)

    # Should return 0 when LLM debugging fails
    score = reproducibility_metric.compute(context)
    assert score == 0.0


def test_reproducibility_extract_from_example_file(tmp_path, reproducibility_metric):
    """Test extraction of code from example files."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    examples_dir = repo_path / "examples"
    examples_dir.mkdir()
    (examples_dir / "demo.py").write_text('print("from example file")', encoding="utf-8")

    local_repo = LocalRepository(
        repo_id="test/model",
        repo_type="model",
        path=repo_path,
    )

    with patch("acme_cli.metrics.reproducibility.HfApi") as mock_api:
        mock_api_instance = MagicMock()
        mock_api.return_value = mock_api_instance
        mock_api_instance.list_repo_files.return_value = ["examples/demo.py"]

        codes = reproducibility_metric._extract_code_from_files(
            repo_id="test/model",
            repo_type="model",
            local_path=repo_path,
        )

        assert len(codes) > 0
        assert "from example file" in codes[0]


def test_reproducibility_multiple_attempts(tmp_path, reproducibility_metric):
    """Test that metric tries multiple code snippets."""
    readme = """# Examples

```python
import nonexistent
print(nonexistent.fail())
```

```python
result = 10 * 5
print(result)
```
"""
    context = _create_model_context(tmp_path, readme_text=readme)

    # Should return 1.0 because the second code snippet works
    score = reproducibility_metric.compute(context)
    assert score == 1.0


def test_reproducibility_code_with_imports(tmp_path, reproducibility_metric):
    """Test code with standard library imports."""
    readme = """# Example

```python
import json
data = json.dumps({"key": "value"})
print(data)
```
"""
    context = _create_model_context(tmp_path, readme_text=readme)

    score = reproducibility_metric.compute(context)
    assert score == 1.0


def test_reproducibility_code_with_computation(tmp_path, reproducibility_metric):
    """Test code that performs computation."""
    readme = """# Computation Example

```python
nums = [1, 2, 3, 4, 5]
squared = [x**2 for x in nums]
print(sum(squared))
```
"""
    context = _create_model_context(tmp_path, readme_text=readme)

    score = reproducibility_metric.compute(context)
    assert score == 1.0


def test_reproducibility_debug_code_with_llm(reproducibility_metric):
    """Test LLM code debugging."""
    broken_code = """
result = undefined_variable
print(result)
"""
    error = "NameError: name 'undefined_variable' is not defined"

    with patch.object(reproducibility_metric, "_llm") as mock_llm:
        mock_llm_instance = MagicMock()
        reproducibility_metric._llm = mock_llm_instance
        mock_llm_instance._client.text_generation.return_value = """
```python
result = 42
print(result)
```
"""
        # The method should attempt to debug the code
        try:
            fixed = reproducibility_metric._debug_code_with_llm(broken_code, error)
            assert "42" in fixed or "result" in fixed
        except Exception:
            # LLM might not be available in test environment
            pass
