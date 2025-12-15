import sys
from pathlib import Path

# Ensure `src` is on sys.path when running this test module directly
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import json
from fastapi.testclient import TestClient

import acme_cli.api.main as api_main
from acme_cli.api.routes import models as models_route


def test_by_regex_name_match():
    client = TestClient(api_main.app)

    aid = "r1"
    models_route.artifacts_metadata[aid] = {
        "name": "searchable-model",
        "type": "model",
        "url": "",
    }
    print("made it here")

    resp = client.post("/api/v1/artifact/byRegEx/", json={"regex": "searchable"})
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert aid in ids

    models_route.artifacts_metadata.pop(aid, None)

    print("Test 1 Finished")

def test_by_regex_github_readme_match(monkeypatch):
    client = TestClient(api_main.app)

    aid = "gh1"
    # Use a large, public GitHub repo that has a README (avoid small/fake repos)
    models_route.artifacts_metadata[aid] = {
        "name": "no-match-name",
        "type": "model",
        "url": "https://github.com/google-research/bert",
    }

    # Try a real fetch; if the network or GitHub API is unavailable, skip the test
    valid, readme = models_route.get_github_readme(models_route.artifacts_metadata[aid]["url"])
    if not valid or not readme:
        import pytest

        pytest.skip("GitHub API/readme unavailable; skipping network-dependent test")

    print("Made it here 2")
    # ensure the README contains something we can search for
    if "bert" not in readme.lower():
        import pytest

        pytest.skip("Unexpected README contents; skipping unstable test")

    resp = client.post("/api/v1/artifact/byRegEx/", json={"regex": "bert"})
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert aid in ids

    models_route.artifacts_metadata.pop(aid, None)
    print("Test 2 Finished")


def test_by_regex_hf_readme_match(monkeypatch, tmp_path):
    client = TestClient(api_main.app)

    aid = "hf1"
    models_route.artifacts_metadata[aid] = {
        "name": "no-match-name",
        "type": "model",
        "url": "https://huggingface.co/bert-base-uncased",
    }
    # Try a real Hugging Face README download; skip if network/HF API unavailable
    parsed = models_route.parse_artifact_url(models_route.artifacts_metadata[aid]["url"])
    repo_id = getattr(parsed, "repo_id", None)
    if not repo_id:
        import pytest

        pytest.skip("Could not parse HF repo id; skipping")

    try:
        # attempt to download README via the HF client
        local = models_route.hf_client._api.hf_hub_download(repo_id=repo_id, filename="README.md", repo_type="model")
        with open(local, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        import pytest

        pytest.skip("Hugging Face download failed; skipping network-dependent test")

    if "bert" not in content.lower():
        import pytest

        pytest.skip("Unexpected HF README contents; skipping unstable test")

    resp = client.post("/api/v1/artifact/byRegEx/", json={"regex": "bert"})
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert aid in ids

    models_route.artifacts_metadata.pop(aid, None)


def test_by_regex_invalid_regex():
    client = TestClient(api_main.app)

    resp = client.post("/api/v1/artifact/byRegEx/", json={"regex": "(unclosed["})
    assert resp.status_code == 400


if __name__ == "__main__":
    test_by_regex_name_match()
    test_by_regex_github_readme_match()
    test_by_regex_hf_readme_match()
    test_by_regex_invalid_regex()