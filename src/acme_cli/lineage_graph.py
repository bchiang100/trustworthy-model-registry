"""Model lineage graph extraction and analysis."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from acme_cli.hf.client import HfClient
from huggingface_hub import HfApi

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LineageNode:
    """Represents a single model in the lineage graph."""

    repo_id: str
    """The repository ID in format 'organization/model'."""
    
    parent_ids: list[str] = field(default_factory=list)
    """List of parent model repository IDs."""
    
    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata about the model (e.g., pipeline_tag, library_name)."""


@dataclass(slots=True)
class LineageGraph:
    """Represents the complete lineage graph for a model and its ancestors."""

    root_repo_id: str
    """The root/target model repo ID."""
    
    nodes: dict[str, LineageNode] = field(default_factory=dict)
    """All nodes in the graph indexed by repo_id."""
    
    discovered_at: dict[str, int] = field(default_factory=dict)
    """Track discovery depth for each node (0 = root, 1 = immediate parent, etc)."""

    def get_ancestors(self) -> list[str]:
        """Get all ancestor model IDs in topological order (parents before children)."""
        ancestors = []
        visited = {self.root_repo_id}
        
        def visit(repo_id: str, depth: int = 0) -> None:
            if repo_id not in self.nodes:
                return
            
            node = self.nodes[repo_id]
            for parent_id in node.parent_ids:
                if parent_id not in visited:
                    visited.add(parent_id)
                    ancestors.append(parent_id)
                    visit(parent_id, depth + 1)
        
        visit(self.root_repo_id)
        return ancestors

    def get_parents(self, repo_id: str) -> list[str]:
        """Get direct parent IDs for a given model."""
        if repo_id not in self.nodes:
            return []
        return self.nodes[repo_id].parent_ids

    def get_depth(self, repo_id: str) -> int:
        """Get the depth of a node in the tree (0 for root, 1 for immediate parents, etc)."""
        return self.discovered_at.get(repo_id, -1)

    def add_node(self, repo_id: str, parents: list[str] | None = None, depth: int = 0, metadata: dict[str, Any] | None = None) -> None:
        """Add a node to the graph."""
        if repo_id not in self.nodes:
            self.nodes[repo_id] = LineageNode(
                repo_id=repo_id,
                parent_ids=parents or [],
                metadata=metadata or {},
            )
            self.discovered_at[repo_id] = depth

    def has_node(self, repo_id: str) -> bool:
        """Check if a node exists in the graph."""
        return repo_id in self.nodes

    def __repr__(self) -> str:
        return f"LineageGraph(root={self.root_repo_id}, nodes={len(self.nodes)})"


class LineageExtractor:
    """Extracts model lineage from Hugging Face model metadata."""

    def __init__(self, hf_client: HfClient | None = None, hf_api: HfApi | None = None) -> None:
        """Initialize the extractor.
        
        Args:
            hf_client: HfClient for metadata retrieval
            hf_api: HfApi for direct API calls (backup for file access)
        """
        self._hf_client = hf_client or HfClient()
        self._hf_api = hf_api or HfApi()

    def extract(self, repo_id: str, max_depth: int = 10) -> LineageGraph:
        """Extract the complete lineage graph for a model.
        
        Args:
            repo_id: The model repository ID to extract lineage for
            max_depth: Maximum depth to traverse (prevents infinite loops)
            
        Returns:
            LineageGraph containing the model and all discovered ancestors
        """
        graph = LineageGraph(root_repo_id=repo_id)
        self._extract_recursive(repo_id, graph, depth=0, max_depth=max_depth)
        return graph

    def _extract_recursive(self, repo_id: str, graph: LineageGraph, depth: int = 0, max_depth: int = 10) -> None:
        """Recursively extract lineage information.
        
        Args:
            repo_id: The repository ID to process
            graph: The graph to populate
            depth: Current recursion depth
            max_depth: Maximum recursion depth
        """
        if depth > max_depth or graph.has_node(repo_id):
            return

        try:
            # Get model metadata
            model_metadata = self._hf_client.get_model(repo_id)
            if not model_metadata:
                logger.warning(f"Could not fetch metadata for {repo_id}")
                graph.add_node(repo_id, parents=[], depth=depth)
                return

            # Extract parent IDs from config.json
            parent_ids = self._extract_parents_from_config(repo_id)

            # Add node to graph
            metadata = {
                "pipeline_tag": model_metadata.pipeline_tag,
                "library_name": model_metadata.library_name,
                "downloads": model_metadata.downloads,
                "likes": model_metadata.likes,
            }
            graph.add_node(repo_id, parents=parent_ids, depth=depth, metadata=metadata)

            # Recursively process parents
            for parent_id in parent_ids:
                self._extract_recursive(parent_id, graph, depth=depth + 1, max_depth=max_depth)

        except Exception as e:
            logger.warning(f"Error extracting lineage for {repo_id}: {e}")
            graph.add_node(repo_id, parents=[], depth=depth)

    def _extract_parents_from_config(self, repo_id: str) -> list[str]:
        """Extract parent model IDs from a model's config.json.
        
        Looks for common parent reference patterns in config.json:
        - model_id
        - base_model_id
        - parent_model
        - pretrained_model_name_or_path
        - _name_or_path
        
        Args:
            repo_id: The model repository ID
            
        Returns:
            List of parent repository IDs found
        """
        parent_ids = []
        
        try:
            # Try to get config.json content
            config_content = self._hf_api.hf_hub_download(
                repo_id=repo_id,
                filename="config.json",
                repo_type="model",
            )
            
            with open(config_content, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            parent_ids.extend(self._extract_from_config(config))
            
        except Exception as e:
            logger.debug(f"Could not read config.json for {repo_id}: {e}")

        return parent_ids

    @staticmethod
    def _extract_from_config(config: dict[str, Any]) -> list[str]:
        """Extract parent model IDs from parsed config dictionary.
        
        Args:
            config: Parsed config.json as dictionary
            
        Returns:
            List of parent repository IDs
        """
        parent_ids = []
        
        # Common keys that might reference parent models
        parent_keys = [
            "model_id",
            "base_model_id",
            "base_model",
            "parent_model",
            "pretrained_model_name_or_path",
            "_name_or_path",
            "name_or_path",
        ]
        
        for key in parent_keys:
            if key in config:
                value = config[key]
                if isinstance(value, str) and value and "/" in value:
                    # Likely a repo_id in format 'org/model'
                    parent_ids.append(value)
        
        # Also check for model_type references that might indicate a fine-tune
        # (though this is less reliable)
        if "architectures" in config and isinstance(config["architectures"], list):
            # Architecture might be inherited from base model, but we can't know for sure
            pass
        
        return parent_ids


__all__ = [
    "LineageNode",
    "LineageGraph",
    "LineageExtractor",
]
