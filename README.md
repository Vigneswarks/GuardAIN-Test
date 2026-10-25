# GuardAIN V2

GuardAIN is a cloud-ready cyber-threat interception platform focused on:

- MuRIL/ONNX Hinglish and Devanagari message analysis.
- Central incident reporting with screenshot, DOM hash, browser metadata, and
  WHOIS/DNS enrichment.
- A Chrome Manifest V3 extension with safe-domain bypass, targeted scanning,
  session override, screenshot capture, and an 8-second circuit breaker.
- A JWT/bcrypt-protected central admin portal.
- A mobile PWA for message, URL, and UPI/VPA triage.
- PostgreSQL persistence with SQLite local fallback and Redis verification
  caching.

## Fastest local start

### Docker with PostgreSQL and Redis

Start Docker Desktop, then run from the repository root:

```powershell
docker compose up -d --build
```

Open:

- Admin portal: <http://127.0.0.1:8080/>
- PWA: <http://127.0.0.1:8080/pwa/>
- API health: <http://127.0.0.1:8080/health>
- Swagger: <http://127.0.0.1:8080/docs>

The local Compose credentials are `admin` / `admin@26`. Replace them before
any shared deployment.

### Local Python fallback

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8080
```

This uses SQLite if PostgreSQL is unavailable and continues without Redis.

## Core API

```text
POST /v1/admin/login
GET  /v1/verify
POST /v1/verify
POST /v1/analyzer/vpa
POST /v1/reports/incidents
POST /v1/telemetry
GET  /v1/admin/incidents
GET  /health
```

Incident reports are authenticated only when reading the admin feed. High-risk
extension telemetry is accepted, enriched asynchronously, and persisted.
Every extension scan also performs a privacy-limited central check using only
the hostname and local risk labels. The resulting URL/domain observation is
upserted into the shared database and becomes available to every connected
extension and the administrator domain-intelligence view.

## Chrome extension

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Choose **Load unpacked**.
4. Select the [extension/](./extension) directory.
5. It automatically uses the production central API:

```text
https://guardain-api.onrender.com
```

No setup is needed on another laptop after loading the extension. Change this
only when deliberately testing against a local/private API.

For a double-clicked local `file:///...` demo fixture, Chrome also requires
**Extensions → GuardAIN Details → Allow access to file URLs**. This is a
browser-controlled permission. The recommended no-setup test is
`https://guardain-api.onrender.com/demo/extension-test`.

The extension bypasses Google, Bing, DuckDuckGo, verified news portals,
`.gov.in`, and `.nic.in`. It scans only interactive scopes, honors
`sessionStorage.guardain_bypass_active`, captures high-risk tabs, uploads
scrubbed telemetry, and closes the tab after the emergency countdown.

## MuRIL model

The inference service uses a fine-tuned local ONNX/tokenizer when available and
falls back to deterministic classification when unavailable. Model binaries are
intentionally excluded from Git because the ONNX data file is very large. Run
`dataset_generator.py`, `train_muril.py`, and then `export_onnx.py`; exporting
the untrained base MuRIL classification head is explicitly rejected.
The dataset utility is [ai_pipeline/dataset_generator.py](./ai_pipeline/dataset_generator.py).

## Cloud deployment

Use [HOW_TO_IMPLEMENT_CLOUD.md](./HOW_TO_IMPLEMENT_CLOUD.md) for managed
PostgreSQL, managed Redis, Docker registry publishing, HTTPS/CORS, static
portal/PWA hosting, extension configuration, secrets, monitoring, and backups.

Required production values:

```text
ENVIRONMENT=production
DATABASE_URL=postgresql://...
REDIS_URL=rediss://...
JWT_SECRET_KEY=<at least 32 random characters>
GUARDAIN_ADMIN_PASSWORD=<at least 12 random characters>
CORS_ORIGINS=https://admin.example.com,https://pwa.example.com
```

## Project layout

```text
backend/       FastAPI, auth, database, WHOIS, MuRIL inference
extension/     Manifest V3 extension and emergency response flow
admin_portal/  Central incident dashboard and evidence export
pwa/           Mobile message, URL, and VPA triage
ai_pipeline/   MuRIL export and dataset generation
docker-compose.yml
Dockerfile
```
