import time
import pytest

# Skip this test file when FastAPI (and TestClient) aren't available in the
# execution environment. This keeps the broader test-suite runnable in minimal
# CI/dev setups that don't have web dependencies installed.
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import acme_cli.api.main as api_main
from acme_cli.api.routes import models as models_route
from acme_cli.lineage_graph import LineageGraph, LineageNode


def make_fake_graph():
    g = LineageGraph(root_repo_id="acme-org/my-finetuned-model")
    g.add_node("acme-org/my-finetuned-model", parents=["bigmodels/base-llm"], depth=0, metadata={"pipeline_tag": "text-generation"})
    g.add_node("bigmodels/base-llm", parents=[], depth=1, metadata={"pipeline_tag": "text-generation"})
    return g


def test_lineage_and_metrics_endpoints(monkeypatch):
    # Prepare TestClient
    client = TestClient(api_main.app)

    # Insert a synthetic artifact into the in-memory registry
    aid = "test-artifact-123"
    models_route.artifacts_metadata[aid] = {
        "name": "my-finetuned-model",
        "type": "model",
        "url": "https://huggingface.co/acme-org/my-finetuned-model",
    }

    # Patch calculate_metrics to return deterministic values
    fake_metrics = {
        "net_score": 0.75,
        "ramp_up_time": 0.6,
        "bus_factor": 0.5,
        "performance_claims": 0.4,
        "license": 1.0,
        "dataset_and_code_score": 0.7,
        "dataset_quality": 0.8,
        "code_quality": 0.9,
        "reproducibility": 1.0,
        "reviewedness": 0.2,
        "tree_score": 0.65,
        "size_score": {
            "raspberry_pi": 1.0,
            "jetson_nano": 0.7,
            "desktop_pc": 0.4,
            "aws_server": 0.1,
        },
    }

    monkeypatch.setattr(models_route, "calculate_metrics", lambda url: fake_metrics)

    # Patch LineageExtractor.extract to return a fake graph
    monkeypatch.setattr(models_route, "LineageExtractor", lambda: None)

    # Instead, patch the function used in the endpoint by creating a dummy extractor
    class DummyExtractor:
        def extract(self, repo_id, max_depth=5):
            return make_fake_graph()

    monkeypatch.setattr(models_route, "LineageExtractor", lambda: DummyExtractor())

    # Call POST lineage endpoint
    resp = client.post(f"/api/v1/artifact/model/{aid}/lineage/")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "nodes" in body and "edges" in body
    assert any(n["artifact_id"] == "acme-org/my-finetuned-model" for n in body["nodes"])

    # Call GET rate endpoint
    resp2 = client.get(f"/api/v1/artifact/model/{aid}/rate/")
    assert resp2.status_code == 200, resp2.text
    rating = resp2.json()
    assert rating["net_score"] == fake_metrics["net_score"]
    assert rating["code_quality"] == fake_metrics["code_quality"]

    # Call single metric endpoint
    resp3 = client.get(f"/api/v1/artifact/model/{aid}/metric/code_quality/")
    assert resp3.status_code == 200, resp3.text
    single = resp3.json()
    assert single["metric"] == "code_quality"
    assert single["value"] == fake_metrics["code_quality"]

    # Clean up
    models_route.artifacts_metadata.pop(aid, None)
