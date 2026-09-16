"""Run the local GuardAIN API and static consoles without requiring ML services."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def start_static_server(directory: Path, port: int) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--directory", str(directory)])


def wait_for_api(url: str, timeout: float = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                return response.status == 200
        except Exception:
            time.sleep(0.25)
    return False


def main() -> int:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Start GuardAIN local services.")
    parser.add_argument("--api-port", type=int, default=int(os.getenv("PORT", "8080")))
    parser.add_argument("--pwa-port", type=int, default=3000)
    parser.add_argument("--admin-port", type=int, default=3001)
    parser.add_argument("--export-model", action="store_true", help="Download/export the optional MuRIL model first")
    args = parser.parse_args()
    (root / "data").mkdir(exist_ok=True)
    (root / "backend" / "models").mkdir(parents=True, exist_ok=True)

    dataset_path = root / "data" / "guardain_v2_dataset.jsonl"
    if not dataset_path.exists():
        subprocess.run(
            [sys.executable, "-m", "ai_pipeline.dataset_generator", "--output", str(dataset_path)],
            cwd=root, check=True,
        )

    if args.export_model:
        subprocess.run([sys.executable, str(root / "ai_pipeline" / "export_onnx.py")], cwd=root, check=True)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", str(args.api_port)],
        cwd=root, env=env,
    )
    pwa = start_static_server(root / "pwa", args.pwa_port)
    admin = start_static_server(root / "admin_portal", args.admin_port)
    if not wait_for_api(f"http://127.0.0.1:{args.api_port}/health"):
        for process in (api, pwa, admin):
            process.terminate()
        raise RuntimeError("FastAPI did not become healthy; inspect the API process output.")
    print(f"API:   http://127.0.0.1:{args.api_port}/health")
    print(f"PWA:   http://127.0.0.1:{args.pwa_port}/index.html")
    print(f"Admin: http://127.0.0.1:{args.admin_port}/index.html")
    print("GuardAIN is running (heuristic fallback is used when no model is present). Press Ctrl+C to stop.")
    try:
        while api.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for process in (api, pwa, admin):
            if process.poll() is None:
                process.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
