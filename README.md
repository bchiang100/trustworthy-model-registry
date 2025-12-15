# ACME Trustworthy Model Registry

This repository implements Phase 2 of the ECE46100 ACME Corporation Model Registry. This tool allows for clients to upload, download, search, and interact with models to the registry through both a programmatic RESTful API and a frontend interface. All models requested for ingestion additionally have ratings corresponding to their quality to determine if they meet minimum standards for ACME. 

## Getting Started
API: http://3.22.117.94/api/v1 
Web UI: http://13.58.108.214/

## Runtime Configuration

- `LOG_FILE`: absolute path for log output. Defaults to stderr when unset.
- `HUGGINGFACEHUB_API_TOKEN` / `HF_API_TOKEN`: token used for Hugging Face Hub and Inference API calls. Required to exercise the LLM-backed metric at scale.
- `GITHUB_TOKEN`: token used for GitHub API for metrics to retrieve repository information.

## Ratings

Each line in the scoring exposes the following fields:

| Field | Type | Description |
| --- | --- | --- |
| `net_score` | float | Weighted aggregate of all sub-metrics |
| `*_latency` | int | Milliseconds to compute the paired metric |
| `ramp_up_time` | float | Documentation clarity (LLM-assisted) |
| `bus_factor` | float | Diversity + activity of Hugging Face commit authors |
| `performance_claims` | float | Strength of empirical evidence (LLM-assisted) |
| `license` | float | License permissiveness assessment |
| `size_score` | object | Hardware compatibility scores `{raspberry_pi, jetson_nano, desktop_pc, aws_server}` |
| `dataset_and_code_score` | float | Presence and quality of linked datasets/code |
| `dataset_quality` | float | Dataset governance, size, and documentation |
| `code_quality` | float | Static code health heuristics on the cloned repo |
| `reviewedness` | float | Percent of repository code that comes from pull requests|
| `reproducibility` | float | How easily the code in a README for an artifact can be executed (potentially with AI agentic assistance) |
| `tree_score` | float | The average of the scores for artifacts in the lineage graph of this artifact |

Latencies are rounded to milliseconds as required.

## Metric Design Highlights

- **Hugging Face API usage**: Downloads, likes, tags, commit history, and dataset metadata are retrieved via `huggingface_hub.HfApi`.
- **Local analysis**: Repositories are cached with `snapshot_download` and inspected for README structure, tests, lint configs, and sample code.
- **LLM-assisted scoring**: `LlmEvaluator` queries the Hugging Face Inference API to rate documentation clarity and performance claims. When inference is unavailable, deterministic heuristics keep the pipeline running and log a warning.
- **Size scoring**: Weight files are sized using repository metadata and graded against hardware targets. Documentation-only clones prevent oversized downloads while retaining local analysis for other metrics.
- **Net score weighting**: `{ramp_up_time: 0.15, bus_factor: 0.10, performance_claims: 0.15, license: 0.10, size_score: 0.10, dataset_and_code_score: 0.10, dataset_quality: 0.15, code_quality: 0.15}`. Weights reflect Sarah’s emphasis on documentation quality, reproducibility, and maintainability.

## Testing & Quality

- `pytest` with coverage (`./run test`) achieves high coverage across all core functionalities.
- Tests mock external services and the LLM to avoid network dependencies.
- Critical components (URL parsing, context building, metrics, registry, runner, scoring pipeline) are unit tested.

## Team
- Parin Timbadia 
- Bryan Chiang
- Daniel Wu
- Evan Zhang 
