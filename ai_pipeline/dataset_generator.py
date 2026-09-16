"""GuardAIN V2 synthetic dataset generator.

The implementation lives in :mod:`generate_dataset` for compatibility with
older launch scripts; this module provides the documented entry point.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .generate_dataset import generate_dataset, write_dataset
except ImportError:  # direct ``python ai_pipeline/dataset_generator.py``
    from generate_dataset import generate_dataset, write_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate GuardAIN fraud-triage JSONL data.")
    parser.add_argument("--count", type=int, default=2400)
    parser.add_argument("--output", default="data/guardain_v2_dataset.jsonl")
    args = parser.parse_args()
    count = max(2000, args.count)
    samples = generate_dataset(count)
    path = Path(args.output)
    write_dataset(samples, path)
    print(json.dumps({"records": len(samples), "path": str(path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
