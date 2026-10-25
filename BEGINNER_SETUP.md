# GuardAIN beginner setup: do this in order

You do **not** need a cloud account to run the project on one laptop first.
Start locally, prove the portal and extension work, then connect cloud services
for access from other laptops.

## A. Run it locally first

1. Install Docker Desktop for Windows and start it. If Docker is unavailable,
   install Python 3.11 or newer instead.
2. Open PowerShell in the project folder and run:

   ```powershell
   .\scripts\doctor.ps1
   ```

3. If Docker is available, start the complete local stack:

   ```powershell
   docker compose up --build
   ```

   Otherwise run `./start.ps1`. Keep that window open.
4. Open `http://127.0.0.1:8080/`. Sign in with `admin` / `admin@26` for this
   local demo only.
5. In Chrome open `chrome://extensions`, switch on **Developer mode**, choose
   **Load unpacked**, and select the `extension` folder. In the extension popup
   set the server URL to `http://127.0.0.1:8080`.

## B. Create the cloud services

You must sign in to providers because this creates accounts and may incur
charges. Use one region for all services.

1. Create a managed PostgreSQL database. Copy its **internal/private URL** for
   the API host, or its TLS public URL if the provider does not offer private
   networking. It must include TLS (usually `?sslmode=require`).
2. Create a managed Redis/Key Value service. Copy its TLS URL, usually starting
   with `rediss://`.
3. Create a Docker web service from this repository's `Dockerfile`. The image
   automatically listens on the `PORT` supplied by the provider (or 8080
   locally). Add the variables in `cloud.env.example` through the provider's
   secret/environment-variable page.
4. Wait until the provider shows a public HTTPS backend URL. Open
   `https://YOUR-API/health`; it must say `database: true` and `redis: true`.

## C. Connect the portal and extension

1. Run the helper, replacing the URL:

   ```powershell
   .\scripts\connect_cloud.ps1 -ApiUrl "https://YOUR-API-HOST"
   ```

2. Push the code to GitHub. In Vercel choose **Add New → Project**, import the
   repository, set **Root Directory** to `admin_portal`, select **Other** as
   framework, leave build command empty and output directory as `.`. Deploy.
3. Copy the Vercel URL. On the API host add it exactly to `CORS_ORIGINS`, then
   redeploy the API.
4. On every laptop load/reload the extension and enter the HTTPS **API URL** in
   its popup. Do not enter the Vercel URL there.

## D. Train MuRIL only after collecting real data

The generated dataset is for development only. Obtain consented, independently
labelled fraud and benign messages, redact personal data, and keep a documented
data-use basis. Then follow the MuRIL section in `HOW_TO_IMPLEMENT_CLOUD.md`.

## Never do these

- Never put `DATABASE_URL`, Redis passwords, JWT keys or admin passwords into
  `admin_portal/config.js`, Vercel variables visible to the browser, or the
  Chrome extension.
- Never deploy with `admin@26`.
- Never use the synthetic-data model as evidence of real-world accuracy.
