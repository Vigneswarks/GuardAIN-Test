"""Fine-tune MuRIL for GuardAIN binary fraud classification.

This script trains a real sequence-classification head, evaluates it on a
held-out split, and saves a Hugging Face checkpoint that export_onnx.py can
convert for the API runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path


def load_records(path: Path, allow_synthetic: bool) -> tuple[list[dict[str, object]], bool]:
    records = []
    synthetic = False
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            # The bundled generator uses these IDs. It is useful for wiring
            # tests, but it is not evidence for a deployable fraud model.
            synthetic = synthetic or str(item.get("id", "")).startswith(("fraud-", "benign-"))
            records.append({"text": str(item["message"]), "label": 1 if item["label"] == "fraud" else 0})
    if len(records) < 20:
        raise ValueError("Training requires at least 20 labeled records")
    if len({int(record["label"]) for record in records}) != 2:
        raise ValueError("Training requires both benign and fraud labels")
    if synthetic and not allow_synthetic:
        raise ValueError(
            "Refusing bundled synthetic data. Use independently labelled, consented data; "
            "pass --allow-synthetic only for pipeline smoke testing."
        )
    return records, synthetic


def stratified_split(records: list[dict[str, object]], seed: int) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    groups: dict[int, list[dict[str, object]]] = {0: [], 1: []}
    for record in records:
        groups[int(record["label"])].append(record)
    rng = random.Random(seed)
    train, validation = [], []
    for group in groups.values():
        rng.shuffle(group)
        split = min(len(group) - 1, max(1, int(len(group) * 0.8)))
        train.extend(group[:split])
        validation.extend(group[split:])
    rng.shuffle(train)
    rng.shuffle(validation)
    return train, validation


def binary_metrics(predictions: list[int], labels: list[int]) -> dict[str, float | int]:
    tp = sum(pred == actual == 1 for pred, actual in zip(predictions, labels))
    tn = sum(pred == actual == 0 for pred, actual in zip(predictions, labels))
    fp = sum(pred == 1 and actual == 0 for pred, actual in zip(predictions, labels))
    fn = sum(pred == 0 and actual == 1 for pred, actual in zip(predictions, labels))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)
    return {"accuracy": round((tp + tn) / max(1, len(labels)), 4), "precision": round(precision, 4),
            "recall": round(recall, 4), "f1": round(f1, 4), "true_positive": tp,
            "true_negative": tn, "false_positive": fp, "false_negative": fn}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fine-tune MuRIL for GuardAIN fraud classification")
    parser.add_argument("--dataset", default="data/guardain_v2_dataset.jsonl")
    parser.add_argument("--output", default="backend/models/guardain_muril_finetuned")
    parser.add_argument("--model-id", default="google/muril-base-cased")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--max-records", type=int, default=0, help="Limit records for a labelled demo smoke test")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--allow-synthetic", action="store_true", help="Only for development pipeline smoke tests")
    args = parser.parse_args()

    try:
        import torch
        from torch.utils.data import DataLoader, Dataset
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("Install ai_pipeline/requirements.txt before training") from exc

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    dataset_path = Path(args.dataset)
    records, synthetic = load_records(dataset_path, args.allow_synthetic)
    if args.max_records:
        if args.max_records < 20:
            raise ValueError("--max-records must be at least 20")
        rng = random.Random(args.seed)
        groups = {0: [], 1: []}
        for record in records:
            groups[int(record["label"])].append(record)
        for group in groups.values():
            rng.shuffle(group)
        per_class = max(10, args.max_records // 2)
        records = groups[0][:per_class] + groups[1][:per_class]
    train_records, validation_records = stratified_split(records, args.seed)
    tokenizer = AutoTokenizer.from_pretrained(args.model_id)

    class FraudDataset(Dataset):
        def __init__(self, items):
            self.items = items

        def __len__(self):
            return len(self.items)

        def __getitem__(self, index):
            item = self.items[index]
            encoded = tokenizer(
                item["text"], truncation=True, padding="max_length",
                max_length=args.max_length, return_tensors="pt",
            )
            result = {key: value.squeeze(0) for key, value in encoded.items()}
            result["labels"] = torch.tensor(item["label"], dtype=torch.long)
            return result

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_id,
        num_labels=2,
        id2label={0: "benign", 1: "fraud"},
        label2id={"benign": 0, "fraud": 1},
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    train_loader = DataLoader(FraudDataset(train_records), batch_size=args.batch_size, shuffle=True)
    validation_loader = DataLoader(FraudDataset(validation_records), batch_size=args.batch_size)

    for epoch in range(max(1, args.epochs)):
        model.train()
        loss_total = 0.0
        for batch in train_loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            output = model(**batch)
            output.loss.backward()
            optimizer.step()
            loss_total += float(output.loss.detach().cpu())

        model.eval()
        predictions: list[int] = []
        labels_seen: list[int] = []
        with torch.inference_mode():
            for batch in validation_loader:
                labels = batch.pop("labels")
                logits = model(**{key: value.to(device) for key, value in batch.items()}).logits.cpu()
                predictions.extend(int(value) for value in logits.argmax(dim=-1).tolist())
                labels_seen.extend(int(value) for value in labels.tolist())
        metrics = binary_metrics(predictions, labels_seen)
        print(json.dumps({
            "epoch": epoch + 1,
            "train_loss": round(loss_total / max(1, len(train_loader)), 6),
            "validation": metrics,
            "device": str(device),
        }))

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output)
    tokenizer.save_pretrained(output)
    fingerprint = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    metadata = {
        "base_model": args.model_id,
        "training_records": len(train_records),
        "validation_records": len(validation_records),
        "epochs": args.epochs,
        "validation": metrics,
        "class_distribution": {str(label): count for label, count in sorted(Counter(int(x["label"]) for x in records).items())},
        "dataset_sha256": fingerprint,
        "synthetic_data": synthetic,
        "demo_record_limit": args.max_records or None,
        "seed": args.seed,
    }
    (output / "guardain_training.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved fine-tuned checkpoint to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
