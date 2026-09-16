# GuardAIN V2

GuardAIN is a privacy-preserving fraud triage service for phishing, digital
arrest, utility-disconnection, UPI-collect, and credential scams.

## Run locally

The API starts in a dependency-light heuristic mode when Redis, PostgreSQL,
ONNX Runtime, or a model file is unavailable:

```powershell
python -m pip install -r backend/requirements.txt
python run_all.py
```

Open the PWA at `http://127.0.0.1:3000` and the admin portal at
`http://127.0.0.1:3001`. The development administrator is `admin` with the
`guardain-local-admin` password; set `GUARDAIN_ADMIN_PASSWORD` before any
shared deployment.

## API

- `GET /health` reports service and fallback status.
- `POST /v1/verify` accepts scrubbed text, URL, VPA, and page context.
- `POST /v1/token` issues a client JWT for protected model/graph routes.
- `POST /v1/admin/login` issues an administrator JWT.
- `GET /v1/admin/incidents` and whitelist routes support triage.
- `POST /v1/telemetry` accepts privacy-scrubbed client events.

Set `JWT_SECRET_KEY`, `DATABASE_URL`, and `REDIS_URL` through the environment
in production. Never commit credentials or raw personal data.

## Optional model

`python ai_pipeline/export_onnx.py` downloads and exports a MuRIL classifier.
Without it, the deterministic fallback identifies common scam indicators.
`python ai_pipeline/generate_dataset.py` creates balanced synthetic JSONL
development data; it is not a substitute for a validated production model.

## Docker

Set `JWT_SECRET_KEY`, `GUARDAIN_ADMIN_PASSWORD`, and `DATABASE_URL`, then run:

```powershell
docker compose up --build
```

The extension can be loaded unpacked from `extension/`. Its API base URL is
configurable through `chrome.storage.local` as `guardainApiBaseUrl`.
