from acme_cli.utils import (clamp, contains_keywords, timed_operation,
                            word_count)


def test_clamp_bounds() -> None:
    assert clamp(-1.0) == 0.0
    assert clamp(1.5) == 1.0


def test_contains_keywords_counts() -> None:
    assert contains_keywords("Accuracy and F1", ["accuracy", "f1"]) == 2


def test_timed_operation_returns_elapsed() -> None:
    with timed_operation() as elapsed:
        pass
    assert isinstance(elapsed(), int)


def test_word_count_handles_none() -> None:
    assert word_count(None) == 0
