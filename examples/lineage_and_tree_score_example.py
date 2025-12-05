#!/usr/bin/env python3
"""
Example demonstrating the Lineage Graph and Tree Score metric.

This example shows how to:
1. Extract a model's lineage graph from its config.json
2. Use the lineage to compute a tree score based on ancestor model scores
3. Cache model scores for efficient retrieval
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime

from acme_cli.lineage_graph import LineageExtractor, LineageGraph
from acme_cli.metrics.tree_score import TreeScoreMetric
from acme_cli.score_registry import InMemoryScoreRegistry, FileSystemScoreRegistry
from acme_cli.types import (
    LocalRepository,
    MetricResult,
    ModelContext,
    ModelMetadata,
    RepoFile,
    ScoreTarget,
)


def create_mock_config(base_model: str | None = None) -> dict:
    """Create a mock model config.json."""
    config = {
        "architectures": ["BertForSequenceClassification"],
        "model_type": "bert",
        "num_hidden_layers": 12,
        "hidden_size": 768,
    }
    if base_model:
        config["_name_or_path"] = base_model
    return config


def create_model_context(
    repo_id: str,
    tmp_path: Path,
    base_model: str | None = None,
) -> ModelContext:
    """Create a model context with optional config.json."""
    repo_path = tmp_path / repo_id.replace("/", "_")
    repo_path.mkdir(parents=True, exist_ok=True)

    # Create mock config.json if base_model is specified
    if base_model:
        config = create_mock_config(base_model)
        (repo_path / "config.json").write_text(json.dumps(config), encoding="utf-8")

    return ModelContext(
        target=ScoreTarget(model_url=f"https://huggingface.co/{repo_id}"),
        model_metadata=ModelMetadata(
            repo_id=repo_id,
            display_name=repo_id.split("/")[-1],
            card_data={},
            downloads=1000,
            likes=100,
            last_modified=datetime.now(),
            tags=["text-classification"],
            files=[],
            pipeline_tag="text-classification",
            library_name="transformers",
        ),
        dataset_metadata=None,
        local_repo=LocalRepository(
            repo_id=repo_id,
            repo_type="model",
            path=repo_path,
        ),
        dataset_local_repo=None,
        readme_text=None,
        dataset_readme_text=None,
        commit_authors=["user1", "user2"],
        commit_total=50,
    )


def example_1_lineage_extraction():
    """Example 1: Extract model lineage from config."""
    print("\n" + "=" * 70)
    print("Example 1: Extracting Model Lineage")
    print("=" * 70)

    extractor = LineageExtractor()

    # Create a mock lineage graph
    graph = LineageGraph(root_repo_id="acme/fine-tuned-bert")
    graph.add_node("acme/fine-tuned-bert", parents=["acme/base-bert"], depth=0)
    graph.add_node("acme/base-bert", parents=["google/bert-base-uncased"], depth=1)
    graph.add_node("google/bert-base-uncased", parents=[], depth=2)

    print(f"\nRoot Model: {graph.root_repo_id}")
    print(f"Total Nodes: {len(graph.nodes)}")
    print(f"\nAncestors (in order): {graph.get_ancestors()}")

    for repo_id, node in graph.nodes.items():
        depth = graph.get_depth(repo_id)
        parents = node.parent_ids
        print(f"  - {repo_id} (depth={depth}, parents={parents})")


def example_2_score_registry():
    """Example 2: Using score registry to cache model scores."""
    print("\n" + "=" * 70)
    print("Example 2: Score Registry (In-Memory)")
    print("=" * 70)

    registry = InMemoryScoreRegistry()

    # Save scores for base models
    base_scores = {
        "model_size": MetricResult(name="model_size", value=0.8, latency_ms=50),
        "performance": MetricResult(name="performance", value=0.9, latency_ms=100),
        "reproducibility": MetricResult(name="reproducibility", value=0.85, latency_ms=200),
    }

    print("\nSaving scores for base models...")
    registry.save_score("google/bert-base-uncased", base_scores)
    registry.save_score(
        "acme/base-bert",
        {
            "model_size": MetricResult(name="model_size", value=0.75, latency_ms=50),
            "performance": MetricResult(name="performance", value=0.88, latency_ms=100),
            "reproducibility": MetricResult(name="reproducibility", value=0.80, latency_ms=200),
        },
    )

    print("\nRetrieving cached scores:")
    for repo_id in ["google/bert-base-uncased", "acme/base-bert"]:
        if registry.has_score(repo_id):
            scores = registry.get_score(repo_id)
            print(f"\n  {repo_id}:")
            for name, result in scores.items():
                print(f"    - {name}: {result.value}")


def example_3_tree_score_with_registry():
    """Example 3: Computing tree score using cached scores."""
    print("\n" + "=" * 70)
    print("Example 3: Tree Score Metric (with Registry)")
    print("=" * 70)

    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Set up registry with ancestor scores
        registry = InMemoryScoreRegistry()

        ancestor_scores = {
            "google/bert-base-uncased": 0.85,
            "acme/base-bert": 0.80,
        }

        for repo_id, score in ancestor_scores.items():
            registry.save_score(
                repo_id,
                {
                    "combined": MetricResult(name="combined", value=score, latency_ms=100)
                },
            )

        # Create tree score metric
        metric = TreeScoreMetric(score_registry=registry)

        # Create model context
        context = create_model_context(
            "acme/fine-tuned-bert",
            tmp_path,
            base_model="acme/base-bert",
        )

        # Manually set up the lineage graph for demo purposes
        from unittest.mock import MagicMock
        mock_graph = LineageGraph(root_repo_id="acme/fine-tuned-bert")
        mock_graph.add_node("acme/fine-tuned-bert", parents=["acme/base-bert"], depth=0)
        mock_graph.add_node("acme/base-bert", parents=["google/bert-base-uncased"], depth=1)
        mock_graph.add_node("google/bert-base-uncased", parents=[], depth=2)

        # Mock the extractor
        metric._extractor.extract = MagicMock(return_value=mock_graph)

        print("\nModel: acme/fine-tuned-bert")
        print(f"Ancestors: {mock_graph.get_ancestors()}")
        print(f"Ancestor Scores:")
        for repo_id, score in ancestor_scores.items():
            print(f"  - {repo_id}: {score}")

        # Compute tree score
        tree_score = metric.compute(context)
        average_score = sum(ancestor_scores.values()) / len(ancestor_scores)

        print(f"\nComputed Tree Score: {tree_score:.3f}")
        print(f"Expected (average): {average_score:.3f}")


def example_4_tree_score_with_function():
    """Example 4: Computing tree score with custom scoring function."""
    print("\n" + "=" * 70)
    print("Example 4: Tree Score Metric (with Custom Score Function)")
    print("=" * 70)

    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Define a custom score function
        def compute_score(repo_id: str) -> float:
            """Mock scoring function that returns different scores per model."""
            scores = {
                "google/bert-base-uncased": 0.95,  # Base model has high score
                "acme/base-bert": 0.87,  # Fine-tuned version has slightly lower score
            }
            return scores.get(repo_id, 0.5)

        # Create tree score metric with scoring function
        metric = TreeScoreMetric(score_fn=compute_score)

        # Create model context
        context = create_model_context(
            "acme/fine-tuned-bert",
            tmp_path,
            base_model="acme/base-bert",
        )

        # Manually set up the lineage graph
        mock_graph = LineageGraph(root_repo_id="acme/fine-tuned-bert")
        mock_graph.add_node("acme/fine-tuned-bert", parents=["acme/base-bert"], depth=0)
        mock_graph.add_node("acme/base-bert", parents=["google/bert-base-uncased"], depth=1)
        mock_graph.add_node("google/bert-base-uncased", parents=[], depth=2)

        # Mock the extractor
        from unittest.mock import MagicMock
        metric._extractor.extract = MagicMock(return_value=mock_graph)

        print("\nModel: acme/fine-tuned-bert")
        print(f"Ancestors: {mock_graph.get_ancestors()}")

        ancestors_scores = [compute_score(aid) for aid in mock_graph.get_ancestors()]
        print(f"\nAncestor Scores (from function):")
        for repo_id in mock_graph.get_ancestors():
            score = compute_score(repo_id)
            print(f"  - {repo_id}: {score}")

        # Compute tree score
        tree_score = metric.compute(context)
        average_score = sum(ancestors_scores) / len(ancestors_scores)

        print(f"\nComputed Tree Score: {tree_score:.3f}")
        print(f"Expected (average): {average_score:.3f}")


def example_5_complex_lineage():
    """Example 5: Complex lineage with multiple paths."""
    print("\n" + "=" * 70)
    print("Example 5: Complex Model Lineage")
    print("=" * 70)

    # Create a more complex lineage graph
    graph = LineageGraph(root_repo_id="acme/final-model")

    # Linear chain: final-model -> model-v2 -> model-v1 -> bert-base
    graph.add_node("acme/final-model", parents=["acme/model-v2"], depth=0)
    graph.add_node("acme/model-v2", parents=["acme/model-v1"], depth=1)
    graph.add_node("acme/model-v1", parents=["google/bert-base-uncased"], depth=2)
    graph.add_node("google/bert-base-uncased", parents=[], depth=3)

    print("\nLineage Tree:")
    print("  acme/final-model")
    print("    └─ acme/model-v2 (depth=1)")
    print("       └─ acme/model-v1 (depth=2)")
    print("          └─ google/bert-base-uncased (depth=3)")

    print(f"\nAll Ancestors: {graph.get_ancestors()}")
    print(f"Total Nodes: {len(graph.nodes)}")

    # Demonstrate depth tracking
    print("\nNode Depths:")
    for repo_id in sorted(graph.nodes.keys()):
        depth = graph.get_depth(repo_id)
        print(f"  {repo_id}: depth={depth}")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("Lineage Graph & Tree Score Examples")
    print("=" * 70)

    example_1_lineage_extraction()
    example_2_score_registry()
    example_3_tree_score_with_registry()
    example_4_tree_score_with_function()
    example_5_complex_lineage()

    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
