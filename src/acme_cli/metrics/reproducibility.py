"""Reproducibility metric for evaluating if example code exists and runs successfully."""
from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any

from acme_cli.llm import LlmConfig, LlmEvaluator, LlmUnavailable
from acme_cli.metrics.base import Metric
from acme_cli.types import ModelContext
from huggingface_hub import HfApi

logger = logging.getLogger(__name__)


class Reproducibility(Metric):
    """Metric that evaluates reproducibility of a model via example code execution."""

    name = "reproducibility"

    def __init__(self, llm_config: LlmConfig | None = None) -> None:
        """Initialize reproducibility metric with optional LLM configuration."""
        self._llm_config = llm_config
        self._llm: LlmEvaluator | None = None

    def compute(self, context: ModelContext) -> float:
        """
        Compute reproducibility score based on example code extraction and execution.

        Returns:
            float: Score between 0 and 1
                - 1.0: Example code exists and runs without LLM debugging
                - 0.5: Example code exists and runs after LLM debugging
                - 0.0: Code doesn't exist or fails to produce valid results
        """
        if not context.local_repo or not context.local_repo.path:
            logger.warning("No local repository available for reproducibility check")
            return 0.0

        # Extract example code from multiple sources
        code_snippets: list[str] = []

        # Try extracting from README/documentation
        if context.readme_text:
            readme_snippets = self._extract_code_from_markdown(context.readme_text)
            code_snippets.extend(readme_snippets)

        # Try extracting from Python example files
        try:
            file_snippets = self._extract_code_from_files(
                repo_id=context.local_repo.repo_id,
                repo_type=context.local_repo.repo_type,
                local_path=context.local_repo.path,
            )
            code_snippets.extend(file_snippets)
        except Exception as e:
            logger.warning(f"Failed to extract code from files: {e}")

        if not code_snippets:
            logger.info("No example code found")
            return 0.0

        # Try running each code snippet
        for code in code_snippets:
            try:
                # First attempt: run without LLM debugging
                output = self._execute_code(code)
                if self._is_valid_output(output):
                    logger.info("Example code executed successfully without LLM debugging")
                    return 1.0
            except Exception as e:
                logger.debug(f"Initial code execution failed: {e}")
                # Second attempt: use LLM to debug and retry
                try:
                    if self._llm is None:
                        self._llm = LlmEvaluator(self._llm_config)

                    debugged_code = self._debug_code_with_llm(code, str(e))
                    output = self._execute_code(debugged_code)
                    if self._is_valid_output(output):
                        logger.info("Example code executed successfully after LLM debugging")
                        return 0.5
                except Exception as debug_e:
                    logger.debug(f"LLM debugging failed: {debug_e}")
                    continue

        logger.info("No valid executable code found after all attempts")
        return 0.0

    def _extract_code_from_markdown(self, markdown_text: str) -> list[str]:
        """Extract Python code blocks from markdown text."""
        code_blocks = []
        # Match both ```python and ``` code blocks
        pattern = r"```(?:python)?\s*\n(.*?)\n```"
        matches = re.findall(pattern, markdown_text, re.DOTALL)
        code_blocks.extend(matches)
        return code_blocks

    def _extract_code_from_files(
        self,
        repo_id: str,
        repo_type: str,
        local_path: Path,
    ) -> list[str]:
        """Extract Python code from example files in the repository."""
        code_snippets = []

        # First, try to scan local repository directly
        if local_path and local_path.exists():
            code_snippets.extend(self._scan_local_directory_for_code(local_path))

        # Then, try to get files from API (may fail for non-existent repos)
        try:
            api = HfApi()
            files = api.list_repo_files(repo_id=repo_id, repo_type=repo_type)
        except Exception as e:
            logger.debug(f"Failed to list repo files from API: {e}")
            return code_snippets

        # Patterns for example code files
        patterns = [
            r"examples?/.*\.py$",
            r"demo/.*\.py$",
            r"tutorials?/.*\.py$",
            r"scripts?/.*\.py$",
            r"app\.py$",
            r"run_.*\.py$",
            r"test_.*\.py$",
        ]

        example_files = []
        for file in files:
            for pattern in patterns:
                if re.search(pattern, file.lower()):
                    example_files.append(file)
                    break

        # Try to read and extract code from matched files
        for file_path in example_files[:5]:  # Limit to first 5 matches
            try:
                full_path = local_path / file_path
                if full_path.exists() and full_path.is_file():
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        # Skip if file is too large
                        if len(content) < 50000:
                            code_snippets.append(content)
            except Exception as e:
                logger.debug(f"Failed to read file {file_path}: {e}")

        return code_snippets

    def _scan_local_directory_for_code(self, local_path: Path) -> list[str]:
        """Scan local directory for Python example files."""
        code_snippets = []

        # Patterns for example code files
        patterns = [
            r"example.*\.py$",
            r"demo.*\.py$",
            r"tutorial.*\.py$",
            r"script.*\.py$",
            r"app\.py$",
            r"run_.*\.py$",
        ]

        try:
            for py_file in local_path.glob("**/*.py"):
                # Skip hidden files and __pycache__
                if any(part.startswith(".") for part in py_file.parts):
                    continue
                if "__pycache__" in py_file.parts:
                    continue

                file_name = py_file.name.lower()
                if any(re.search(pattern, file_name) for pattern in patterns):
                    try:
                        with open(py_file, "r", encoding="utf-8") as f:
                            content = f.read()
                            if len(content) < 50000:  # Skip very large files
                                code_snippets.append(content)
                    except Exception as e:
                        logger.debug(f"Failed to read file {py_file}: {e}")
        except Exception as e:
            logger.debug(f"Failed to scan local directory: {e}")

        return code_snippets

    def _execute_code(self, code: str, timeout: int = 30) -> str:
        """
        Execute Python code in a temporary environment and capture output.

        Args:
            code: Python code to execute
            timeout: Timeout in seconds

        Returns:
            str: The output from the code execution

        Raises:
            Exception: If code execution fails
        """
        with NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(code)
            temp_file = f.name

        try:
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )

            if result.returncode != 0:
                error_output = result.stderr or result.stdout
                raise RuntimeError(f"Code execution failed:\n{error_output}")

            output = result.stdout.strip()
            return output
        finally:
            try:
                os.unlink(temp_file)
            except Exception as e:
                logger.debug(f"Failed to clean up temp file: {e}")

    def _is_valid_output(self, output: str) -> bool:
        """
        Validate if the output is meaningful (non-empty, not just warnings).

        Args:
            output: The output to validate

        Returns:
            bool: True if output is valid and meaningful
        """
        if not output:
            return False

        # Filter out just warnings or empty lines
        lines = [line.strip() for line in output.split("\n") if line.strip()]
        if not lines:
            return False

        # Filter out common non-output lines
        non_output_patterns = [
            r"^(Downloading|Hf_user_agent|Warning|Traceback|Using.*device)",
        ]

        meaningful_lines = []
        for line in lines:
            is_noise = any(re.search(pattern, line) for pattern in non_output_patterns)
            if not is_noise:
                meaningful_lines.append(line)

        return len(meaningful_lines) > 0

    def _debug_code_with_llm(self, code: str, error_message: str) -> str:
        """
        Use LLM to debug code and suggest fixes.

        Args:
            code: The original code that failed
            error_message: The error message from execution

        Returns:
            str: The debugged/fixed code

        Raises:
            LlmUnavailable: If LLM inference fails
        """
        if self._llm is None:
            self._llm = LlmEvaluator(self._llm_config)

        prompt = (
            "You are an expert Python debugger. Fix the following Python code that failed with an error. "
            "Return ONLY the corrected Python code, without explanations or markdown formatting.\n\n"
            f"Original code:\n{code}\n\n"
            f"Error:\n{error_message}\n\n"
            "Fixed code:"
        )

        try:
            response = self._llm._client.text_generation(
                prompt,
                max_new_tokens=len(code) + 100,
                temperature=0.3,
            )
        except Exception as exc:
            raise LlmUnavailable(f"Failed to get LLM response: {exc}") from exc

        # Extract the code from the response
        # Try to find code blocks first
        code_match = re.search(r"```(?:python)?\s*\n(.*?)\n```", response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # If no code block, return the response as-is (strip common prefixes)
        fixed_code = response.strip()
        if fixed_code.startswith("Fixed code:"):
            fixed_code = fixed_code[len("Fixed code:") :].strip()

        return fixed_code
