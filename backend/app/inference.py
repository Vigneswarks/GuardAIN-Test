"""ONNX inference with a deterministic, privacy-safe fallback classifier."""
from __future__ import annotations

import asyncio
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Sequence

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

try:
    import onnxruntime as ort
except ImportError:  # pragma: no cover
    ort = None

try:
    from transformers import AutoTokenizer
except ImportError:  # pragma: no cover
    AutoTokenizer = None


class MuRILInferenceService:
    def __init__(self, model_path=None, tokenizer_path=None, providers=None):
        root = Path(__file__).resolve().parents[2]
        self.model_path = str(Path(model_path or os.getenv(
            "ONNX_MODEL_PATH", str(root / "backend" / "models" / "guardain_muril.onnx")
        )))
        self.tokenizer_path = str(Path(tokenizer_path or os.getenv(
            "ONNX_TOKENIZER_PATH", str(root / "backend" / "models" / "guardain_tokenizer")
        )))
        self.providers = providers or ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self._session = None
        self._tokenizer = None
        self._fallback_mode = True
        self._executor = ThreadPoolExecutor(
            max_workers=max(2, min(8, int(os.getenv("GUARDAIN_INFERENCE_WORKERS", "4")))),
            thread_name_prefix="guardain-inference",
        )
        self._load_model()

    def _load_model(self):
        if ort is None or np is None or not os.path.isfile(self.model_path):
            return
        try:
            available = set(ort.get_available_providers())
            selected = [provider for provider in self.providers if provider in available]
            self._session = ort.InferenceSession(self.model_path, providers=selected or None)
            self._fallback_mode = False
            if AutoTokenizer is not None and os.path.isdir(self.tokenizer_path):
                self._tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_path, local_files_only=True)
        except Exception:
            self._session = None
            self._tokenizer = None
            self._fallback_mode = True

    @staticmethod
    def _fallback_score(payload: str) -> dict[str, Any]:
        lower = payload.lower()
        indicators = {
            "digital_arrest": ("digital arrest", "cbi", "bail", "court order", "police notice", "cybercrime"),
            "utility_disconnection": ("electricity", "bill paid", "disconnect", "power cut", "utility", "meter"),
            "upi_collect": ("upi qr", "qr collect", "collect request", "paytm qr", "phonepe", "scan this qr"),
            "phishing": ("verify account", "update kyc", "click link", "login urgently", "secure your account", "otp"),
        }
        score = 0.04
        weights = {"digital_arrest": 0.46, "utility_disconnection": 0.32,
                   "upi_collect": 0.34, "phishing": 0.34}
        categories = []
        for category, terms in indicators.items():
            if any(term in lower for term in terms):
                categories.append(category)
                score += weights.get(category, 0.18)
        if re.search(r"\b(otp|password|aadhaar|pan|bank login|upi id)\b", lower):
            score += 0.12
        if re.search(r"\b(urgent|immediately|today|last chance|within \d+ hours|block your account)\b", lower):
            score += 0.18
        if re.search(r"https?://|(?:\.[a-z]{2,})\b", lower):
            score += 0.08
        score = round(min(0.98, max(0.0, score)), 4)
        risk = "critical" if score >= 0.72 else "high" if score >= 0.5 else "medium" if score >= 0.28 else "low"
        return {
            "score": score,
            "label": "fraud" if score >= 0.5 else "benign",
            "risk_level": risk,
            "matched_categories": categories,
            "coercion_category": categories[0] if categories else None,
            "key_trigger_words": [term for terms in indicators.values() for term in terms if term in lower],
            "engine": "heuristic-fallback",
        }

    def _tokenize(self, text):
        if self._tokenizer is not None:
            encoded = self._tokenizer(text, truncation=True, max_length=128, return_tensors="np")
            return {key: np.asarray(value).astype("int64") for key, value in encoded.items()}
        tokens = re.findall(r"\b[\w\u0900-\u097F]+\b", text.lower())[:128] or ["pad"]
        return {
            "input_ids": np.asarray([[index + 1 for index, _ in enumerate(tokens)]], dtype="int64"),
            "attention_mask": np.ones((1, len(tokens)), dtype="int64"),
        }

    def _predict_sync(self, text: str | Sequence[str]):
        payload = text if isinstance(text, str) else " ".join(str(item) for item in text if item)
        if self._fallback_mode or self._session is None:
            return self._fallback_score(payload)
        try:
            inputs = self._tokenize(payload)
            # Exported MuRIL graphs sometimes retain token_type_ids and
            # sometimes do not.  Match the graph's declared names exactly.
            names = {item.name for item in self._session.get_inputs()}
            output = self._session.run(None, {key: value for key, value in inputs.items() if key in names})[0]
            values = np.asarray(output)
            if values.ndim == 0:
                score = float(1 / (1 + np.exp(-float(values))))
            elif values.ndim >= 2 and values.shape[-1] == 2:
                logits = values[0]
                probabilities = np.exp(logits - np.max(logits))
                score = float(probabilities[1] / probabilities.sum())
            else:
                score = float(np.max(1 / (1 + np.exp(-values))))
            score = min(1.0, max(0.0, score))
            risk = "critical" if score >= 0.8 else "high" if score >= 0.6 else "medium" if score >= 0.35 else "low"
            return {"score": round(score, 4), "label": "fraud" if score >= 0.5 else "benign",
                    "risk_level": risk, "matched_categories": [], "coercion_category": None,
                    "key_trigger_words": [], "engine": "muril-onnx"}
        except Exception:
            return self._fallback_score(payload)

    async def predict(self, text: str | Sequence[str]):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._predict_sync, text)

    async def predict_batch(self, texts: Sequence[str]) -> list[dict[str, Any]]:
        """Run independent messages concurrently on the bounded worker pool."""
        return list(await asyncio.gather(*(self.predict(text) for text in texts)))

    async def close(self):
        self._executor.shutdown(wait=False, cancel_futures=True)
