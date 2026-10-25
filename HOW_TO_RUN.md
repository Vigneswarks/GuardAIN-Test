# GuardAIN V2: Run, Demo, and Validate

GuardAIN is a FastAPI threat-analysis platform with:

- Central admin portal and evidence viewer.
- Mobile PWA for message, URL, and UPI/VPA triage.
- Chrome Manifest V3 fraud-protection extension.
- Safe-zone bypass for search engines, approved news portals, `.gov.in`, and
  `.nic.in`.
- PII redaction, screenshot hashing, WHOIS enrichment, and incident telemetry.
- SQLite fallback for local development.
- PostgreSQL and Redis support through Docker Compose.

## 1. Prerequisites

For the local fallback:

- Windows 10/11.
- Python 3.11 or newer.
- PowerShell.

For the full container stack:

- Docker Desktop with the Linux engine running.

From PowerShell, move to the repository root:

```powershell
Set-Location "C:\Users\ksvig\OneDrive\Desktop\GuardAIN\Guardain v2"
```

Confirm the tools:

```powershell
python --version
docker --version
docker compose version
```

## 2. Recommended Docker run

Docker runs the API, PostgreSQL, and Redis together.

```powershell
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://127.0.0.1:8080/health
```

Expected health:

```json
{
  "status": "online",
  "service": "guardain-api",
  "database": true,
  "redis": true
}
```

Open the working application:

| Surface | URL |
|---|---|
| Admin portal | http://127.0.0.1:8080/ |
| Mobile PWA | http://127.0.0.1:8080/pwa/ |
| Swagger API | http://127.0.0.1:8080/docs |
| Health | http://127.0.0.1:8080/health |

Local development login:

```text
Username: admin
Password: admin@26
```

Do not use these credentials outside local development.

Stop the stack without deleting database/cache data:

```powershell
docker compose down
```

Delete Docker volumes only when you intentionally want a clean database:

```powershell
docker compose down -v
```

## 3. Windows local fallback

Use this path when Docker Desktop is unavailable. It runs the API, admin
portal, and PWA with SQLite. Redis is optional; health will report
`"redis": false` when no Redis service is available.

Create and activate the environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

If PowerShell blocks activation for the current user, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Start the application:

```powershell
$env:ENVIRONMENT = "development"
$env:DATABASE_URL = "sqlite:///./guardain.db"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:JWT_SECRET_KEY = "local-only-secret-with-at-least-32-characters"
$env:GUARDAIN_ADMIN_USERNAME = "admin"
$env:GUARDAIN_ADMIN_PASSWORD = "admin@26"
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8080
```

Keep this terminal running. Open:

- http://127.0.0.1:8080/
- http://127.0.0.1:8080/pwa/
- http://127.0.0.1:8080/docs

Stop the server with `Ctrl+C`.

The repository also includes an automated starter:

```powershell
.\start.ps1
```

Use the explicit commands above when you need to control environment values
or avoid automatic dependency installation.

## 4. End-to-end demo

### 4.1 Open the PWA

1. Open http://127.0.0.1:8080/pwa/.
2. Leave the sample message in the Chat / Text Triage tab.
3. Select **Verify Threat**.
4. Confirm that a risk score, classification, reason, and execution time appear.
5. Select **VPA** and test `merchant@upi`.
6. Select **URL** and test `https://verify-kyc.example`.

### 4.2 Test the safe-zone guarantee

The following search query must never be blocked:

```powershell
Invoke-RestMethod `
  "http://127.0.0.1:8080/v1/verify?url=https%3A%2F%2Fwww.google.com%2Fsearch%3Fq=digital%20arrest"
```

The response must contain:

```text
threat_score = 0.0
engine = safe-zone-bypass
```

### 4.3 Create an incident for the admin portal

```powershell
$incident = @{
  url = "https://verify-kyc.example/login"
  message = "Urgent KYC verification required"
  threat_score = 0.91
  source = "manual-demo"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri http://127.0.0.1:8080/v1/telemetry `
  -Method Post `
  -ContentType "application/json" `
  -Body $incident
```

Open the admin portal, sign in, and select **Refresh Telemetry Feed**. The
incident should appear as a critical event. Select **View Raw JSON** to see
the URL, SHA-256 DOM digest, and WHOIS enrichment.

## 5. API smoke tests

### Verify a suspicious message

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8080/v1/verify `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"CBI digital arrest. Pay bail immediately and share OTP.","url":""}'
```

### Analyze a VPA

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8080/v1/analyzer/vpa `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"vpa":"merchant@upi"}'
```

### Authenticate and read incidents

```powershell
$login = Invoke-RestMethod `
  -Uri http://127.0.0.1:8080/v1/admin/login `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"username":"admin","password":"admin@26"}'

$headers = @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod `
  -Uri http://127.0.0.1:8080/v1/admin/incidents `
  -Headers $headers
```

## 6. Run automated tests

Install development dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

Run the integration suite:

```powershell
python -m pytest -q
```

The tests exercise:

- API health and static portal/PWA delivery.
- Safe-zone and scam verification.
- Administrator login and protected incident feed.
- Invalid screenshot rejection.

## 7. Load the Chrome extension

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked**.
4. Choose:
   `C:\Users\ksvig\OneDrive\Desktop\GuardAIN\Guardain v2\extension`
5. Open the extension popup and confirm the API is reachable.

The local API base is:

```text
http://127.0.0.1:8080
```

The popup now includes **Central server HTTPS URL**. Enter the public HTTPS
API address and select **Save and test connection**. For testing on one private
LAN, an address such as `http://192.168.1.25:8080` is accepted.

The extension scans only targeted interactive scopes. On a high-risk result it
captures the visible tab, computes a SHA-256 screenshot hash, sends telemetry
to `/v1/telemetry`, and displays the eight-second circuit breaker. Selecting
**Proceed anyway** sets the session bypass lock.

## 8. MuRIL model

The API remains usable with the deterministic fallback classifier when the
ONNX model is not present. A base MuRIL checkpoint is not a fraud classifier;
it must first be fine-tuned on labeled data. Run the complete pipeline on a
GPU-equipped development machine:

```powershell
python -m pip install -r ai_pipeline\requirements.txt
python ai_pipeline\dataset_generator.py --count 2400
python ai_pipeline\train_muril.py --epochs 3 --batch-size 8
python ai_pipeline\export_onnx.py
```

Verify model artifacts:

```powershell
Test-Path backend\models\guardain_muril.onnx
Test-Path backend\models\guardain_muril.onnx.data
Test-Path backend\models\guardain_tokenizer
```

After restarting the API, `/health` must report
`inference.model_loaded: true` and `inference.engine: muril-onnx`. The portal
also displays **MuRIL ONNX ACTIVE**. Do not accept an exported base checkpoint
with a randomly initialized classification head.

## 9. Access from another laptop

The server already listens on all interfaces. On the central Windows PC, set
the active network profile to **Private**, open an elevated PowerShell window,
and run:

```powershell
.\scripts\enable_lan_access.ps1
.\start.ps1
```

The starter prints one or more LAN URLs. Open the appropriate URL from the
second laptop, for example `http://192.168.1.25:8080/`. Configure that same URL
in the extension popup on the second laptop. Both devices must be on the same
trusted LAN, and Windows must not be using a Public network profile.

For access over the internet, do not forward port 8080 directly. Deploy the
Docker image behind a public HTTPS reverse proxy/cloud service, use managed
PostgreSQL and Redis, and set the extension to `https://API_HOST`. See
`HOW_TO_IMPLEMENT_CLOUD.md`.

## 10. Troubleshooting

### Port 8080 is already in use

```powershell
Get-NetTCPConnection -LocalPort 8080 -State Listen
```

Stop only the identified process:

```powershell
Stop-Process -Id <PID>
```

### Docker cannot connect

Start Docker Desktop, wait for the Linux engine to become ready, then run:

```powershell
docker info
docker compose up -d --build
```

### Health reports `redis: false`

This is expected for the Python fallback unless Redis is running. Verification
continues to work; Docker mode starts Redis automatically.

### Clear local fallback data

Stop the API first, then remove only the generated local database:

```powershell
Remove-Item -LiteralPath .\guardain.db -Force -ErrorAction SilentlyContinue
```

Never delete the repository root or unrelated user files.

## 11. Production deployment

For managed PostgreSQL, Redis, HTTPS, CORS, secrets, monitoring, and backups,
follow [HOW_TO_IMPLEMENT_CLOUD.md](./HOW_TO_IMPLEMENT_CLOUD.md). Production
must use a unique JWT secret, a strong administrator password, HTTPS, and
PostgreSQL/Redis rather than SQLite.
