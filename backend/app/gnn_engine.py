"""Optional graph-based mule-account scoring with a deterministic fallback."""
from __future__ import annotations

import os
from typing import Any

try:
    import torch
    from torch_geometric.data import Data
    from torch_geometric.nn import SAGEConv
except ImportError:  # pragma: no cover - optional accelerator dependency
    torch = None
    Data = None
    SAGEConv = None


class MuleAccountScorer:
    def __init__(self, feature_dim: int = 32, hops: int = 3) -> None:
        self.feature_dim = feature_dim
        self.hops = hops
        self._model = None
        model_path = os.getenv("GUARDAIN_GNN_MODEL_PATH", "").strip()
        if torch is not None and SAGEConv is not None and model_path and os.path.isfile(model_path):
            layers = [SAGEConv(feature_dim, feature_dim) for _ in range(max(1, hops))]
            self._model = torch.nn.ModuleList(layers)
            self._model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
            self._model.eval()

    def score(self, features: dict[str, Any] | None = None) -> dict[str, Any]:
        values = features or {}
        transaction_count = max(0, int(values.get("transaction_count", 0) or 0))
        unique_counterparties = max(0, int(values.get("unique_counterparties", 0) or 0))
        velocity = max(0.0, float(values.get("velocity", 0.0) or 0.0))
        heuristic = min(1.0, 0.15 + min(transaction_count / 100, 0.35)
                        + min(unique_counterparties / 50, 0.25) + min(velocity / 20, 0.25))
        engine = "heuristic-graph-fallback"
        if self._model is not None and Data is not None:
            x = torch.zeros((1, self.feature_dim), dtype=torch.float32)
            x[0, :3] = torch.tensor([transaction_count / 100, unique_counterparties / 50, velocity / 20])
            graph = Data(x=x, edge_index=torch.empty((2, 0), dtype=torch.long))
            with torch.inference_mode():
                for layer in self._model:
                    graph.x = layer(graph.x, graph.edge_index).relu()
            heuristic = float(torch.sigmoid(graph.x.mean()).item())
            engine = "pyg-sage"
        return {"mule_score": round(heuristic, 4), "risk_level": "high" if heuristic >= 0.7 else "review" if heuristic >= 0.45 else "low", "engine": engine}
