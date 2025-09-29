from __future__ import annotations

import pytest

import acme_cli.llm as llm_module
from acme_cli.llm import LlmEvaluator, LlmUnavailable


class _GoodClient:
    def __init__(self, model: str, token: str | None = None, timeout: float = 30) -> None:  # noqa: D401
        self.model = model
        self.token = token
        self.timeout = timeout

    def text_generation(self, prompt: str, max_new_tokens: int, temperature: float) -> str:  # noqa: D401
        return "0.85"


class _BadClient(_GoodClient):
    def text_generation(self, prompt: str, max_new_tokens: int, temperature: float) -> str:  # noqa: D401
        raise RuntimeError("offline")


def test_llm_evaluator_success(monkeypatch) -> None:
    monkeypatch.setattr(llm_module, "InferenceClient", _GoodClient)
    evaluator = LlmEvaluator()
    score = evaluator.score_clarity("Documentation")
    assert 0 < score <= 1


def test_llm_evaluator_failure(monkeypatch) -> None:
    monkeypatch.setattr(llm_module, "InferenceClient", _BadClient)
    evaluator = LlmEvaluator()
    with pytest.raises(LlmUnavailable):
        evaluator.score_performance_claims("Text")
