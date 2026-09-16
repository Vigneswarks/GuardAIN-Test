# How to Run GuardAIN

This guide covers the complete local development flow, authentication, Docker,
and the browser extension.

## 1. Prepare Python

Use Python 3.11 or newer. From the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

If PowerShell blocks activation, run the project with the explicit interpreter:

```powershell
.\.venv\Scripts\python.exe run_all.py
```

## 2. Start the whole local project

```powershell
python run_all.py
```

The launcher starts:

| Component | URL |
| --- | --- |
| FastAPI | <http://127.0.0.1:8080> |
| Health | <http://127.0.0.1:8080/health> |
| Swagger docs | <http://127.0.0.1:8080/docs> |
| PWA | <http://127.0.0.1:3000> |
| Admin portal | <http://127.0.0.1:3001> |

The first startup can take longer while optional model libraries initialize.
The launcher allows up to 60 seconds for the API health check. The project
continues in heuristic fallback mode when Redis, PostgreSQL, or an ONNX model
is unavailable.

Custom ports:

```powershell
python run_all.py --api-port 8080 --pwa-port 3000 --admin-port 3001
```

Stop the launcher with `Ctrl+C`.

## 3. Test the API and authentication

Check health:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
```

Verify a message without authentication:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8080/v1/verify `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"text_content":"Your electricity bill is due today. Verify KYC immediately."}'
```

Sign in to the admin API using the development account:

```powershell
$login = Invoke-RestMethod `
  -Uri http://127.0.0.1:8080/v1/admin/login `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"username":"admin","password":"guardain-local-admin"}'

$headers = @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod `
  -Uri http://127.0.0.1:8080/v1/admin/incidents `
  -Headers $headers
```

The same credentials work in the admin portal. For a shared deployment, set
these environment variables before starting the API:

```powershell
$env:GUARDAIN_ADMIN_PASSWORD = "use-a-strong-password"
$env:JWT_SECRET_KEY = "use-a-long-random-secret"
```

## 4. Run with Docker Compose

Docker Compose requires Docker Desktop:

```powershell
$env:JWT_SECRET_KEY = "replace-with-a-long-random-secret"
$env:GUARDAIN_ADMIN_PASSWORD = "replace-with-a-strong-admin-password"
$env:DATABASE_URL = "postgresql://guardain:guardain@postgres:5432/guardain"
docker compose up --build
```

The API waits for healthy Redis and PostgreSQL containers. Stop it with
`Ctrl+C`; remove the containers and volumes only when you intentionally want
to delete local database/cache data:

```powershell
docker compose down
```

## 5. Load the Chrome extension

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked** and choose the `extension` folder.
4. Open the extension details and enable **Allow access to file URLs**.
5. Open `extension\scam.html` to see the blocking flow.
6. Open `extension\safe.html` to see the safe flow.

The extension is offline-first. Its optional API base URL is stored as
`guardainApiBaseUrl` in Chrome local storage.

## Troubleshooting

- **API did not become healthy:** wait for the first startup to finish, then
  retry. Check that ports 8080, 3000, and 3001 are not already in use.
- **Admin login fails:** use the configured `GUARDAIN_ADMIN_PASSWORD`; if it is
  unset, the development password is `guardain-local-admin`.
- **Fallback status is true:** this is expected without reachable Redis and
  PostgreSQL. Verification still works in local heuristic mode.
- **Extension changes are not visible:** reload the extension from
  `chrome://extensions`.
