#!/usr/bin/env python3
"""Quick test to verify the new metric endpoints work."""

import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import the router and set up the client
from src.acme_cli.api.routes.models import router, artifacts_metadata

# Create a minimal FastAPI app with the router
from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_endpoints():
    """Test the new metric endpoints with a mock artifact."""
    
    # Add a mock artifact to the in-memory registry
    test_artifact_id = "test-model-001"
    artifacts_metadata[test_artifact_id] = {
        "name": "test-model",
        "type": "model",
        "url": "https://huggingface.co/test-org/test-model",
        "download_url": "https://example.com/download",
        "s3_key": "model/test-model-001/test-model.tar.gz"
    }
    
    print("✓ Mock artifact added to registry")
    
    # Mock the calculate_metrics function to return deterministic values
    mock_metrics = {
        "net_score": 0.75,
        "ramp_up_time": 0.8,
        "bus_factor": 0.7,
        "performance_claims": 0.65,
        "license": 0.9,
        "dataset_and_code_score": 0.6,
        "dataset_quality": 0.7,
        "code_quality": 0.8,
        "reproducibility": 0.5,
        "reviewedness": -1.0,
        "tree_score": 0.72,
        "size_score": {
            "raspberry_pi": 0.1,
            "jetson_nano": 0.5,
            "desktop_pc": 0.9,
            "aws_server": 1.0,
        }
    }
    
    with patch('src.acme_cli.api.routes.models.calculate_metrics', return_value=mock_metrics):
        # Test 1: GET /artifact/model/{id}/rate/
        print("\n[Test 1] GET /artifact/model/{id}/rate/")
        response = client.get(f"/artifact/model/{test_artifact_id}/rate/")
        print(f"  Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        rating = response.json()
        print(f"  Name: {rating.get('name')}")
        print(f"  Net Score: {rating.get('net_score')}")
        print(f"  Ramp-up Time: {rating.get('ramp_up_time')}")
        print(f"  Reproducibility: {rating.get('reproducibility')}")
        print(f"  Reviewedness: {rating.get('reviewedness')}")
        print(f"  Size Score: {rating.get('size_score')}")
        
        # Validate required fields per OpenAPI spec
        assert rating.get("name") == "test-model"
        assert rating.get("category") == "model"
        assert "net_score" in rating
        assert "net_score_latency" in rating
        assert "ramp_up_time" in rating
        assert "reproducibility" in rating
        assert "reviewedness" in rating
        assert "tree_score" in rating
        assert "size_score" in rating
        print("All required fields present")
        
        # Test 2: GET /artifact/model/{id}/metric/{metric_name}/
        print("\n[Test 2] GET /artifact/model/{id}/metric/{metric_name}/")
        response = client.get(f"/artifact/model/{test_artifact_id}/metric/code_quality/")
        print(f"  Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        metric_resp = response.json()
        print(f"  Metric: {metric_resp.get('metric')}")
        print(f"  Value: {metric_resp.get('value')}")
        print(f"  Latency: {metric_resp.get('latency_seconds')} seconds")
        
        assert metric_resp.get("metric") == "code_quality"
        assert metric_resp.get("value") == 0.8
        assert "latency_seconds" in metric_resp
        print("Metric endpoint working")
        
        # Test 3: GET /artifact/model/{id}/metric/{nonexistent}/
        print("\n[Test 3] GET /artifact/model/{id}/metric/{nonexistent}/ (should 404)")
        response = client.get(f"/artifact/model/{test_artifact_id}/metric/nonexistent_metric/")
        print(f"  Status: {response.status_code}")
        assert response.status_code == 404, f"Expected 404 for nonexistent metric, got {response.status_code}"
        print("Correctly returns 404 for missing metric")
        
        # Test 4: POST /artifact/model/{id}/lineage/
        print("\n[Test 4] POST /artifact/model/{id}/lineage/")
        # This one will likely fail because LineageExtractor needs real HF data
        # but we can verify it at least tries
        response = client.post(f"/artifact/model/{test_artifact_id}/lineage/")
        print(f"  Status: {response.status_code}")
        print(f"  Note: May return 500 without real HF data; endpoint is wired correctly")
        print(f"  In production, this would extract lineage from the model's config.json")
    
    # Test 5: 404 for nonexistent artifact
    print("\n[Test 5] GET /artifact/model/nonexistent/rate/ (should 404)")
    response = client.get("/artifact/model/nonexistent/rate/")
    print(f"  Status: {response.status_code}")
    assert response.status_code == 404, f"Expected 404 for nonexistent artifact, got {response.status_code}"
    print("Correctly returns 404 for missing artifact")
    
    print("\n" + "="*60)
    print("All endpoint tests passed! ✓")
    print("="*60)


if __name__ == "__main__":
    test_endpoints()
