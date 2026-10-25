# GuardAIN project showcase guide

This guide gives a repeatable final-year demonstration. Every page below is a
local fictional training fixture; it uses no real bank, UPI account, payment,
credential collection, or public victim data.

## Before the audience arrives

1. Start Docker Desktop, then run `docker compose up --build`, or run
   `./start.ps1` when using the local Python/SQLite path.
2. Confirm `http://127.0.0.1:8080/health` reports `status: online` and
   `database: true`.
3. Load/reload the Chrome extension from the `extension` folder.
4. The extension automatically uses `https://guardain-api.onrender.com`.
   Open its popup and confirm **Connected**; no endpoint needs to be typed on
   another laptop.
5. For a local `file:///.../demo-scam-test.html` test, open the GuardAIN
   extension's **Details** page and enable **Allow access to file URLs**. This
   is a Chrome permission that an extension cannot enable by itself. Otherwise
   use the hosted test URL below.
6. Keep the test tab focused. Screenshot capture is intentionally limited to
   the visible warning tab.

## Demonstration sequence

| Stage | URL path | Expected GuardAIN behavior | What it proves |
|---|---|---|---|
| 1 | `/demo/awareness` | No overlay, close, or incident | Fraud words alone never cause blocking |
| 2 | `/demo/normal-login` | No overlay or high-risk incident | A normal same-origin login is not treated as fraud |
| 3 | `/demo/review-only` | Review/suspicious state only; no closure | Collection plus urgency alone is not enough to close a page |
| 4 | `/demo/extension-test` | Warning, evidence/report attempt, eight-second close | Corroborated credential phishing is blocked |
| 5 | `/demo/upi-payment` | Warning, evidence/report attempt, eight-second close | Corroborated urgent UPI/payment fraud is blocked |

For example, stage 4 is:

```text
https://guardain-api.onrender.com/demo/extension-test
```

Replace the path for each stage in the table. Do not click **Proceed anyway**
on the two high-risk pages; it is the operator/user override and cancels the
circuit breaker by design.

Use the hosted PWA at `https://guardain-api.onrender.com/pwa/` for the demo.
Do not double-click `pwa/index.html`: browsers give local files an opaque
origin, which the cloud API intentionally does not trust.

## Portal portion

1. Open `http://127.0.0.1:8080/` after stages 4 or 5.
2. Sign in with local demonstration credentials `admin` / `admin@26`.
3. Refresh the telemetry feed after about ten seconds. It shows the queued
   incident, URL origin, event time, decision score, screenshot status/hash,
   and enrichment when available.
4. Open **Domain Intelligence**. The local host is now an observation in the
   database. It is pending until an analyst explicitly marks it safe or
   malicious.
5. Explain that a domain observation is not a conviction. Only an authenticated
   analyst review can create a confirmed malicious-domain block.

## PWA triage-to-portal flow

1. Open `http://127.0.0.1:8080/pwa/` and check the green **Central server
   connected** status in the header.
2. Paste a fictional high-risk message such as: `CBI digital arrest notice:
   share OTP and UPI PIN now to avoid account freeze.` Then select **Analyse
   message**.
3. The PWA shows the risk explanation and immediately queues the high-risk
   triage result as a `pwa-triage` incident. It does not require a web URL,
   because a message/VPA report is a valid incident on its own.
4. Refresh the portal incident feed. The entry shows `pwa-triage`, the risk
   score, model/explanation metadata, and `url: null` for the message-only
   report.

Low-risk checks are deliberately not sent to the central feed. This keeps
routine personal messages on the device while preserving analyst visibility
for review/block-level fraud signals.

## What to say about the model and database

- **Database:** local demonstrations use SQLite; `health.database=true` means
  URL/domain observations and incidents are being persisted. Cloud deployment
  uses PostgreSQL so multiple laptops share the same database.
- **MuRIL:** the local exhibition setup runs a loaded MuRIL ONNX demonstration
  model plus explainable multilingual safety rules. Its training metadata is
  explicitly marked synthetic; do not claim its local validation score as
  real-world accuracy. Production needs independently labelled
  Hindi/Hinglish/English data, calibration, and held-out evaluation.
- **Privacy:** routine extension checks send structured domain/page facts, not
  arbitrary page text or typed form values. High-risk screenshots are limited
  to the visible tab and include a SHA-256 integrity hash.

## If a result differs

| Symptom | Check |
|---|---|
| Popup says connection failed | Keep the API terminal running; open `/health` directly |
| Page says safe-domain bypass | Do not test on Google, Bing, government, or configured news domains |
| No warning on a high-risk demo | Reload the extension, refresh the test tab, and ensure Page protection is enabled |
| Demo opened as a local file has no extension warning | Enable **Allow access to file URLs** in the extension Details page, or use the hosted `/demo/extension-test` URL |
| No portal incident | Keep the high-risk tab active until the warning appears; wait ten seconds and refresh the portal |
| PWA says central delivery failed | Start the API, refresh the PWA, and confirm its header says **Central server connected** |
| Screenshot missing | The page can still report metadata. Ensure the high-risk tab stayed visible during the warning |

## Responsible conclusion

GuardAIN is an academic prototype for analyst-assisted fraud prevention. It
does not assert government approval, legal certification, bank ownership
verification, or validated model accuracy. A public rollout additionally needs
real data governance, security review, role-based operator access, backups,
abuse controls, and a hosted HTTPS PostgreSQL deployment.
