from acme_cli.net_score import compute_net_score
from acme_cli.types import EvaluationOutcome, MetricResult


def test_compute_net_score_with_complete_metrics() -> None:
    metrics = {
        "ramp_up_time": MetricResult("ramp_up_time", 0.8, 10),
        "bus_factor": MetricResult("bus_factor", 0.6, 5),
        "performance_claims": MetricResult("performance_claims", 0.7, 7),
        "license": MetricResult("license", 1.0, 3),
        "size_score": MetricResult("size_score", {"raspberry_pi": 0.9, "jetson_nano": 0.7, "desktop_pc": 0.6, "aws_server": 0.5}, 4),
        "dataset_and_code_score": MetricResult("dataset_and_code_score", 0.9, 6),
        "dataset_quality": MetricResult("dataset_quality", 0.8, 2),
        "code_quality": MetricResult("code_quality", 0.7, 5),
    }
    outcome = EvaluationOutcome(metrics=metrics, failures=[])

    net_result = compute_net_score(outcome)

    assert net_result.name == "net_score"
    assert 0 <= net_result.value <= 1
    assert net_result.latency_ms >= 0


def test_compute_net_score_handles_missing_metrics() -> None:
    outcome = EvaluationOutcome(metrics={}, failures=[])

    net_result = compute_net_score(outcome)

    assert net_result.value == 0.0
