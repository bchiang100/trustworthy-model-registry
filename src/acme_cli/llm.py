"""
Wrapper around the Hugging Face Inference API for lightweight scoring in ACME Registry.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from huggingface_hub import InferenceClient

from acme_cli.utils import clamp

DEFAULT_LLM_MODEL = "meta-llama/Llama-3.2-1B-Instruct"


class LlmUnavailable(RuntimeError):
    """
    Raised when an LLM inference could not be completed.
    """


@dataclass(slots=True)
class LlmConfig:
    """
    Configuration for LLM evaluation, including model and token.
    """
    model: str = os.getenv("ACME_LLM_MODEL", DEFAULT_LLM_MODEL)
    token: str | None = os.getenv("HUGGINGFACEHUB_API_TOKEN") or os.getenv(
        "HF_API_TOKEN"
    ) # this API token is used to gain access to LLMs from HF API
    timeout: float = float(os.getenv("ACME_LLM_TIMEOUT", "30"))


class LlmEvaluator:
    """
    Simple text-to-score evaluator using an instruction-following LLM.
    """

    def __init__(self, config: LlmConfig | None = None) -> None:
        self._config = config or LlmConfig()
        self._client = InferenceClient(
            model=self._config.model,
            token=self._config.token,
            timeout=self._config.timeout,
        )

    def score_clarity(self, readme_text: str) -> float:
        """
        Score the clarity of a README using the LLM.
        Returns a float score.
        """
        prompt = (
            "You are reviewing developer documentation. Rate how easily an engineer could "
            "understand how to use the project. Return a single decimal number between 0 and 1, "
            "where 1 means very clear and 0 means unusable.\nDocumentation:\n"
            + readme_text
        )
        return self._inference_to_score(prompt)

    def score_performance_claims(self, readme_text: str) -> float:
        prompt = (
            "You are an auditor verifying machine learning performance claims. Based on the text, "
            "rate the strength of empirical evidence (benchmarks, metrics, ablations). Return only a "
            "number between 0 and 1.\nText:\n" + readme_text
        )
        return self._inference_to_score(prompt)

    def _inference_to_score(self, prompt: str) -> float:
        try:
            response = self._client.text_generation(
                prompt, max_new_tokens=16, temperature=0.0
            )
        except Exception as exc:  # noqa: BLE001
            raise LlmUnavailable(str(exc)) from exc

        match = re.search(r"([01](?:\.\d+)?)", response)
        if not match:
            raise LlmUnavailable(
                f"Model response did not contain a score: {response!r}"
            )
        return clamp(float(match.group(1)))

    def judge_license_compatibility(self, project_license: str, model_license: str) -> bool:
        """Ask the LLM whether the project license is compatible with the model license.

        Returns True if the model can be used under the project license, False otherwise.
        Any errors or unparsable responses fall back to False.
        """
        prompt = (
            "You are an expert open-source license compatibility checker. "
            "Given a project license and a model license, answer with only 'true' if the project "
            "license permits using the model for fine-tuning and inference under its terms, "
            "or 'false' otherwise.\nProject license:\n"
            + project_license
            + "\nModel license:\n"
            + model_license
            + "\nAnswer:"
        )
        try:
            response = self._client.text_generation(
                prompt, max_new_tokens=16, temperature=0.0
            )
            text = str(response)
            m = re.search(r"\b(true|false)\b", text, re.I)
            if not m:
                return False
            return m.group(1).lower() == "true"
        except Exception:
            return False


__all__ = ["LlmEvaluator", "LlmUnavailable", "LlmConfig", "DEFAULT_LLM_MODEL"]
