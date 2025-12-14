import pytest

from acme_cli.hf.client import HfClient


def test_choose_preferred_file_on_codebert_repo():
    """Live test against jiekeshi/CodeBERT-50MB-Clone-Detection to ensure
    the selection heuristic picks a sensible weight file for download.

    This test will be skipped when the HF API is unreachable or when the
    repository metadata does not expose file information.
    """
    repo_id = "jiekeshi/CodeBERT-50MB-Clone-Detection"
    client = HfClient()

    info = client.get_model(repo_id)
    if info is None:
        pytest.skip("Hugging Face API inaccessible or model info not available")

    files = info.files or []
    if not files:
        pytest.skip("No file listing available for repo; skipping live selection test")

    choice = client.choose_preferred_file(files)
    assert choice in [f.path for f in files]

    # Ensure the selected file looks like a weights file (preferred patterns),
    # otherwise it should at least be the largest file in the listing.
    preferred_patterns = [
        "pytorch_model.bin",
        ".safetensors",
        "flax_model.msgpack",
        ".msgpack",
        ".bin",
        ".pt",
        ".ckpt",
        ".h5",
        ".onnx",
    ]

    if not any(p in choice for p in preferred_patterns):
        # fallback: choice must be the largest file
        largest = max(files, key=lambda f: (f.size_bytes or 0)).path
        assert choice == largest
