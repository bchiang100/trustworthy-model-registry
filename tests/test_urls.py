from acme_cli.urls import (is_code_url, is_dataset_url, is_model_url,
                           parse_artifact_url)


def test_parse_huggingface_model_url() -> None:
    parsed = parse_artifact_url("https://huggingface.co/acme/model/tree/main")
    assert parsed.platform == "huggingface"
    assert parsed.kind == "model"
    assert parsed.repo_id == "acme/model"


def test_parse_dataset_url() -> None:
    url = "https://huggingface.co/datasets/acme/demo"
    assert is_dataset_url(url)
    parsed = parse_artifact_url(url)
    assert parsed.repo_id == "acme/demo"


def test_parse_code_urls() -> None:
    assert is_code_url("https://github.com/org/repo")
    assert is_code_url("https://gitlab.com/org/repo")
    assert not is_code_url("https://example.com/unknown")


def test_is_model_url_otherwise() -> None:
    assert not is_model_url("https://example.com/resource")


def test_parse_dataset_without_owner() -> None:
    url = "https://huggingface.co/datasets/ag_news"
    parsed = parse_artifact_url(url)
    assert parsed.kind == "dataset"
    assert parsed.repo_id == "ag_news"


def test_parse_model_without_owner() -> None:
    url = "https://huggingface.co/distilbert-base-uncased"
    parsed = parse_artifact_url(url)
    assert parsed.kind == "model"
    assert parsed.repo_id == "distilbert-base-uncased"
