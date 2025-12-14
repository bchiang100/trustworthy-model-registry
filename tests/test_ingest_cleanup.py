import os
import tempfile
import shutil
from fastapi.testclient import TestClient

import acme_cli.api.main as api_main
from acme_cli.api.routes import models as models_route


def test_ingest_cleanup_removes_tempdir(monkeypatch, tmp_path):
    client = TestClient(api_main.app)

    # Prepare a fake artifact URL and ensure it will be ingested
    artifact_url = "https://huggingface.co/example/repo"
    payload = {"name": "tmp-model", "url": artifact_url}

    # Create a temporary directory that simulates download output with extra files
    temp_dir = tempfile.mkdtemp(dir=str(tmp_path))
    tar_path = os.path.join(temp_dir, "id123.tar.gz")
    # create the archive file and an extra transient file to simulate leftover cache
    with open(tar_path, "wb") as fh:
        fh.write(b"x")
    extra_file = os.path.join(temp_dir, ".cache")
    with open(extra_file, "w") as fh:
        fh.write("cache")

    # Monkeypatch download_artifact_from_hf to return our tar_path
    monkeypatch.setattr(models_route, "download_artifact_from_hf", lambda url, aid: tar_path)

    # Monkeypatch upload_to_s3 to avoid real S3 calls
    monkeypatch.setattr(models_route, "upload_to_s3", lambda local, key: "https://example.com/download")
    # Ensure rating check passes so ingest proceeds to download & cleanup
    monkeypatch.setattr(models_route, "calculate_metrics", lambda url: {"net_score": 1.0})

    # POST to ingest endpoint
    resp = client.post(f"/api/v1/artifact/model", json=payload)
    assert resp.status_code in (200, 201, 424, 500)  # ingest may rate-limit etc; primary goal is cleanup

    # The temp dir should be removed by the ingest cleanup logic
    assert not os.path.exists(temp_dir)

    # Tidy up if still present
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass
