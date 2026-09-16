"""Export a fine-tuned Hugging Face classifier to an INT8 ONNX file.

Imports are lazy because the API intentionally supports a no-model fallback.
"""
from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_MODEL_ID = "google/muril-base-cased"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "backend" / "models" / "guardain_muril.onnx"


def export_model(model_id: str, output_path: Path, quantized_output_path: Path | None = None) -> Path:
    try:
        import torch
        from onnxruntime.quantization import QuantType, quantize_dynamic
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("Model export requires torch, transformers, and onnxruntime.") from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForSequenceClassification.from_pretrained(model_id, num_labels=2)
    model.eval()
    tokenizer.save_pretrained(output_path.parent / "guardain_tokenizer")
    inputs = tokenizer("Verify this message safely.", return_tensors="pt")
    token_type_ids = inputs.get("token_type_ids", torch.zeros_like(inputs["input_ids"]))

    class Classifier(torch.nn.Module):
        def __init__(self, wrapped):
            super().__init__()
            self.wrapped = wrapped

        def forward(self, input_ids, attention_mask, token_type_ids):
            return self.wrapped(input_ids=input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids).logits

    torch.onnx.export(
        Classifier(model),
        (inputs["input_ids"], inputs["attention_mask"], token_type_ids),
        str(output_path),
        input_names=["input_ids", "attention_mask", "token_type_ids"],
        output_names=["logits"],
        dynamic_axes={"input_ids": {0: "batch", 1: "sequence"}, "attention_mask": {0: "batch", 1: "sequence"}, "token_type_ids": {0: "batch", 1: "sequence"}, "logits": {0: "batch"}},
        opset_version=17,
    )
    quantized = quantized_output_path or output_path.with_suffix(".int8.onnx")
    quantize_dynamic(str(output_path), str(quantized), weight_type=QuantType.QUInt8, per_channel=False)
    if quantized.exists():
        output_path.unlink(missing_ok=True)
        quantized.replace(output_path)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export and quantize the GuardAIN classifier.")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()
    print(f"Exported model to {export_model(args.model_id, Path(args.output))}")


if __name__ == "__main__":
    main()
