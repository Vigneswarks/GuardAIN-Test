# Deploy the administrator portal on Vercel

The Vercel site is the frontend. FastAPI, MuRIL, PostgreSQL and Redis run on
your HTTPS backend. The extension connects directly to that backend.

1. Deploy the backend Docker image to your cloud container host. Configure
   DATABASE_URL, REDIS_URL, ENVIRONMENT=production, JWT_SECRET_KEY and a strong
   GUARDAIN_ADMIN_PASSWORD using the host's secret settings. Keep database
   and Redis ports private. Obtain its public HTTPS origin.
2. Set admin_portal/config.js to:
   `window.GUARDAIN_API_URL = "https://YOUR-API-HOST";`
   This URL is public configuration. Never put admin passwords, JWT signing
   keys, database credentials or Redis URLs in this file or on Vercel frontend.
3. Push your reviewed source to your Git repository. On Vercel choose Add New
   Project, import the repository, set Root Directory to admin_portal and
   Framework Preset to Other. Leave the build command empty and set Output
   Directory to `.`. Deploy. The included vercel.json adds response headers.
4. Set backend CORS_ORIGINS to the exact Vercel origin, e.g.
   `https://guardain-admin.vercel.app`. Redeploy/restart the backend. Add a
   custom domain explicitly if you use one. Preview URLs are separate origins;
   do not use a wildcard to enable all Vercel customers.
5. Open your Vercel site and log in using the backend admin credentials. Test
   message analysis, domain reviews and the incident feed. Vercel environment
   variables do not automatically modify static config.js; edit it and redeploy.
6. On each laptop load extension/, then set its Central server URL to the
   HTTPS BACKEND origin, not the Vercel frontend. Save and test. Reload the
   extension after installing code updates and refresh already-open web tabs.

## Acceptance checks before a real pilot

- google.com, its true subdomains, and configured government/news domains:
  no scan, screenshot, block or close. google.com.attacker.example is not safe.
- A fraud-awareness article mentioning digital arrest: no auto-close.
- A normal password form alone: no auto-close.
- Coercive urgent demand + credential/payment collection + insecure or
  cross-origin form: warning with an eight-second countdown.
- Proceed anyway cancels closure; navigation prevents an old verdict from
  closing the new page. Test on disposable tabs on your own controlled site.
- New domain observations appear as pending. Only an authenticated analyst
  can promote a domain to malicious or safe. Client reports never alone
  establish confirmed reputation.
- Screenshot reports appear in the authenticated incident feed with a matching
  SHA-256 hash. Background tabs or failed capture produce metadata reports;
  focus changes discard the capture. Offline reports retry every minute to
  their original configured backend. A bounded local queue prevents unbounded
  screenshot storage; the popup reports delivery or retry state.
- MuRIL activation requires the checkpoint, tokenizer and training metadata.
  The present synthetic dataset is a development fixture, not evidence of
  real-world accuracy. Validate on independently labeled Hindi, Hinglish and
  English fraud/benign messages, split by source/template, and measure false
  positives, precision, recall and calibration before a real pilot.

## Current limits

No cloud account or domain has been provisioned by this code change. Real
PostgreSQL/cloud connectivity and two-laptop Chrome behavior must be tested on
your deployment. Automated tests use SQLite and mocked Chrome APIs.
MuRIL training dependencies are not installed in the project environment.
The page policy uses structured facts; raw page text is not automatically
sent to MuRIL. Explicitly submitted messages use the message analyzer.
Screenshots may contain personal information and need access/retention policy.
The public intake API still needs enrolled-device authentication and distributed
abuse controls before broad public rollout. Operator RBAC, durable audit logs,
backup restoration and an independently reviewed security assessment are
also required before government deployment. UI labels are not certification.

Reference: https://vercel.com/docs/builds/configure-a-build

## Example backend setup on Render

Create PostgreSQL and a Redis-compatible Render Key Value service in the
same region as the API. Create a Web Service from your Git repository using
the Docker runtime and root Dockerfile. Set PORT=8080 (the image listens on
8080), health check path /health, and supply the internal datastore URLs via
DATABASE_URL and REDIS_URL. Set ENVIRONMENT=production and strong admin/JWT
secrets. Use its assigned HTTPS URL as the portal config.js API origin.
Add the final Vercel origin to CORS_ORIGINS and redeploy the API.

Select compute/storage according to measured model memory and throughput;
review provider costs before provisioning. An always-available backend is
needed for central checks. This guide does not create paid resources.

References: https://render.com/docs/docker and https://render.com/docs/web-services
