"""Tests for lineage graph and tree score metric."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from acme_cli.lineage_graph import LineageExtractor, LineageGraph, LineageNode
from acme_cli.metrics.tree_score import TreeScoreMetric
from acme_cli.score_registry import FileSystemScoreRegistry, InMemoryScoreRegistry
from acme_cli.types import (
    LocalRepository,
    MetricResult,
    ModelContext,
    ModelMetadata,
    RepoFile,
    ScoreTarget,
)


class TestLineageNode:
    """Tests for LineageNode."""

    def test_creation(self):
        """Test LineageNode creation."""
        node = LineageNode(repo_id="org/model", parent_ids=["org/parent1", "org/parent2"])
        assert node.repo_id == "org/model"
        assert len(node.parent_ids) == 2

    def test_metadata(self):
        """Test LineageNode with metadata."""
        metadata = {"pipeline_tag": "text-classification", "likes": 100}
        node = LineageNode(repo_id="org/model", metadata=metadata)
        assert node.metadata["pipeline_tag"] == "text-classification"


class TestLineageGraph:
    """Tests for LineageGraph."""

    def test_empty_graph(self):
        """Test creating an empty lineage graph."""
        graph = LineageGraph(root_repo_id="org/model")
        assert graph.root_repo_id == "org/model"
        assert len(graph.nodes) == 0

    def test_add_node(self):
        """Test adding nodes to graph."""
        graph = LineageGraph(root_repo_id="org/model")
        graph.add_node("org/model", parents=["org/parent"])
        graph.add_node("org/parent", parents=[])

        assert graph.has_node("org/model")
        assert graph.has_node("org/parent")
        assert len(graph.nodes) == 2

    def test_get_ancestors_simple(self):
        """Test getting ancestors in simple case."""
        graph = LineageGraph(root_repo_id="org/model")
        graph.add_node("org/model", parents=["org/parent"], depth=0)
        graph.add_node("org/parent", parents=[], depth=1)

        ancestors = graph.get_ancestors()
        assert ancestors == ["org/parent"]

    def test_get_ancestors_chain(self):
        """Test getting ancestors in a chain."""
        graph = LineageGraph(root_repo_id="org/model3")
        graph.add_node("org/model3", parents=["org/model2"], depth=0)
        graph.add_node("org/model2", parents=["org/model1"], depth=1)
        graph.add_node("org/model1", parents=[], depth=2)

        ancestors = graph.get_ancestors()
        assert len(ancestors) == 2
        assert "org/model2" in ancestors
        assert "org/model1" in ancestors
        # Check order: parents come before their children
        assert ancestors.index("org/model2") < ancestors.index("org/model1")

    def test_get_parents(self):
        """Test getting direct parents."""
        graph = LineageGraph(root_repo_id="org/model")
        graph.add_node("org/model", parents=["org/parent1", "org/parent2"])

        parents = graph.get_parents("org/model")
        assert len(parents) == 2
        assert "org/parent1" in parents
        assert "org/parent2" in parents

    def test_get_depth(self):
        """Test getting node depth."""
        graph = LineageGraph(root_repo_id="org/model")
        graph.add_node("org/model", depth=0)
        graph.add_node("org/parent", depth=1)
        graph.add_node("org/grandparent", depth=2)

        assert graph.get_depth("org/model") == 0
        assert graph.get_depth("org/parent") == 1
        assert graph.get_depth("org/grandparent") == 2


class TestLineageExtractor:
    """Tests for LineageExtractor."""

    def test_extract_no_parents(self):
        """Test extraction for model with no parents."""
        extractor = LineageExtractor()

        with patch.object(extractor._hf_client, "get_model") as mock_get:
            mock_get.return_value = ModelMetadata(
                repo_id="org/model",
                display_name="model",
                card_data={},
                downloads=100,
                likes=10,
                last_modified=datetime.now(),
                tags=[],
                files=[],
                pipeline_tag=None,
                library_name=None,
            )

            with patch.object(extractor, "_extract_parents_from_config") as mock_parents:
                mock_parents.return_value = []

                graph = extractor.extract("org/model")

                assert graph.root_repo_id == "org/model"
                assert graph.has_node("org/model")
                assert len(graph.get_ancestors()) == 0

    def test_extract_with_parents(self):
        """Test extraction for model with parents."""
        extractor = LineageExtractor()

        def mock_get_model(repo_id):
            return ModelMetadata(
                repo_id=repo_id,
                display_name=repo_id.split("/")[-1],
                card_data={},
                downloads=100,
                likes=10,
                last_modified=datetime.now(),
                tags=[],
                files=[],
                pipeline_tag=None,
                library_name=None,
            )

        with patch.object(extractor._hf_client, "get_model", side_effect=mock_get_model):
            with patch.object(extractor, "_extract_parents_from_config") as mock_parents:

                def parents_side_effect(repo_id):
                    if repo_id == "org/model":
                        return ["org/parent1", "org/parent2"]
                    return []

                mock_parents.side_effect = parents_side_effect

                graph = extractor.extract("org/model", max_depth=2)

                assert graph.has_node("org/model")
                assert graph.has_node("org/parent1")
                assert graph.has_node("org/parent2")
                ancestors = graph.get_ancestors()
                assert len(ancestors) == 2

    def test_extract_from_config_parent_keys(self):
        """Test extraction of parent IDs from config."""
        config1 = {"model_id": "org/base_model"}
        parents1 = LineageExtractor._extract_from_config(config1)
        assert "org/base_model" in parents1

        config2 = {"base_model_id": "org/base"}
        parents2 = LineageExtractor._extract_from_config(config2)
        assert "org/base" in parents2

        config3 = {"_name_or_path": "org/pretrained"}
        parents3 = LineageExtractor._extract_from_config(config3)
        assert "org/pretrained" in parents3

    def test_extract_from_config_no_parents(self):
        """Test extraction from config with no parent references."""
        config = {"model_type": "bert", "num_layers": 12}
        parents = LineageExtractor._extract_from_config(config)
        assert len(parents) == 0


class TestInMemoryScoreRegistry:
    """Tests for InMemoryScoreRegistry."""

    def test_save_and_get(self):
        """Test saving and retrieving scores."""
        registry = InMemoryScoreRegistry()
        repo_id = "org/model"

        scores = {
            "metric1": MetricResult(name="metric1", value=0.8, latency_ms=100),
            "metric2": MetricResult(name="metric2", value=0.9, latency_ms=200),
        }

        registry.save_score(repo_id, scores)
        retrieved = registry.get_score(repo_id)

        assert retrieved is not None
        assert len(retrieved) == 2
        assert retrieved["metric1"].value == 0.8

    def test_has_score(self):
        """Test checking if score exists."""
        registry = InMemoryScoreRegistry()
        repo_id = "org/model"

        assert not registry.has_score(repo_id)

        scores = {"metric1": MetricResult(name="metric1", value=0.8, latency_ms=100)}
        registry.save_score(repo_id, scores)

        assert registry.has_score(repo_id)

    def test_clear(self):
        """Test clearing registry."""
        registry = InMemoryScoreRegistry()
        scores = {"metric1": MetricResult(name="metric1", value=0.8, latency_ms=100)}
        registry.save_score("org/model", scores)

        assert registry.has_score("org/model")
        registry.clear()
        assert not registry.has_score("org/model")


class TestFileSystemScoreRegistry:
    """Tests for FileSystemScoreRegistry."""

    def test_save_and_get(self, tmp_path):
        """Test saving and retrieving scores from filesystem."""
        registry = FileSystemScoreRegistry(cache_dir=tmp_path)
        repo_id = "org/model"

        scores = {
            "metric1": MetricResult(name="metric1", value=0.8, latency_ms=100),
            "metric2": MetricResult(name="metric2", value=0.9, latency_ms=200),
        }

        registry.save_score(repo_id, scores)
        retrieved = registry.get_score(repo_id)

        assert retrieved is not None
        assert len(retrieved) == 2

    def test_has_score(self, tmp_path):
        """Test checking if score exists on filesystem."""
        registry = FileSystemScoreRegistry(cache_dir=tmp_path)
        repo_id = "org/model"

        assert not registry.has_score(repo_id)

        scores = {"metric1": MetricResult(name="metric1", value=0.8, latency_ms=100)}
        registry.save_score(repo_id, scores)

        assert registry.has_score(repo_id)


class TestTreeScoreMetric:
    """Tests for TreeScoreMetric."""

    def _create_context(self, repo_id: str, tmp_path: Path) -> ModelContext:
        """Helper to create a model context."""
        repo_path = tmp_path / repo_id.replace("/", "_")
        repo_path.mkdir(parents=True, exist_ok=True)

        return ModelContext(
            target=ScoreTarget(model_url=f"https://huggingface.co/{repo_id}"),
            model_metadata=ModelMetadata(
                repo_id=repo_id,
                display_name=repo_id.split("/")[-1],
                card_data={},
                downloads=100,
                likes=10,
                last_modified=datetime.now(),
                tags=[],
                files=[],
                pipeline_tag=None,
                library_name=None,
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
            commit_authors=[],
            commit_total=0,
        )

    def test_no_ancestors(self, tmp_path):
        """Test tree score for model with no ancestors."""
        metric = TreeScoreMetric()

        context = self._create_context("org/model", tmp_path)

        with patch.object(metric._extractor, "extract") as mock_extract:
            graph = LineageGraph(root_repo_id="org/model")
            graph.add_node("org/model", parents=[])
            mock_extract.return_value = graph

            score = metric.compute(context)

            assert score == 1.0  # Neutral score for models with no parents

    def test_with_ancestor_scores(self, tmp_path):
        """Test tree score with ancestor scores from registry."""
        registry = InMemoryScoreRegistry()
        registry.save_score(
            "org/parent1",
            {"metric1": MetricResult(name="metric1", value=0.8, latency_ms=100)},
        )
        registry.save_score(
            "org/parent2",
            {"metric1": MetricResult(name="metric1", value=0.6, latency_ms=100)},
        )

        metric = TreeScoreMetric(score_registry=registry)
        context = self._create_context("org/model", tmp_path)

        with patch.object(metric._extractor, "extract") as mock_extract:
            graph = LineageGraph(root_repo_id="org/model")
            graph.add_node("org/model", parents=["org/parent1", "org/parent2"], depth=0)
            graph.add_node("org/parent1", parents=[], depth=1)
            graph.add_node("org/parent2", parents=[], depth=1)
            mock_extract.return_value = graph

            score = metric.compute(context)

            # Average of 0.8 and 0.6 = 0.7
            assert abs(score - 0.7) < 0.01

    def test_with_score_function(self, tmp_path):
        """Test tree score with custom score function."""

        def score_fn(repo_id: str) -> float:
            scores = {"org/parent1": 0.9, "org/parent2": 0.7}
            return scores.get(repo_id, 0.5)

        metric = TreeScoreMetric(score_fn=score_fn)
        context = self._create_context("org/model", tmp_path)

        with patch.object(metric._extractor, "extract") as mock_extract:
            graph = LineageGraph(root_repo_id="org/model")
            graph.add_node("org/model", parents=["org/parent1", "org/parent2"], depth=0)
            graph.add_node("org/parent1", parents=[], depth=1)
            graph.add_node("org/parent2", parents=[], depth=1)
            mock_extract.return_value = graph

            score = metric.compute(context)

            # Average of 0.9 and 0.7 = 0.8
            assert abs(score - 0.8) < 0.01

    def test_no_ancestors_with_score_function(self, tmp_path):
        """Test that score function is not called for models with no ancestors."""
        score_fn = MagicMock(return_value=0.8)

        metric = TreeScoreMetric(score_fn=score_fn)
        context = self._create_context("org/model", tmp_path)

        with patch.object(metric._extractor, "extract") as mock_extract:
            graph = LineageGraph(root_repo_id="org/model")
            graph.add_node("org/model", parents=[])
            mock_extract.return_value = graph

            score = metric.compute(context)

            assert score == 1.0
            score_fn.assert_not_called()
