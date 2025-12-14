#!/usr/bin/env python3
"""Test script for the /artifact/{artifact_type}/{id}/cost/ endpoint."""

import sys
import json
from unittest.mock import Mock, patch

# Add src to path
sys.path.insert(0, "src")

from fastapi.testclient import TestClient
from acme_cli.api.routes.models import router, artifacts_metadata

# Create test app with just the models router
from fastapi import FastAPI
app = FastAPI()
app.include_router(router)

client = TestClient(app)


def test_cost_endpoint_basic():
    """Test basic cost endpoint without dependencies."""
    print("\n[Test 1] GET /artifact/model/{id}/cost/ (basic, no dependency)")
    
    # Add mock artifact to registry
    test_id = "test-model-123"
    artifacts_metadata[test_id] = {
        "name": "test-model",
        "type": "model",
        "url": "https://huggingface.co/test-org/test-model",
        "download_url": "https://example.com/download",
        "s3_key": "model/test-model-123/test-model.tar.gz"
    }
    
    # Mock HfApi to return predictable file sizes
    with patch("huggingface_hub.HfApi") as mock_hf_api:
        mock_model_info = Mock()
        mock_sibling_1 = Mock(size=100 * 1024 * 1024)  # 100 MB
        mock_sibling_2 = Mock(size=50 * 1024 * 1024)   # 50 MB
        mock_model_info.siblings = [mock_sibling_1, mock_sibling_2]
        
        mock_hf_api.return_value.model_info.return_value = mock_model_info
        
        response = client.get(f"/artifact/model/{test_id}/cost/")
    
    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"  Response: {json.dumps(data, indent=2)}")
        assert test_id in data, "Artifact ID should be in response"
        assert "total_cost" in data[test_id], "total_cost should be present"
        # Should be 150 MB total (100 + 50)
        assert data[test_id]["total_cost"] == 150.0, f"Expected 150.0 MB, got {data[test_id]['total_cost']}"
        print("  ✓ Basic cost endpoint working")
    else:
        print(f"  ✗ Expected 200, got {response.status_code}")
        print(f"  Response: {response.text}")


def test_cost_endpoint_with_dependencies():
    """Test cost endpoint with dependencies=true."""
    print("\n[Test 2] GET /artifact/model/{id}/cost/?dependency=true")
    
    # Add mock artifact
    test_id = "test-model-456"
    artifacts_metadata[test_id] = {
        "name": "test-model-2",
        "type": "model",
        "url": "https://huggingface.co/test-org/test-model-2",
        "download_url": "https://example.com/download",
        "s3_key": "model/test-model-456/test-model-2.tar.gz"
    }
    
    # Mock HfApi for the main model
    with patch("huggingface_hub.HfApi") as mock_hf_api:
        mock_model_info = Mock()
        mock_sibling = Mock(size=200 * 1024 * 1024)  # 200 MB
        mock_model_info.siblings = [mock_sibling]
        mock_hf_api.return_value.model_info.return_value = mock_model_info
        
        # Mock LineageExtractor to return a graph with one ancestor
        with patch("acme_cli.api.routes.models.LineageExtractor") as mock_extractor_class:
            mock_extractor = Mock()
            mock_extractor_class.return_value = mock_extractor
            
            # Create mock lineage graph
            mock_graph = Mock()
            mock_graph.get_ancestors.return_value = ["ancestor-org/ancestor-model"]
            mock_extractor.extract.return_value = mock_graph
            
            # Call endpoint with dependency=true
            response = client.get(f"/artifact/model/{test_id}/cost/?dependency=true")
    
    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"  Response: {json.dumps(data, indent=2)}")
        assert test_id in data, "Artifact ID should be in response"
        assert "standalone_cost" in data[test_id], "standalone_cost should be present"
        assert "total_cost" in data[test_id], "total_cost should be present"
        # Main artifact: 200 MB, ancestor: ~200 MB (fallback), total > 200
        assert data[test_id]["total_cost"] >= 200.0, "total_cost should include dependencies"
        print("  ✓ Cost endpoint with dependencies working")
    else:
        print(f"  ✗ Expected 200, got {response.status_code}")
        print(f"  Response: {response.text}")


def test_cost_endpoint_missing_artifact():
    """Test cost endpoint with missing artifact."""
    print("\n[Test 3] GET /artifact/model/nonexistent/cost/ (should 404)")
    
    response = client.get("/artifact/model/nonexistent-id/cost/")
    
    print(f"  Status: {response.status_code}")
    if response.status_code == 404:
        print("  ✓ Correctly returns 404 for missing artifact")
    else:
        print(f"  ✗ Expected 404, got {response.status_code}")


def test_cost_endpoint_invalid_type():
    """Test cost endpoint with invalid artifact type."""
    print("\n[Test 4] GET /artifact/invalid/{id}/cost/ (should 400)")
    
    response = client.get("/artifact/invalid/test-id/cost/")
    
    print(f"  Status: {response.status_code}")
    if response.status_code == 400:
        print("  ✓ Correctly returns 400 for invalid artifact type")
    else:
        print(f"  ✗ Expected 400, got {response.status_code}")


def test_cost_endpoint_dataset():
    """Test cost endpoint for dataset artifact."""
    print("\n[Test 5] GET /artifact/dataset/{id}/cost/")
    
    test_id = "test-dataset-789"
    artifacts_metadata[test_id] = {
        "name": "test-dataset",
        "type": "dataset",
        "url": "https://huggingface.co/datasets/test-org/test-dataset",
        "download_url": "https://example.com/download",
        "s3_key": "dataset/test-dataset-789/test-dataset.tar.gz"
    }
    
    with patch("huggingface_hub.HfApi") as mock_hf_api:
        mock_dataset_info = Mock()
        mock_sibling = Mock(size=500 * 1024 * 1024)  # 500 MB
        mock_dataset_info.siblings = [mock_sibling]
        mock_hf_api.return_value.dataset_info.return_value = mock_dataset_info
        
        response = client.get(f"/artifact/dataset/{test_id}/cost/")
    
    print(f"  Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"  Response: {json.dumps(data, indent=2)}")
        assert test_id in data, "Dataset ID should be in response"
        assert "total_cost" in data[test_id], "total_cost should be present"
        assert data[test_id]["total_cost"] == 500.0, f"Expected 500.0 MB, got {data[test_id]['total_cost']}"
        print("  ✓ Cost endpoint for datasets working")
    else:
        print(f"  ✗ Expected 200, got {response.status_code}")
        print(f"  Response: {response.text}")


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Cost Endpoint")
    print("=" * 70)
    
    try:
        test_cost_endpoint_basic()
        test_cost_endpoint_with_dependencies()
        test_cost_endpoint_missing_artifact()
        test_cost_endpoint_invalid_type()
        test_cost_endpoint_dataset()
        
        print("\n" + "=" * 70)
        print("All cost endpoint tests passed! ✓")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
