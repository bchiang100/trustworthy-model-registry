"""Tree score metric based on model lineage and ancestor model scores."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from acme_cli.context import ContextBuilder
from acme_cli.lineage_graph import LineageExtractor, LineageGraph
from acme_cli.metrics.base import Metric
from acme_cli.score_registry import InMemoryScoreRegistry, ScoreRegistry
from acme_cli.types import ModelContext
from acme_cli.utils import clamp

logger = logging.getLogger(__name__)


class TreeScoreMetric(Metric):
    """
    Metric that computes a score based on model lineage and parent model scores.
    
    The tree score is calculated as the average of all ancestor model scores.
    For models without cached scores, the scores are computed on-demand using
    a provided scoring function.
    
    Tree Score = Average of all parent model scores (or 1.0 if no parents)
    """

    name = "tree_score"

    def __init__(
        self,
        lineage_extractor: LineageExtractor | None = None,
        score_registry: ScoreRegistry | None = None,
        context_builder: ContextBuilder | None = None,
        score_fn: Optional[Callable[[str], float]] = None,
        max_lineage_depth: int = 10,
    ) -> None:
        """Initialize the tree score metric.
        
        Args:
            lineage_extractor: Extractor for building model lineage graphs
            score_registry: Registry for caching and retrieving scores
            context_builder: Builder for creating model contexts
            score_fn: Optional function to compute scores for ancestor models.
                     If provided, will be called with repo_id to compute scores for
                     models not in the registry.
            max_lineage_depth: Maximum depth to traverse in lineage graph
        """
        self._extractor = lineage_extractor or LineageExtractor()
        self._registry = score_registry or InMemoryScoreRegistry()
        self._context_builder = context_builder or ContextBuilder()
        self._score_fn = score_fn
        self._max_lineage_depth = max_lineage_depth

    def compute(self, context: ModelContext) -> float:
        """
        Compute the tree score for a model.
        
        Args:
            context: The model context containing model metadata
            
        Returns:
            float: Tree score between 0 and 1
        """
        if not context.local_repo:
            logger.warning("No local repository available for tree score computation")
            return 1.0  # Default to neutral score if no lineage data

        repo_id = context.local_repo.repo_id

        try:
            # Extract lineage graph
            graph = self._extractor.extract(repo_id, max_depth=self._max_lineage_depth)

            # Get all ancestor model IDs
            ancestor_ids = graph.get_ancestors()

            if not ancestor_ids:
                # No parents, return neutral score
                logger.debug(f"Model {repo_id} has no ancestors")
                return 1.0

            # Get scores for all ancestors
            ancestor_scores = self._get_ancestor_scores(ancestor_ids)

            if not ancestor_scores:
                # Could not compute any ancestor scores
                logger.warning(f"Could not compute scores for any ancestors of {repo_id}")
                return 0.5  # Conservative score

            # Return average of ancestor scores
            tree_score = sum(ancestor_scores) / len(ancestor_scores)
            return clamp(tree_score)

        except Exception as e:
            logger.error(f"Error computing tree score for {repo_id}: {e}")
            return 0.5  # Conservative score on error

    def _get_ancestor_scores(self, ancestor_ids: list[str]) -> list[float]:
        """Get scores for all ancestor models.
        
        For each ancestor, first checks the registry for cached scores.
        If not found and score_fn is available, computes the score on-demand.
        
        Args:
            ancestor_ids: List of ancestor model repository IDs
            
        Returns:
            List of averaged scores for ancestors
        """
        ancestor_scores = []

        for repo_id in ancestor_ids:
            try:
                score = self._get_single_ancestor_score(repo_id)
                if score is not None:
                    ancestor_scores.append(score)
            except Exception as e:
                logger.warning(f"Failed to get score for ancestor {repo_id}: {e}")

        return ancestor_scores

    def _get_single_ancestor_score(self, repo_id: str) -> Optional[float]:
        """Get the average score for a single ancestor model.
        
        Checks registry first, then uses score_fn if available.
        
        Args:
            repo_id: The ancestor model repository ID
            
        Returns:
            Average of all metric scores, or None if unable to compute
        """
        # Check registry first
        if self._registry.has_score(repo_id):
            scores = self._registry.get_score(repo_id)
            if scores:
                return self._average_scores(scores.values())

        # Try to compute score on-demand
        if self._score_fn:
            try:
                score = self._score_fn(repo_id)
                return score
            except Exception as e:
                logger.warning(f"Score function failed for {repo_id}: {e}")

        return None

    @staticmethod
    def _average_scores(scores) -> float:
        """Calculate average of multiple metric scores.
        
        Args:
            scores: Iterable of MetricResult objects
            
        Returns:
            Average score between 0 and 1
        """
        numeric_scores = []

        for score_result in scores:
            try:
                value = score_result.value
                if isinstance(value, dict):
                    # For composite scores, take the average of values
                    numeric_scores.extend(v for v in value.values() if isinstance(v, (int, float)))
                elif isinstance(value, (int, float)):
                    numeric_scores.append(value)
            except Exception:
                pass

        if numeric_scores:
            return sum(numeric_scores) / len(numeric_scores)
        return 0.5


__all__ = ["TreeScoreMetric"]
