from pathlib import Path

from acme_cli.input_loader import parse_url_file


def test_parse_url_file(tmp_path: Path) -> None:
    content = "\n".join(
        [
            "https://huggingface.co/datasets/acme/demo",
            "https://github.com/acme/repo",
            "https://huggingface.co/acme/model",
        ]
    )
    url_file = tmp_path / "urls.txt"
    url_file.write_text(content)

    targets = parse_url_file(url_file)

    assert len(targets) == 1
    target = targets[0]
    assert target.model_url.endswith("acme/model")
    assert target.dataset_urls == ["https://huggingface.co/datasets/acme/demo"]
    assert target.code_urls == ["https://github.com/acme/repo"]
