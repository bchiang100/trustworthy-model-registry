"""Lightweight HTTP API exposing lineage and tree-score endpoints.

This module uses FastAPI to provide two endpoints:

- GET /lineage/{repo_id} -> returns the lineage graph for a given model repo_id
- GET /tree_score/{repo_id} -> computes and returns the tree score for the model

Notes:
- The endpoints use the existing LineageExtractor and TreeScoreMetric.
- The default score_fn will compute and cache missing ancestor scores using
  the filesystem-backed ScoreRegistry and ModelScorer.

To run locally for development:

    # from project root
    uvicorn acme_cli.api:app --reload --port 8080

"""
from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from acme_cli.lineage_graph import LineageExtractor, LineageGraph
from acme_cli.metrics.tree_score import TreeScoreMetric
from acme_cli.score_registry import FileSystemScoreRegistry
from acme_cli.score_helpers import make_score_fn
from acme_cli.context import ContextBuilder
from acme_cli.types import ModelContext, ScoreTarget, LocalRepository

logger = logging.getLogger(__name__)

app = FastAPI(title="Trustworthy Model Registry API", version="0.1")

# Shared components (created once per process)
_hf_lineage_extractor = LineageExtractor()
_cache_dir = os.getenv("ACME_SCORE_CACHE_DIR")
_score_registry = FileSystemScoreRegistry(cache_dir=_cache_dir) if _cache_dir else FileSystemScoreRegistry()
_default_score_fn = make_score_fn(registry=_score_registry)
_tree_metric = TreeScoreMetric(lineage_extractor=_hf_lineage_extractor, score_registry=_score_registry, score_fn=_default_score_fn)
_context_builder = ContextBuilder()


# --- Response models -------------------------------------------------
class LineageNodeOut(BaseModel):
    repo_id: str
    parents: List[str]
    depth: int
    metadata: Dict[str, Any]


class LineageResponse(BaseModel):
    root: str
    nodes: Dict[str, LineageNodeOut]
    ancestors: List[str]


class TreeScoreResponse(BaseModel):
    repo_id: str
    tree_score: float
    ancestors: List[str]
    ancestor_scores: Dict[str, float]


# --- Helpers ---------------------------------------------------------
def _build_context_for_repo(repo_id: str) -> ModelContext:
    # Minimal ModelContext using local repo field to allow metrics to run
    # If more context is needed, the ContextBuilder can be used instead.
    return ModelContext(
        target=ScoreTarget(model_url=f"https://huggingface.co/{repo_id}"),
        model_metadata=None,
        dataset_metadata=None,
        local_repo=LocalRepository(repo_id=repo_id, repo_type="model", path=None),
        dataset_local_repo=None,
        readme_text=None,
        dataset_readme_text=None,
        commit_authors=[],
        commit_total=0,
    )


# --- Endpoints ------------------------------------------------------
@app.get("/lineage/{repo_id}", response_model=LineageResponse)
def get_lineage(repo_id: str, max_depth: int = Query(5, ge=0, le=20)) -> LineageResponse:
    """Return the lineage graph for the given model repo_id.

    repo_id should be in the form 'org/model'.
    """
    try:
        graph: LineageGraph = _hf_lineage_extractor.extract(repo_id, max_depth=max_depth)

        nodes_out: Dict[str, LineageNodeOut] = {}
        for rid, node in graph.nodes.items():
            nodes_out[rid] = LineageNodeOut(
                repo_id=rid,
                parents=node.parent_ids,
                depth=graph.get_depth(rid),
                metadata=node.metadata or {},
            )

        ancestors = graph.get_ancestors()
        return LineageResponse(root=graph.root_repo_id, nodes=nodes_out, ancestors=ancestors)

    except Exception as exc:  # noqa: BLE001 - return 404 for errors retrieving metadata
        logger.exception("Failed to build lineage for %s: %s", repo_id, exc)
        raise HTTPException(status_code=404, detail=f"Could not build lineage for {repo_id}: {exc}")


@app.get("/tree_score/{repo_id}", response_model=TreeScoreResponse)
def get_tree_score(repo_id: str, max_depth: int = Query(5, ge=0, le=20), recompute: bool = Query(False)) -> TreeScoreResponse:
    """Compute and return the tree score for the specified model.

    Parameters:
    - recompute: If true, forces recomputation of ancestor scores even if cached.
    """
    try:
        # Extract lineage
        graph = _hf_lineage_extractor.extract(repo_id, max_depth=max_depth)
        ancestors = graph.get_ancestors()

        # If recompute requested, clear registry entries for ancestors
        if recompute:
            for aid in ancestors:
                try:
                    # FileSystemScoreRegistry exposes clear/remove via filesystem; try to delete
                    path = _score_registry._get_cache_path(aid)  # use protected API for convenience
                    if path.exists():
                        path.unlink()
                except Exception:
                    # ignore; best-effort
                    logger.debug("Could not clear cache for %s", aid)

        # Compute the tree score using the metric instance
        # Build a minimal context with local_repo set so metric can run
        context = _build_context_for_repo(repo_id)
        # The metric internally uses the lineage_extractor we created above
        tree_score_value = _tree_metric.compute(context)

        # Collect ancestor-level scores from registry (or compute via score_fn)
        ancestor_scores = {}
        for aid in ancestors:
            try:
                if _score_registry.has_score(aid):
                    scores = _score_registry.get_score(aid)
                    # average numeric values (same logic as scores helper)
                    avg = _tree_metric._average_scores(scores.values()) if scores else 0.5
                    ancestor_scores[aid] = avg
                else:
                    # compute on-demand via default score_fn
                    val = _default_score_fn(aid)
                    ancestor_scores[aid] = val
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to get/compute score for ancestor %s: %s", aid, e)
                ancestor_scores[aid] = 0.5

        return TreeScoreResponse(repo_id=repo_id, tree_score=tree_score_value, ancestors=ancestors, ancestor_scores=ancestor_scores)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Error computing tree score for %s: %s", repo_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


# Simple health endpoint
@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}
