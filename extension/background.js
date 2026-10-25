// GuardAIN MV3 service worker
// Local-first fraud detection
// High-risk warning -> content.js -> 8s countdown -> AUTO_CLOSE_WARNING_TAB

// Public production endpoint. It can be overridden in the popup for local or
// private-network development without changing the shared cloud destination.
const DEFAULT_API_BASE = "https://guardain-api.onrender.com";
const LEGACY_LOCAL_API_BASE = "http://127.0.0.1:8080";
const SAFE_ZONES = ['google.com', 'google.co.in', 'bing.com', 'duckduckgo.com', 'thehindu.com', 'timesofindia.indiatimes.com', 'gov.in', 'nic.in'];
function isGuardainSafeZone(host) {
  const value = String(host || '').toLowerCase().replace(/\.$/, '');
  return SAFE_ZONES.some(domain => value === domain || value.endsWith(`.${domain}`));
}

async function reportWarning(message, sender, captured = () => {}) {
  if (!sender.tab || sender.frameId !== 0) return;
  let host = '';
  try { host = new URL(sender.tab.url || '').hostname; } catch (_) { return; }
  if (isGuardainSafeZone(host)) return;
  const stored = await chrome.storage.session.get(`verdict:${sender.tab.id}`);
  const verdict = stored[`verdict:${sender.tab.id}`];
  if (verdict?.risk_level !== 'high_risk' || verdict.host !== host) return;
  const payload = {
    client_report_id: crypto.randomUUID(), url: `https://${host}/`,
    threat_score: verdict.threat_score, source: 'extension',
    browser: {evidence_status: 'metadata_only'},
    dom_snapshot: JSON.stringify({reasons: verdict.reasons})
  };
  // Chrome captures the visible tab, not an arbitrary tab ID. Check both
  // sides of capture and discard evidence if focus/navigation changed.
  try {
    const [before] = await chrome.tabs.query({active: true, windowId: sender.tab.windowId});
    if (before?.id !== sender.tab.id || before.url !== sender.tab.url) throw new Error('Tab not visible');
    const dataUrl = await chrome.tabs.captureVisibleTab(sender.tab.windowId, {format: 'png'});
    const [after] = await chrome.tabs.query({active: true, windowId: sender.tab.windowId});
    if (after?.id !== sender.tab.id || after.url !== sender.tab.url) throw new Error('Tab changed');
    if (dataUrl.length > 3500000) throw new Error('Screenshot exceeds local queue budget');
    const bytes = Uint8Array.from(atob(dataUrl.split(',')[1]), c => c.charCodeAt(0));
    payload.screenshot_base64 = dataUrl;
    payload.screenshot_hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), b => b.toString(16).padStart(2, '0')).join('');
    payload.browser.evidence_status = 'visible_tab_screenshot';
  } catch (error) { payload.browser.evidence_status = `screenshot_unavailable: ${error.message}`; }
  captured({captured: Boolean(payload.screenshot_base64)});
  const base = await apiBase();
  const key = `pending-report:${payload.client_report_id}`;
  const all = await chrome.storage.local.get(null);
  if (Object.keys(all).filter(k => k.startsWith('pending-report:')).length >= 2) {
    // Preserve an incident even when the evidence queue is full.
    delete payload.screenshot_base64;
    delete payload.screenshot_hash;
    payload.browser.evidence_status = 'screenshot_omitted_queue_capacity';
  }
  if (Object.keys(all).filter(k => k.startsWith('pending-report:')).length >= 50) {
    await chrome.storage.local.set({guardainReportStatus: 'Report queue full; connect to central server'});
    return;
  }
  await chrome.storage.local.set({[key]: {base, payload}, guardainReportStatus: 'Report queued'});
  await flushReports();
}

let flushing = false;
async function flushReports() {
  if (flushing) return;
  flushing = true;
  try {
    const items = await chrome.storage.local.get(null);
    for (const [key, item] of Object.entries(items)) {
      if (!key.startsWith('pending-report:')) continue;
      if (isGuardainSafeZone(new URL(item.payload.url).hostname)) {
        await chrome.storage.local.remove(key);
        continue;
      }
      try {
        const response = await fetch(`${item.base}/v1/telemetry`, {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(item.payload), signal: AbortSignal.timeout(8000)
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        await chrome.storage.local.remove(key);
        await chrome.storage.local.set({guardainReportStatus: 'Report delivered'});
      } catch (error) {
        await chrome.storage.local.set({guardainReportStatus: `Queued for retry: ${error.message}`});
      }
    }
  } finally { flushing = false; }
}
chrome.alarms.create('guardain-report-retry', {periodInMinutes: 1});
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === 'guardain-report-retry') flushReports(); });

async function apiBase() {
  const stored = await chrome.storage.local.get({ guardainApiBaseUrl: DEFAULT_API_BASE });
  return String(stored.guardainApiBaseUrl || DEFAULT_API_BASE).replace(/\/+$/, "");
}

async function migrateCentralEndpoint() {
  const stored = await chrome.storage.local.get({
    guardainApiBaseUrl: "",
    guardainApiConfigured: false,
  });
  // Migrate only the earlier implicit localhost default. A URL saved by an
  // operator remains untouched.
  if (!stored.guardainApiConfigured && (!stored.guardainApiBaseUrl || stored.guardainApiBaseUrl === LEGACY_LOCAL_API_BASE)) {
    await chrome.storage.local.set({ guardainApiBaseUrl: DEFAULT_API_BASE });
  }
}

if (chrome.runtime.onInstalled) chrome.runtime.onInstalled.addListener(() => { void migrateCentralEndpoint(); });
if (chrome.runtime.onStartup) chrome.runtime.onStartup.addListener(() => { void migrateCentralEndpoint(); });
void migrateCentralEndpoint();


function offlineClassify(signal = {}) {
  // Offline protection is deliberately structural, not keyword-only. This
  // mirrors the server policy so an unreachable API cannot disable safety on
  // a coercive page with a credential/payment collection form and unsafe form
  // destination. All other pages remain unverified rather than blocked.
  const facts = signal.signals || {};
  const collection = Boolean(facts.credential_form || facts.payment_request);
  const coercion = Boolean(facts.coercion && facts.urgent_demand);
  const unsafeDestination = Boolean(facts.insecure_form || facts.cross_origin_form);
  if (collection && coercion && unsafeDestination) {
    return {
      risk_level: "high_risk", threat_score: 0.92,
      reasons: ["coercive_demand", "collection_form", "unsafe_form_destination"],
      tier: "local-corroborated-policy", host: signal.url_host || ""
    };
  }
  if (collection && (coercion || unsafeDestination)) {
    return {
      risk_level: "suspicious", threat_score: 0.6, reasons: ["corroborated_warning"],
      tier: "local-corroborated-policy", host: signal.url_host || ""
    };
  }
  return {risk_level: "unknown", threat_score: 0, reasons: ["insufficient_blocking_evidence"], tier: "awaiting_central_policy", host: signal.url_host || ""};
}

async function cloudClassify(signal, localVerdict) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 4500);
  try {
    const base = await apiBase();
    const host = String(signal.url_host || "").toLowerCase();
    const response = await fetch(`${base}/v1/page-check`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        domain: host,
        signals: signal.signals || {}
      }),
      signal: controller.signal
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    const score = Number(result.threat_score ?? result.score ?? 0);
    return {
      risk_level: result.action === "BLOCK" ? "high_risk" : result.action === "REVIEW" ? "suspicious" : "safe",
      threat_score: score,
      reasons: result.reasons || [],
      tier: result.engine || "central_muril",
      host
    };
  } finally {
    clearTimeout(timeout);
  }
}

// ------------------------------------------------------------
// SCAN
// ------------------------------------------------------------

async function scanSignal(
  signal,
  tabId
) {

  if (!signal || tabId == null || !signal.url_host) {
    return;
  }
  if (isGuardainSafeZone(signal.url_host)) {
    await applyVerdict({risk_level: "safe", threat_score: 0, reasons: ["safe_zone_bypass"], tier: "safe_zone_bypass", host: signal.url_host}, tabId);
    return;
  }

  const {
    heuristic_enabled = true
  } = await chrome.storage.local.get({
    heuristic_enabled: true
  });

  // Local detection disabled
  if (!heuristic_enabled) {

    await applyVerdict(
      {
        risk_level: "unknown",
        threat_score: 0,
        reasons: [
          "page_protection_disabled"
        ],
        tier: "offline_disabled",
        host: signal.url_host || ""
      },
      tabId
    );

    return;
  }


  // Central verification receives only the hostname and local risk labels;
  // paths, query strings, and arbitrary private page text stay on-device.
  const localVerdict = offlineClassify(signal);
  let verdict = localVerdict;
  try {
    const cloudVerdict = await cloudClassify(signal, localVerdict);
    verdict = cloudVerdict;
  } catch (error) {
    verdict = {...localVerdict, tier: `${localVerdict.tier}+cloud_unavailable`};
    console.warn("[GuardAIN] central verification unavailable:", error);
  }
  verdict.documentUrl = signal.url;
  try {
    const currentTab = await chrome.tabs.get(tabId);
    if (currentTab.url !== signal.url) return;
  } catch (_) { return; }


  await applyVerdict(
    verdict,
    tabId
  );
}

// ------------------------------------------------------------
// APPLY VERDICT
// ------------------------------------------------------------

async function applyVerdict(
  verdict,
  tabId
) {

  const risk =
    verdict?.risk_level ||
    "safe";

  const badgeMap = {

    safe: {
      text: "",
      color: "#00000000"
    },

    suspicious: {
      text: "!",
      color: "#F5A623"
    },

    high_risk: {
      text: "!!",
      color: "#D0021B"
    }
  };

  const badge =
    badgeMap[risk] ||
    badgeMap.safe;

  // Badge
  chrome.action
    .setBadgeText({
      text: badge.text,
      tabId
    })
    .catch(() => {});

  chrome.action
    .setBadgeBackgroundColor({
      color: badge.color,
      tabId
    })
    .catch(() => {});

  // Store verdict
  try {
    // Persist before notifying content.js. The immediate report/capture path
    // reads this same verdict to prevent unverified screenshots and closures.
    await chrome.storage.session.set({
      [`verdict:${tabId}`]: {
        ...verdict,
        scannedAt: Date.now()
      }
    });
  } catch (_) { return; }

  // Send scan result
  await chrome.tabs
    .sendMessage(
      tabId,
      {
        type: "SCAN_RESULT",
        payload: {
          ...verdict
        }
      }
    )
    .catch(() => {});

  // ----------------------------------------------------------
  // HIGH RISK
  // ----------------------------------------------------------

  if (risk === "high_risk") {

    chrome.tabs.update(tabId, { muted: true }).catch(() => {});

    const reasons =
      (verdict.reasons || [])
        .join(", ") ||
      "strong signs of fraud";

    // Browser notification
    chrome.notifications
      .create({
        type: "basic",
        iconUrl: "icon128.png",
        title:
          "GuardAIN: Dangerous site detected",
        message:
          `Risk ${
            Math.round(
              (verdict.threat_score || 0) *
              100
            )
          }%. ${reasons}.`,
        priority: 2
      })
      .catch(() => {});

    // Show warning overlay
    chrome.tabs
      .sendMessage(
        tabId,
        {
          type: "BLOCK_PAGE",
          payload: {
            risk_level: risk,
            threat_score:
              verdict.threat_score || 0,
            host:
              verdict.host || "",
            reasons:
              verdict.reasons || []
          }
        }
      )
      .catch(() => {});
  }
}

// ------------------------------------------------------------
// MESSAGE HANDLER
// ------------------------------------------------------------

chrome.runtime.onMessage.addListener(
  (message, sender, sendResponse) => {
    if (message?.type === 'CANCEL_WARNING' && sender.tab) {
      chrome.storage.session.remove(`verdict:${sender.tab.id}`);
      chrome.tabs.update(sender.tab.id, {muted: false}).catch(() => {});
      return false;
    }
    if (message?.action === "capture_tab") {
      reportWarning(message, sender, sendResponse).catch(error => {
        console.warn('[GuardAIN] report failed:', error);
        sendResponse({captured: false});
      });
      return true;
    }

    // Page scan
    if (
      message?.type ===
      "PAGE_SIGNAL"
    ) {

      const tabId =
        sender.tab?.id;

      if (tabId == null) {
        return false;
      }

      scanSignal(
        {...message.payload, url: sender.tab.url, url_host: new URL(sender.tab.url).hostname},
        tabId
      ).catch(error => {
        console.warn(
          "[GuardAIN] scan failed:",
          error
        );
      });

      return false;
    }

    // --------------------------------------------------------
    // 8 SECOND AUTO CLOSE
    // --------------------------------------------------------

    if (
      message?.type ===
      "AUTO_CLOSE_WARNING_TAB"
    ) {

      const tabId =
        sender.tab?.id;

      if (tabId != null) {
        chrome.storage.session.get(`verdict:${tabId}`).then(async stored => {
          const verdict = stored[`verdict:${tabId}`];
          const tab = await chrome.tabs.get(tabId);
          const host = new URL(tab.url).hostname;
          if (verdict?.risk_level === "high_risk" && verdict.host === host &&
              verdict.documentUrl === tab.url &&
              !isGuardainSafeZone(host) && Date.now() - verdict.scannedAt >= 7500 &&
              Date.now() - verdict.scannedAt < 60000 && tab.url === sender.tab.url) {
            await chrome.tabs.remove(tabId);
          }
        }).catch(console.warn);
      }

      return false;
    }

    // --------------------------------------------------------
    // Legacy CLOSE_TAB
    // --------------------------------------------------------

    if (
      message?.type ===
      "CLOSE_TAB"
    ) {

      // Ignore old messages.
      // Only the new 8-second countdown
      // can request automatic closing.

      console.info(
        "[GuardAIN] Ignoring legacy CLOSE_TAB request."
      );

      return false;
    }

    return false;
  }
);

// ------------------------------------------------------------
// NAVIGATION SCAN
// ------------------------------------------------------------

chrome.webNavigation.onCommitted.addListener(
  details => {

    if (
      details.frameType !==
      "outermost_frame"
    ) {
      return;
    }

    chrome.tabs
      .sendMessage(
        details.tabId,
        {
          type: "REQUEST_SCAN"
        }
      )
      .catch(() => {});
  }
);

// ------------------------------------------------------------
// TAB CLEANUP
// ------------------------------------------------------------

chrome.tabs.onRemoved.addListener(
  tabId => {


    chrome.storage.session
      .remove(
        `verdict:${tabId}`
      )
      .catch(() => {});
  }
);

// ------------------------------------------------------------
// INSTALL
// ------------------------------------------------------------

chrome.runtime.onInstalled.addListener(
  () => {

    console.log(
      "[GuardAIN] Extension installed."
    );

    console.log(
      "[GuardAIN] Local-first protection ready."
    );

    console.log(
      "[GuardAIN] High-risk pages will show a warning."
    );

    console.log(
      "[GuardAIN] Warning countdown can request tab closure after 8 seconds."
    );
  }
);
