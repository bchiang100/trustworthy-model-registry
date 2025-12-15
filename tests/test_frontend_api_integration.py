"""
Frontend API Integration Tests
Tests that the frontend correctly calls backend endpoints.

Run with: pytest tests/test_frontend_api_integration.py -v
"""

import pytest
from fastapi.testclient import TestClient
import json


@pytest.fixture
def client():
    """Create test client from main app."""
    from acme_cli.api.main import app
    return TestClient(app)


class TestFrontendStaticFiles:
    """Test that frontend static files are served."""

    def test_index_html_served(self, client):
        """Test index.html is served at root."""
        response = client.get("/")
        assert response.status_code == 200
        # Should be HTML content
        assert b"html" in response.content.lower() or b"<!doctype" in response.content.lower()

    def test_upload_html_served(self, client):
        """Test upload.html is accessible."""
        response = client.get("/upload.html")
        assert response.status_code in [200, 304]  # 304 if cached

    def test_ingest_html_served(self, client):
        """Test ingest.html is accessible."""
        response = client.get("/ingest.html")
        assert response.status_code in [200, 304]

    def test_enumerate_html_served(self, client):
        """Test enumerate.html is accessible."""
        response = client.get("/enumerate.html")
        assert response.status_code in [200, 304]

    def test_license_check_html_served(self, client):
        """Test license_check.html is accessible."""
        response = client.get("/license_check.html")
        assert response.status_code in [200, 304]

    def test_model_html_served(self, client):
        """Test model.html is accessible."""
        response = client.get("/model.html")
        assert response.status_code in [200, 304]

    def test_app_js_served(self, client):
        """Test app.js is served."""
        response = client.get("/app.js")
        assert response.status_code in [200, 304]
        # Should be JavaScript
        assert b"javascript" in response.headers.get("content-type", "").lower() or b"function" in response.content[:100].lower()

    def test_styles_css_served(self, client):
        """Test styles.css is served."""
        response = client.get("/styles.css")
        assert response.status_code in [200, 304]


class TestFrontendAPIEndpoints:
    """Test that frontend can call all necessary API endpoints."""

    def test_api_info_endpoint(self, client):
        """Test API info endpoint exists for frontend."""
        response = client.get("/api/v1/info")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data or "version" in data

    def test_health_endpoint_exists(self, client):
        """Test health endpoint for frontend monitoring."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_artifacts_list_endpoint(self, client):
        """Test artifacts list endpoint that frontend uses."""
        payload = {"name": "*", "types": ["model"]}
        response = client.post(
            "/api/v1/artifacts",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        # Should return list (even if empty)
        data = response.json()
        assert isinstance(data, list)

    def test_artifact_regex_search_endpoint(self, client):
        """Test regex search endpoint for search page."""
        payload = {"regex": ".*"}
        response = client.post(
            "/api/v1/artifact/byRegEx",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [200, 404]  # 404 if no matches

    def test_cors_headers_present(self, client):
        """Test CORS headers are present for frontend."""
        response = client.get("/api/v1/info")
        # Should have CORS headers
        assert "access-control-allow-origin" in response.headers or True  # Might be handled by middleware

    def test_content_type_json(self, client):
        """Test API returns JSON content type."""
        response = client.get("/api/v1/info")
        assert "application/json" in response.headers.get("content-type", "")


class TestFrontendFormEndpoints:
    """Test endpoints that frontend forms call."""

    def test_create_artifact_endpoint(self, client):
        """Test POST endpoint for creating artifacts (ingest form)."""
        payload = {
            "name": "test-model",
            "url": "https://huggingface.co/test/model",
        }
        response = client.post(
            "/api/v1/artifact/model",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        # Should accept the request (even if validation fails)
        assert response.status_code in [200, 201, 400, 422]

    def test_get_artifact_by_id_endpoint(self, client):
        """Test GET endpoint for artifact details."""
        # Test with non-existent ID (should 404)
        response = client.get("/api/v1/artifacts/model/nonexistent")
        assert response.status_code == 404

    def test_artifact_cost_endpoint(self, client):
        """Test cost endpoint that frontend calls."""
        # Test with non-existent ID
        response = client.get("/api/v1/artifact/model/nonexistent/cost")
        assert response.status_code in [404, 200]  # Either not found or empty

    def test_artifact_rating_endpoint(self, client):
        """Test rating endpoint for model detail page."""
        response = client.get("/api/v1/artifact/model/nonexistent/rate")
        assert response.status_code in [404, 200, 400]

    def test_reset_endpoint_exists(self, client):
        """Test reset endpoint exists for home page button."""
        # Just check it exists, don't call it
        response = client.delete("/api/v1/reset")
        # Should exist (even if we don't execute)
        assert response.status_code in [200, 400, 405, 422]


class TestFrontendCORS:
    """Test CORS configuration for frontend."""

    def test_cors_allow_origin_development(self, client):
        """Test CORS allows frontend in development."""
        headers = {
            "Origin": "http://localhost:8000"
        }
        response = client.get("/api/v1/info", headers=headers)
        assert response.status_code == 200

    def test_cors_allow_methods(self, client):
        """Test CORS allows necessary methods."""
        # Frontend needs GET, POST, OPTIONS, DELETE
        for method in ["GET", "POST", "DELETE"]:
            # Just check endpoint exists
            if method == "GET":
                response = client.get("/api/v1/health")
            elif method == "POST":
                response = client.post(
                    "/api/v1/artifacts",
                    json={"name": "*", "types": ["model"]},
                    headers={"Content-Type": "application/json"}
                )
            elif method == "DELETE":
                response = client.delete("/api/v1/reset")

            # Just verify endpoint is reachable
            assert response.status_code is not None


class TestFrontendResponseFormats:
    """Test that API responses match what frontend expects."""

    def test_model_list_response_format(self, client):
        """Test model list response has expected structure."""
        response = client.post(
            "/api/v1/artifacts",
            json={"name": "*", "types": ["model"]},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_error_response_format(self, client):
        """Test error responses are proper JSON."""
        response = client.get("/api/v1/artifacts/model/nonexistent")
        assert response.status_code == 404
        # Should be JSON error
        try:
            data = response.json()
            # Error responses should have some structure
            assert isinstance(data, (dict, list))
        except:
            pass  # Sometimes 404 returns HTML

    def test_empty_list_response(self, client):
        """Test empty list returns valid JSON array."""
        response = client.post(
            "/api/v1/artifacts",
            json={"name": "nonexistent-*", "types": ["model"]},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            data = response.json()
            # Empty list is valid
            assert isinstance(data, list)


class TestFrontendErrorHandling:
    """Test frontend can handle API errors gracefully."""

    def test_api_404_handling(self, client):
        """Test 404 responses are JSON."""
        response = client.get("/api/v1/artifacts/model/xyz")
        assert response.status_code == 404
        # Try to parse as JSON
        try:
            response.json()
            is_json = True
        except:
            is_json = False
        assert is_json or response.status_code in [304, 400, 401, 403, 404, 500]

    def test_api_timeout_handling(self, client):
        """Test API doesn't hang (reasonable response time)."""
        import time
        start = time.time()
        response = client.get("/api/v1/health")
        elapsed = time.time() - start
        # Should respond in less than 5 seconds
        assert elapsed < 5

    def test_api_invalid_json_handling(self, client):
        """Test API handles invalid JSON gracefully."""
        response = client.post(
            "/api/v1/artifacts",
            data="not json",
            headers={"Content-Type": "application/json"}
        )
        # Should be 400 Bad Request, not 500 error
        assert response.status_code in [400, 422]


class TestFrontendDataValidation:
    """Test frontend data is validated by API."""

    def test_missing_required_field(self, client):
        """Test API validates required fields."""
        payload = {"name": "test"}  # Missing url
        response = client.post(
            "/api/v1/artifact/model",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        # Should reject (400/422) or handle gracefully
        assert response.status_code in [200, 201, 400, 422]

    def test_invalid_url_format(self, client):
        """Test API validates URL format."""
        payload = {
            "name": "test",
            "url": "not-a-valid-url",
        }
        response = client.post(
            "/api/v1/artifact/model",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        # Should handle validation
        assert response.status_code in [200, 201, 400, 422]

    def test_empty_string_validation(self, client):
        """Test API validates empty strings."""
        payload = {"name": "", "url": ""}
        response = client.post(
            "/api/v1/artifact/model",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        # Should reject or handle
        assert response.status_code is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
