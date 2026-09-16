# Project GaurdAIN — Real-Time Cyber Fraud & UPI Mule Defense

A standalone **Manifest V3 Chrome Extension** that acts as a client-side **Sensor**,
**Offline Heuristic Engine**, and **Intervention UI**. It runs fully autonomously with
**no backend / mock server dependency** — all detection happens on-device.

---

## Files

```
Project/
├── manifest.json                 # Chrome MV3 manifest (webNavigation, file:// support, 3 icons)
├── background.js                 # MV3 service worker — offline heuristic + hard block + 8s circuit breaker
├── content.js                    # Targeted DOM scanner + block overlay + 8s countdown
├── popup.html / popup.js         # Dashboard UI (protection status, offline indicator, heuristic toggle)
├── icon16.png / icon48.png / icon128.png   # Extension icons
├── scam.html                     # Dangerous test page (KYC/digital-arrest/UPI scam keywords)
└── safe.html                     # Benign test page (zero false positives)
```

---

## How It Works

- **Offline Heuristic Engine (`background.js`):** Classifies every page locally using
  keyword rules for scam vectors (KYC Blocked, Digital Arrest, Fake Investment, UPI
  Collect Requests, mule recruitment) plus WHOIS/domain-age signals. No network call.
- **Hard Blocking:** On a `high_risk` verdict:
  1. Fires a native Chrome notification showing the dangerous URL + reasons.
  2. Sends a `BLOCK_PAGE` message to `content.js`, which injects a **non-dismissable**
     full-screen overlay (`z-index: 2147483647`) covering the whole viewport.
  3. Shows an active **8-second circuit-breaker countdown**.
  4. After 8s, the tab is closed by the service worker.
- **Privacy-by-Design:** only `#main`, `.chat-content`, password/tel inputs and
  payment dialogs are scanned. PII is scrubbed locally and
  `[data-guardain-exempt]` subtrees are never collected.
- **Safe zones:** Google, Bing, DuckDuckGo, The Hindu, Times of India,
  `.gov.in`, and `.nic.in` set `sessionStorage.guardain_bypass_active` and bypass scanning.

---

## Test It (no server — just open the file)

1. Open `chrome://extensions` → enable **Developer mode** → **Load unpacked** → select this
   folder.
2. On the extension card, click **Details** and enable **"Allow access to file URLs"**.
3. Double-click **`scam.html`** in this folder to open it in Chrome.
   → You'll see a native notification, then a red block overlay with an **8-second
   circuit-breaker countdown**, and the tab auto-closes.
4. Double-click **`safe.html`** → you'll see a green **"✓ Looks safe"** badge and normal
   rendering (no false positive).

> **Troubleshooting:** After editing any file, reload the extension in
> `chrome://extensions`. If scanning doesn't start, confirm "Allow access to file URLs"
> is enabled and the heuristic toggle in the popup is ON.
