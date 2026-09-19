"""Remove explicitly obsolete GuardAIN demo artifacts and verify required files."""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OBSOLETE = ("README.md.bak", "test_bench.html", "run_all.py", "quickstart.sh")
REQUIRED = (
    "backend/app/config.py", "backend/app/auth.py", "backend/app/whois_engine.py",
    "backend/app/inference.py", "backend/app/main.py", "extension/manifest.json",
    "extension/background.js", "extension/content.js", "admin_portal/index.html",
    "pwa/index.html",
)


def clean(dry_run: bool = False) -> list[str]:
    removed: list[str] = []
    for name in OBSOLETE:
        path = ROOT / name
        if path.is_file():
            removed.append(name)
            if not dry_run:
                path.unlink()
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    if missing:
        raise FileNotFoundError("Required GuardAIN files are missing: " + ", ".join(missing))
    return removed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print({"removed": clean(args.dry_run), "verified": len(REQUIRED)})
