import pytest
from fastapi.testclient import TestClient

import acme_cli.api.main as api_main
from acme_cli.api.routes import models as models_route


def test_license_endpoint_parses_model_license(monkeypatch):
    client = TestClient(api_main.app)

    aid = "m1"
    models_route.artifacts_metadata[aid] = {
        "name": "my-model",
        "type": "model",
        "url": "https://huggingface.co/acme-org/my-model",
    }

    # stub GitHub README fetch to show a project license
    monkeypatch.setattr(models_route, "get_github_readme", lambda url, timeout=2: (True, "# Project\nLicense: MIT"))

    # stub HF client to return model metadata with license in card_data
    class FakeModel:
        card_data = {"license": "MIT"}

    monkeypatch.setattr(models_route.hf_client, "get_model", lambda repo_id: FakeModel())
    # stub LLM judge to avoid external calls and return True for compatible licenses
    monkeypatch.setattr(models_route.LlmEvaluator, "judge_license_compatibility", lambda self, a, b: True)

    resp = client.post(f"/api/v1/artifact/model/{aid}/license-check/", json={"github_url": "https://github.com/acme-org/project"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_has_license"] is True
    assert body["project_license"].lower().startswith("mit")
    assert body["model_license"].lower().startswith("mit")
    assert body["license_compatible"] is True

    models_route.artifacts_metadata.pop(aid, None)


def test_license_endpoint_llm_failure_falls_back_false(monkeypatch):
    client = TestClient(api_main.app)

    aid = "m2"
    models_route.artifacts_metadata[aid] = {
        "name": "other-model",
        "type": "model",
        "url": "https://huggingface.co/acme-org/other-model",
    }

    monkeypatch.setattr(models_route, "get_github_readme", lambda url, timeout=2: (True, "# Project\nLicense: MIT"))

    class FakeModel2:
        card_data = {"license": "GPL-3.0"}

    monkeypatch.setattr(models_route.hf_client, "get_model", lambda repo_id: FakeModel2())
    # make the LLM raise to simulate unavailability
    def raise_exc(self, a, b):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(models_route.LlmEvaluator, "judge_license_compatibility", raise_exc)

    resp = client.post(f"/api/v1/artifact/model/{aid}/license-check/", json={"github_url": "https://github.com/acme-org/project"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_has_license"] is True
    assert body["license_compatible"] is False

    models_route.artifacts_metadata.pop(aid, None)
