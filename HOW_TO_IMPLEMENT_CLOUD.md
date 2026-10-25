# GuardAIN Cloud and Redis Omnichannel Deployment

This runbook deploys GuardAIN as a cloud API with managed PostgreSQL,
managed Redis, a hosted admin portal and PWA, and a Chrome extension
configured for the public HTTPS API. It does not require police servers.

The repository supplies the application and Docker image. Cloud accounts,
DNS, TLS certificates, PostgreSQL, and Redis credentials must be supplied by
the operator and must not be committed to Git.

## 1. Target topology

```text
Chrome extension ─────┐
Admin portal ─────────┼── HTTPS ── GuardAIN FastAPI ── Managed PostgreSQL
PWA triage app ───────┘                  │
                                       Managed Redis
```

Use one API hostname, such as `api.guardain.example`, and HTTPS static
hostnames such as `admin.guardain.example` and `triage.guardain.example`.
Never expose PostgreSQL or Redis directly to the public internet.

## 2. Create managed PostgreSQL and Redis

Create one PostgreSQL database and one Redis instance in the same region as
the API. Any provider is supported if it supplies standard connection URLs.

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require
REDIS_URL=rediss://:PASSWORD@REDIS_HOST:6380/0
```

If the provider gives a `postgres://` URL it is also accepted. Preserve the
TLS parameters supplied by the provider. The API creates the
`url_observations` and `incidents` tables on startup.

Set `DATABASE_SSL_MODE=auto` when the URL includes `sslmode=require`, or
`DATABASE_SSL_MODE=require` when the provider requires TLS but omits that
query option. The API uses certificate-validated TLS for either setting.

Every administrator domain decision is also appended to a durable audit trail.
Back up PostgreSQL and test a restore before any institutional pilot.

## 3. Generate production secrets

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Configure these as cloud secret-manager values:

```text
ENVIRONMENT=production
JWT_SECRET_KEY=<generated value, at least 32 characters>
GUARDAIN_ADMIN_USERNAME=admin
GUARDAIN_ADMIN_PASSWORD=<unique password of at least 12 characters>
CORS_ORIGINS=https://admin.guardain.example,https://triage.guardain.example
```

Do not use `admin@26` in a shared deployment. It remains the development
default only. The local Compose default is `admin@26`; replace it before any
shared or production deployment.

## 4. Build and publish the API

From the repository root:

```powershell
docker build -t guardain-api:2.0.0 -f Dockerfile .
docker tag guardain-api:2.0.0 REGISTRY/guardain-api:2.0.0
docker push REGISTRY/guardain-api:2.0.0
```

Replace `REGISTRY` with the private registry for the selected provider.
Deploy the image as a web service listening on port `8080` and configure:

```text
DATABASE_URL
REDIS_URL
ENVIRONMENT=production
JWT_SECRET_KEY
GUARDAIN_ADMIN_USERNAME
GUARDAIN_ADMIN_PASSWORD
CORS_ORIGINS
PORT=8080
```

Redis is used for verification-result caching when reachable. If Redis is
temporarily unavailable, verification remains functional but `/health`
reports `"redis": false`; alert on that condition in production.

## 5. Verify the API

Replace `API_HOST` with the HTTPS API hostname:

```powershell
Invoke-RestMethod https://API_HOST/health

$login = Invoke-RestMethod `
  -Uri https://API_HOST/v1/admin/login `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"username":"admin","password":"<production-password>"}'

$headers = @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod `
  -Uri https://API_HOST/v1/admin/incidents `
  -Headers $headers
```

Expected health:

```json
{"status":"online","service":"guardain-api","database":true,"redis":true}
```

The load-balancer readiness endpoint is stricter and should return HTTP 200:

```powershell
Invoke-RestMethod https://API_HOST/ready
```

Before exposing the API, run the same dependency check with the production
environment configured. It never prints connection URLs or passwords:

```powershell
python scripts/cloud_preflight.py
```

Verify safe-zone behavior:

```powershell
Invoke-RestMethod `
  "https://API_HOST/v1/verify?url=https%3A%2F%2Fwww.google.com%2Fsearch%3Fq=digital%20arrest"
```

The result must have `threat_score` equal to `0.0` and
`engine` equal to `safe-zone-bypass`.

## 6. Host the admin portal and PWA

Deploy these directories to HTTPS static hosting:

```text
admin_portal/  -> https://admin.guardain.example
pwa/           -> https://triage.guardain.example

For a single-container deployment, the API also serves the admin portal at
`/` and the PWA at `/pwa/`. This is the simplest startup-grade deployment:
publish only the API hostname and use `https://API_HOST/` and
`https://API_HOST/pwa/`.
```

Before using the admin portal, configure its API base:

```javascript
sessionStorage.setItem("guardainApiUrl", "https://API_HOST");
location.reload();
```

For the PWA:

```javascript
localStorage.setItem("guardainApiUrl", "https://API_HOST");
location.reload();
```

For a permanent PWA deployment, inject this before its existing scripts:

```html
<script>window.GUARDAIN_API_URL = "https://API_HOST";</script>
```

The exact static origins must be present in `CORS_ORIGINS`.

## 7. Configure the Chrome extension

Load [extension/](./extension) unpacked during development. For production,
package and publish it through the Chrome Web Store or an organization
extension policy.

Open the extension popup, enter the cloud URL under **Central server HTTPS
URL**, and select **Save and test connection**. It stores the equivalent of:

```javascript
chrome.storage.local.set({
  guardainApiBaseUrl: "https://API_HOST"
});
```

High-risk telemetry is sent to `POST /v1/telemetry`, including the
URL, scrubbed DOM snapshot, screenshot data, hashes, browser metadata, and
timestamp. The backend performs WHOIS/DNS enrichment before persistence.
Routine scans send only the hostname and locally derived risk labels to
`POST /v1/verify`; page paths, query strings, and arbitrary page text remain
on the device. Every resulting observation is upserted into PostgreSQL, so a
new scam domain learned by one extension becomes shared reputation data.

## 8. MuRIL model: train, evaluate, export, then deploy

The application works in deterministic heuristic fallback mode until a
fine-tuned and provenance-marked model is present. Install the training
dependencies in a separate Python environment, train on independently
labelled and consented records, then export before building the image:

```powershell
python -m pip install -r ai_pipeline/requirements.txt
python ai_pipeline/train_muril.py --dataset data/approved_fraud_labels.jsonl --output backend/models/guardain_muril_finetuned
python ai_pipeline/export_onnx.py
```

The input JSONL must contain `message` and `label` (`fraud` or `benign`). The
trainer creates a stratified hold-out split and records accuracy, precision,
recall, F1, class distribution and a dataset fingerprint in
`guardain_training.json`. The bundled generated data is blocked by default;
`--allow-synthetic` exists only to smoke-test the pipeline and produces a
model that production refuses to load. Never describe its metrics as real
fraud-detection performance.

Then rebuild the image and configure:

```text
ONNX_MODEL_PATH=backend/models/guardain_muril.onnx
ONNX_TOKENIZER_PATH=backend/models/guardain_tokenizer
```

Rebuild/redeploy the image after exporting. Check `/health`; its `inference`
object must show `engine: muril-onnx` and `model_loaded: true` before relying
on model output. Model output remains an advisory input: the browser block
policy still requires URL/page evidence and does not block on message keywords
alone.

## 9. Observability and security

Alert on API 5xx responses, latency, HTTP 429 rates, failed database
connections, `/health` reporting `database: false` or `redis: false`, and
PostgreSQL/Redis resource pressure. Take encrypted PostgreSQL backups.
Redis is a cache and may be rebuilt; correctness must not depend on cached
data.

Never log raw DOM snapshots, screenshots, Aadhaar numbers, phone numbers,
payment-card data, passwords, or JWTs. Use HTTPS for every public surface.

## 10. Local Compose equivalent

With Docker Desktop running:

```powershell
$env:ENVIRONMENT = "development"
$env:JWT_SECRET_KEY = "local-only-secret-with-at-least-32-characters"
$env:GUARDAIN_ADMIN_PASSWORD = "admin@26"
$env:DATABASE_URL = "postgresql://guardain:guardain@postgres:5432/guardain"
$env:REDIS_URL = "redis://redis:6379/0"
$env:CORS_ORIGINS = "http://127.0.0.1:3000,http://127.0.0.1:3001"
docker compose up --build
```

For a production Compose deployment, set `ENVIRONMENT=production`,
`JWT_SECRET_KEY` to a unique value, and `GUARDAIN_ADMIN_PASSWORD` to a
unique password of at least 12 characters before starting the stack.

Then run:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
```

The Compose result should report both `"database": true` and `"redis": true`.
If Docker Desktop is unavailable, the normal local fallback is SQLite with
Redis disabled; that is not the cloud deployment state.
