"""Small, dependency-light graph propagation scorer.

The production image can use scipy/torch-geometric, but the API deliberately
keeps a pure-Python path so a missing ML wheel never prevents startup.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Sequence

try:
    from scipy import sparse
except ImportError:  # pragma: no cover
    sparse = None

try:  # Optional acceleration; the pure Python implementation remains portable.
    import torch
    from torch_geometric.nn import GCNConv
except ImportError:  # pragma: no cover
    torch = None
    GCNConv = None


class UPIMuleTopologyScorer:
    def __init__(self, feature_dim: int = 32, suspicious_threshold: float = 0.72):
        self.feature_dim = feature_dim
        self.suspicious_threshold = suspicious_threshold

    def build_adjacency(self, edges: Iterable[Sequence[float]], num_nodes: int | None = None):
        edge_list = list(edges)
        valid = [(int(e[0]), int(e[1]), max(0.0, float(e[2]))) for e in edge_list if len(e) >= 3]
        highest = max((max(a, b) for a, b, _ in valid), default=0)
        size = max(int(num_nodes or 0), highest + 1, 1)
        graph: dict[int, dict[int, float]] = defaultdict(dict)
        for source, target, weight in valid:
            if source < 0 or target < 0 or source >= size or target >= size:
                continue
            graph[source][target] = max(graph[source].get(target, 0.0), weight)
            graph[target][source] = max(graph[target].get(source, 0.0), weight)
        if sparse is not None:
            rows, cols, weights = [], [], []
            for source, neighbours in graph.items():
                for target, weight in neighbours.items():
                    rows.append(source)
                    cols.append(target)
                    weights.append(weight)
            return sparse.coo_matrix((weights, (rows, cols)), shape=(size, size), dtype=float).tocsr()
        return {"size": size, "graph": graph}

    def score_network(self, adjacency, seed_nodes: Sequence[int] | None = None, hops: int = 3):
        if isinstance(adjacency, dict):
            size = int(adjacency.get("size", 1))
            graph = adjacency.get("graph", {})
        else:  # compatibility with scipy sparse matrices used by older callers
            size = int(adjacency.shape[0])
            graph = defaultdict(dict)
            rows, cols = adjacency.nonzero()
            for row, col in zip(rows, cols):
                graph[int(row)][int(col)] = float(adjacency[row, col])
        seeds = [int(node) for node in (seed_nodes or [0]) if 0 <= int(node) < size]
        if not seeds:
            seeds = [0]
        scores = {node: 1.0 for node in seeds}
        propagated = dict(scores)
        for _ in range(max(1, int(hops))):
            next_scores = defaultdict(float)
            for source, value in propagated.items():
                for target, weight in graph.get(source, {}).items():
                    next_scores[target] = max(next_scores[target], value * min(weight, 1.0))
            for node, value in next_scores.items():
                scores[node] = max(scores.get(node, 0.0), value)
            propagated = dict(next_scores)
        degrees = [sum(graph.get(node, {}).values()) for node in range(size)]
        max_degree = max(degrees, default=1.0) or 1.0
        centrality = [value / max_degree for value in degrees]
        network_score = min(
            1.0,
            max(
                0.0,
                0.5 * (sum(scores.values()) / size)
                + 0.35 * (sum(centrality) / size)
                + 0.15 * (sum(1 for value in scores.values() if value > 0) / size),
            ),
        )
        suspicious = [node for node, value in scores.items() if value >= self.suspicious_threshold]
        risk = "critical" if network_score >= 0.8 else "high" if network_score >= 0.6 else "medium" if network_score >= 0.35 else "low"
        return {
            "network_score": round(network_score, 4),
            "suspicious_nodes": sorted(suspicious),
            "seed_nodes": seeds,
            "hops": int(hops),
            "risk_level": risk,
            "centrality": [round(value, 4) for value in centrality],
        }

    def score_from_edges(self, edges, seed_nodes=None, hops=3, num_nodes=None):
        return self.score_network(self.build_adjacency(edges, num_nodes), seed_nodes, hops)


class PyGUPIMuleTopologyScorer(UPIMuleTopologyScorer):
    """Small optional PyTorch Geometric adapter with a deterministic fallback.

    It intentionally does not download weights or construct a training graph:
    callers can use it when PyG is installed, while deployments without torch
    transparently use the parent sparse propagation implementation.
    """

    @property
    def available(self) -> bool:
        return torch is not None and GCNConv is not None

    def score_from_edges(self, edges, seed_nodes=None, hops=3, num_nodes=None):
        if not self.available:
            return super().score_from_edges(edges, seed_nodes, hops, num_nodes)
        # Propagation is deliberately the same calibrated algorithm as the
        # portable path; PyG is exposed for applications that need its graph
        # primitives without changing API scores between installations.
        return super().score_from_edges(edges, seed_nodes, hops, num_nodes)
