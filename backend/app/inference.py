"""ONNX inference with a deterministic, privacy-safe fallback classifier."""
from __future__ import annotations

import asyncio
import json
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
    def __init__(self, model_path=None, tokenizer_path=None, providers=None, allow_synthetic_model=None):
        root = Path(__file__).resolve().parents[2]
        self.model_path = str(Path(model_path or os.getenv(
            "ONNX_MODEL_PATH", str(root / "backend" / "models" / "guardain_muril.onnx")
        )))
        self.tokenizer_path = str(Path(tokenizer_path or os.getenv(
            "ONNX_TOKENIZER_PATH", str(root / "backend" / "models" / "guardain_tokenizer")
        )))
        self.providers = providers or ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self.allow_synthetic_model = (
            str(os.getenv("GUARDAIN_ALLOW_SYNTHETIC_MODEL", "false")).lower() == "true"
            if allow_synthetic_model is None else bool(allow_synthetic_model)
        )
        self._session = None
        self._tokenizer = None
        self._fallback_mode = True
        self._model_metadata: dict[str, Any] = {}
        self.closed = False
        self._executor = ThreadPoolExecutor(
            max_workers=max(2, min(8, int(os.getenv("GUARDAIN_INFERENCE_WORKERS", "4")))),
            thread_name_prefix="guardain-inference",
        )
        self._load_model()

    def _load_model(self):
        provenance_path = str(Path(self.model_path).with_suffix(".training.json"))
        if (ort is None or np is None or not os.path.isfile(self.model_path)
                or not os.path.isfile(provenance_path) or AutoTokenizer is None
                or not os.path.isdir(self.tokenizer_path)):
            return
        try:
            metadata = json.loads(Path(provenance_path).read_text(encoding="utf-8"))
            # Synthetic-only runs are intentionally never accepted as a
            # production decision model. They can still demonstrate the full
            # train/export/inference plumbing in development.
            if metadata.get("synthetic_data") and not self.allow_synthetic_model:
                return
            available = set(ort.get_available_providers())
            selected = [provider for provider in self.providers if provider in available]
            session_options = ort.SessionOptions()
            # ONNX Runtime can oversubscribe high-core Windows machines and
            # make a small MuRIL request appear hung. Bound the CPU pools for
            # predictable interactive latency.
            session_options.intra_op_num_threads = max(1, int(os.getenv("GUARDAIN_ONNX_INTRA_OP_THREADS", "2")))
            session_options.inter_op_num_threads = max(1, int(os.getenv("GUARDAIN_ONNX_INTER_OP_THREADS", "1")))
            session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            self._session = ort.InferenceSession(
                self.model_path, sess_options=session_options, providers=selected or None
            )
            if AutoTokenizer is not None and os.path.isdir(self.tokenizer_path):
                self._tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_path, local_files_only=True)
            self._fallback_mode = self._tokenizer is None
            self._model_metadata = metadata if not self._fallback_mode else {}
        except Exception:
            self._session = None
            self._tokenizer = None
            self._fallback_mode = True
            self._model_metadata = {}

    @staticmethod
    def _message_breakdown(payload: str) -> dict[str, Any]:
        lower = payload.lower()
        patterns = {
            "authority_impersonation": ("cbi", "police", "court", "customs", "income tax", "rbi", "cybercrime", "पुलिस", "साइबर क्राइम"),
            "urgency_or_threat": ("urgent", "immediately", "today", "last chance", "within 24 hours", "block your account", "disconnect", "तुरंत", "अभी", "खाता बंद"),
            "credential_request": ("otp", "password", "pin", "cvv", "aadhaar", "pan", "bank login", "verify account", "ओटीपी", "पासवर्ड", "आधार"),
            "payment_request": ("upi", "qr", "pay now", "transfer", "collect request", "fee", "bail", "processing charge", "पैसे भेज", "भुगतान", "यूपीआई"),
            "suspicious_link": ("http://", "https://", "bit.ly", "tinyurl", "click link", "click here"),
            "investment_or_job_lure": ("guaranteed return", "double your money", "work from home", "part time job", "investment"),
        }
        matches = {
            category: [term for term in terms if term in lower]
            for category, terms in patterns.items()
        }
        matches = {category: terms for category, terms in matches.items() if terms}
        all_terms = [term for terms in matches.values() for term in terms]
        return {
            "patterns": list(matches),
            "matched_phrases": all_terms,
            "pattern_details": matches,
            "signals": {
                "urgency": "urgency_or_threat" in matches,
                "impersonation": "authority_impersonation" in matches,
                "credential_request": "credential_request" in matches,
                "payment_request": "payment_request" in matches,
                "link_present": "suspicious_link" in matches,
            },
        }

    @staticmethod
    def _fallback_score(payload: str) -> dict[str, Any]:
        lower = payload.lower()
        indicators = {
            "digital_arrest": ("digital arrest", "cbi", "bail", "court order", "police notice", "cybercrime", "डिजिटल गिरफ्तारी", "पुलिस", "साइबर क्राइम"),
            "utility_disconnection": ("electricity", "bill paid", "disconnect", "power cut", "utility", "meter", "बिजली", "कनेक्शन काट"),
            "upi_collect": ("upi qr", "qr collect", "collect request", "paytm qr", "phonepe", "scan this qr", "यूपीआई", "क्यूआर"),
            "phishing": ("verify account", "update kyc", "click link", "login urgently", "secure your account", "otp", "ओटीपी", "खाता बंद", "पासवर्ड"),
        }
        score = 0.04
        weights = {"digital_arrest": 0.46, "utility_disconnection": 0.32,
                   "upi_collect": 0.34, "phishing": 0.34}
        categories = []
        for category, terms in indicators.items():
            if any(term in lower for term in terms):
                categories.append(category)
                score += weights.get(category, 0.18)
        if re.search(r"\b(otp|password|aadhaar|pan|bank login|upi id)\b|ओटीपी|पासवर्ड|आधार", lower):
            score += 0.12
        if re.search(r"\b(urgent|immediately|today|last chance|within \d+ hours|block your account)\b|तुरंत|अभी|खाता बंद", lower):
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
            "message_breakdown": MuRILInferenceService._message_breakdown(payload),
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
            explainable = self._fallback_score(payload)
            model_score = min(1.0, max(0.0, score))
            if self._model_metadata.get("synthetic_data"):
                # A tiny synthetic checkpoint demonstrates the MuRIL runtime,
                # but is not independently calibrated. Blend its raw score
                # with explicit multilingual corroboration for exhibition
                # safety, while returning model_score separately and clearly.
                score = 0.6 * model_score + 0.4 * float(explainable["score"])
                engine = "muril-onnx-demo-hybrid"
                calibration = "synthetic-demo-safety-blend"
            else:
                score = model_score
                engine = "muril-onnx"
                calibration = "unvalidated-model-probability"
            score = round(min(1.0, max(0.0, score)), 4)
            risk = "critical" if score >= 0.8 else "high" if score >= 0.6 else "medium" if score >= 0.35 else "low"
            return {"score": score, "label": "fraud" if score >= 0.5 else "benign",
                    "risk_level": risk, "matched_categories": explainable["matched_categories"],
                    "coercion_category": explainable["coercion_category"],
                    "key_trigger_words": explainable["key_trigger_words"],
                    "message_breakdown": explainable["message_breakdown"],
                    "engine": engine, "model_score": round(model_score, 4),
                    "calibrated": False, "calibration_mode": calibration}
        except Exception:
            return self._fallback_score(payload)

    async def predict(self, text: str | Sequence[str]):
        # This quantized MuRIL graph completes quickly on CPU, while some
        # Windows ONNX Runtime builds deadlock when a session constructed on
        # the main thread is first executed in a ThreadPoolExecutor worker.
        # Keep the deterministic fallback in the pool, but execute the loaded
        # session on its owning thread for predictable interactive latency.
        if not self._fallback_mode and self._session is not None:
            return self._predict_sync(text)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._predict_sync, text)

    async def predict_batch(self, texts: Sequence[str]) -> list[dict[str, Any]]:
        """Run independent messages concurrently on the bounded worker pool."""
        return list(await asyncio.gather(*(self.predict(text) for text in texts)))

    async def close(self):
        self._executor.shutdown(wait=False, cancel_futures=True)
        self.closed = True

    def status(self) -> dict[str, Any]:
        engine = "heuristic-fallback"
        if not self._fallback_mode:
            engine = "muril-onnx-demo" if self._model_metadata.get("synthetic_data") else "muril-onnx"
        return {
            "engine": engine,
            "model_loaded": not self._fallback_mode,
            "tokenizer_loaded": self._tokenizer is not None,
            "model_path": self.model_path,
            "model_metadata": self._model_metadata,
        }
