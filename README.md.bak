# GuardAIN V2

GuardAIN is a privacy-preserving fraud triage project with:

- a FastAPI backend with deterministic heuristic fallback detection;
- a PWA triage console;
- an administrator incident portal;
- an optional Chrome Manifest V3 extension; and
- optional Redis, PostgreSQL, and ONNX model integrations.

V2 exposes public triage endpoints at `POST /v1/verify`, `/v1/analyzer/vpa`,
`/v1/analyzer/url`, `/v1/analyzer/apk`, and `POST /v1/telemetry`.  The URL
analyzer reports entropy, best-effort WHOIS age, and brand typosquatting
distance.  The APK endpoint accepts metadata and never stores an uploaded
binary.  When MuRIL is unavailable, a bounded thread pool runs the
privacy-safe deterministic fallback.

## Quick start

From the project root, run the following in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python run_all.py
```

If no virtual environment exists, create one first:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Open these URLs after startup:

- PWA: <http://127.0.0.1:3000>
- Admin portal: <http://127.0.0.1:3001>
- API health: <http://127.0.0.1:8080/health>
- API docs: <http://127.0.0.1:8080/docs>

The launcher starts the API and both static consoles. Press `Ctrl+C` to stop
all three processes.

## Development authentication

The admin portal uses `POST /v1/admin/login` and JWT bearer tokens.

- Username: `admin` (or `GUARDAIN_ADMIN_USERNAME`)
- Password: set `GUARDAIN_ADMIN_PASSWORD`; if omitted in development a
  random password is generated for the process and printed nowhere.

Development passwords are generated per process when not supplied. Before
sharing or deploying the project, set `GUARDAIN_ADMIN_PASSWORD` and
`JWT_SECRET_KEY` (at least 32 random characters) to strong secret values.
Production configuration rejects short keys and the development password.
Do not commit `.env` files or credentials.

All text and telemetry are scrubbed for Aadhaar, Indian phone numbers, payment
cards, bank accounts, VPA and email before inference or persistence. JWTs are
HS256 by default and must be sent as `Authorization: Bearer ...` for admin
incidents and protected legacy routes. Rate limits are applied per API key and
the extension performs only targeted DOM scanning; Google/Bing/DuckDuckGo,
The Hindu, Times of India, `.gov.in`, and `.nic.in` are explicit safe zones.

## Dataset and model export

`python -m ai_pipeline.dataset_generator` creates at least 2,000 JSONL
records covering valid/scam VPAs, safe/phishing URLs, Hinglish and Devanagari
messages. `run_all.py` creates `data/guardain_v2_dataset.jsonl` when absent.
`python ai_pipeline\export_onnx.py` exports a dynamic-sequence MuRIL graph and
quantizes its weights to dynamic `QUInt8` when the optional ML dependencies
are installed.

The public `POST /v1/verify` endpoint does not require a token. Protected
model/graph endpoints require both a bearer token from `POST /v1/token` and an
`X-API-Key` header.

## Docker

Docker Compose starts Redis, PostgreSQL, and the API:

```powershell
$env:JWT_SECRET_KEY = "replace-with-a-long-random-secret"
$env:GUARDAIN_ADMIN_PASSWORD = "replace-with-a-strong-admin-password"
$env:DATABASE_URL = "postgresql://guardain:guardain@postgres:5432/guardain"
docker compose up --build
```

The container API is available at <http://127.0.0.1:8080>. See
[HOW_TO_RUN.md](HOW_TO_RUN.md) for health checks, authentication examples,
troubleshooting, and extension setup.

## Optional model export

The default local mode uses `heuristic-fallback-v1`, so model export is not
required:

```powershell
python ai_pipeline\export_onnx.py
python run_all.py --export-model
```

The export downloads model assets and may require substantial disk space and
network access.
