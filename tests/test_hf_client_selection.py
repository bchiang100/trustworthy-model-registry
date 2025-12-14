from acme_cli.hf.client import HfClient
from acme_cli.types import RepoFile


def test_choose_preferred_file_prefers_weights():
    client = HfClient()
    files = [
        RepoFile(path="README.md", size_bytes=100),
        RepoFile(path="pytorch_model.bin", size_bytes=500000),
        RepoFile(path="model.safetensors", size_bytes=400000),
    ]
    choice = client.choose_preferred_file(files)
    assert choice in {"pytorch_model.bin", "model.safetensors"}


def test_choose_preferred_file_chooses_largest_when_no_preference():
    client = HfClient()
    files = [
        RepoFile(path="a.txt", size_bytes=100),
        RepoFile(path="b.dat", size_bytes=1000),
    ]
    assert client.choose_preferred_file(files) == "b.dat"


def test_hf_hub_download_wraps_and_returns_path(monkeypatch, tmp_path):
    called = {}

    def fake_hf_hub_download(*, repo_id, filename, repo_type, cache_dir, token=None):
        out = tmp_path / filename
        out.write_text("x")
        called['args'] = (repo_id, filename, repo_type, str(cache_dir))
        return str(out)

    monkeypatch.setattr('huggingface_hub.hf_hub_download', fake_hf_hub_download)
    client = HfClient()
    p = client.hf_hub_download('org/repo', 'pytorch_model.bin', repo_type='model', cache_dir=str(tmp_path))
    assert p and p.endswith('pytorch_model.bin')
    assert called['args'][0] == 'org/repo'
