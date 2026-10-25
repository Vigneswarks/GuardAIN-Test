# GuardAIN Chrome extension: install and troubleshoot

## Install

1. The production extension defaults to `https://guardain-api.onrender.com`.
   For a local API, start it first (`docker compose up --build` or
   `./start.ps1`) and override the endpoint in the popup.
2. Open `chrome://extensions`.
3. Turn on **Developer mode**.
4. Select **Load unpacked** and choose this `extension` folder itself, not the
   project root and not a ZIP file.
5. Open the GuardAIN extension popup. The deployed central server is filled in
   automatically. Select **Save and test connection**; use
   `http://127.0.0.1:8080` only for same-laptop testing.
6. Select **Save and test connection**. It must say `Connected`.

## If Chrome displays an extension error

1. In `chrome://extensions`, click the circular **Reload** button on GuardAIN.
2. Click **Errors**. If an error remains, copy its complete text and the line
   number before changing settings.
3. Click **service worker** under GuardAIN to open its console. A cloud URL
   failure means the backend is unavailable or its CORS list does not include
   the portal origin; it does not mean Chrome cannot load the extension.
4. Do not expect the extension to operate on `chrome://`, Chrome Web Store,
   browser settings, PDF viewer pages, or other browser-restricted pages.
5. Reload the tested web tab after reloading the extension.

## Safe test

Start the API, configure the popup with `http://127.0.0.1:8080`, then open
`http://127.0.0.1:8080/demo/extension-test`. This bundled, controlled page has
the corroborated signals required for a warning. Do not use Google AI Studio
or any other `google.com` subdomain for testing: safe-domain bypass means it
will intentionally never scan or report those pages.

The extension intentionally does not block a page just because it mentions
"digital arrest". A block needs either an analyst-reviewed malicious domain or
corroborated page facts: coercive/urgent payment or credential demand plus a
credential/payment form plus an insecure or cross-origin form destination.

## What the popup status means

- **Connected**: the API `/health` endpoint answered.
- **Status unknown**: the page was not eligible for scanning, was just opened,
  or Chrome blocked content scripts on that page.
- **Server unavailable — unverified**: a non-safe page sent a privacy-limited
  hostname/signal check but the backend could not be reached. It is not blocked
  automatically unless it has the same corroborated high-risk page facts that
  the central policy requires. In that case GuardAIN warns locally and queues
  the report for later delivery.
- **Report queued**: a warning incident is stored locally and will retry every
  minute. A screenshot is captured only for the visible, unchanged warning tab.
