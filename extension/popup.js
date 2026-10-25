// GuardAIN popup — renders the latest local verdict without network calls.

const LABELS = {
  safe: "Looks safe",
  suspicious: "Suspicious signals",
  high_risk: "High risk — be careful",
  unknown: "Not scanned yet"
};

const SAFE_ZONES = [
  "google.com", "google.co.in", "bing.com", "duckduckgo.com", "thehindu.com",
  "timesofindia.indiatimes.com", "gov.in", "nic.in"
];

function isSafeZone(host) {
  const value = String(host || "").toLowerCase().replace(/\.$/, "");
  return SAFE_ZONES.some(domain => value === domain || value.endsWith(`.${domain}`));
}

function addText(parent, tag, text, className) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  el.textContent = String(text ?? "");
  parent.appendChild(el);
  return el;
}

async function render() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) return;

  const dot = document.getElementById("dot");
  const label = document.getElementById("label");
  const hostEl = document.getElementById("host");
  const details = document.getElementById("details");

  let host = "";
  try { host = new URL(tab.url || "").hostname; } catch { host = tab.url || ""; }
  hostEl.textContent = host;

  const key = `verdict:${tab.id}`;
  const stored = await chrome.storage.session.get(key);
  const verdict = stored[key];

  details.replaceChildren();

  // Safe domains never send content, screenshots, URLs, or page signals to
  // GuardAIN. Show that intentional state instead of a confusing "unknown".
  if (isSafeZone(host)) {
    dot.className = "dot safe";
    label.textContent = "Safe-domain bypass";
    addText(details, "div", "GuardAIN intentionally does not scan, report, block, or close this configured safe domain.");
    const indicator = document.getElementById("offlineIndicator");
    indicator.textContent = "◉ Safe-domain privacy bypass";
    indicator.className = "mode online";
    return;
  }

  if (!verdict) {
    dot.className = "dot";
    label.textContent = LABELS.unknown;
    addText(details, "div", "This page has not been scanned yet, or no page signal is available.");
    const indicator = document.getElementById("offlineIndicator");
    indicator.textContent = "◉ Status unknown";
    indicator.className = "mode";
    return;
  }

  dot.className = `dot ${verdict.risk_level || ""}`;
  label.textContent = LABELS[verdict.risk_level] || "Unknown result";
  addText(details, "div", `Threat score: ${Math.round((verdict.threat_score || 0) * 100)}%`);
  addText(details, "div", `Source: ${verdict.tier || "n/a"}`);

  if (Array.isArray(verdict.reasons) && verdict.reasons.length) {
    const reasons = document.createElement("div");
    reasons.className = "reasons";
    verdict.reasons.forEach(r => addText(reasons, "span", String(r).replace(/_/g, " ")));
    details.appendChild(reasons);
  }

  const indicator = document.getElementById("offlineIndicator");
  indicator.textContent =
    verdict.tier === "offline_disabled"
      ? "◉ Local heuristic engine disabled"
      : "◉ Local-first protection active";
  indicator.className = "mode offline";
}

async function setupToggle() {
  const toggle = document.getElementById("heuristicToggle");
  const stored = await chrome.storage.local.get({ heuristic_enabled: true });
  toggle.checked = stored.heuristic_enabled !== false;
  toggle.addEventListener("change", async () => {
    await chrome.storage.local.set({ heuristic_enabled: toggle.checked });
    await render();
  });
}

async function analyzeMessage() {
  const input = document.getElementById("messageInput");
  const result = document.getElementById("messageResult");
  const message = input.value.trim();
  if (!message) {
    result.textContent = "Paste a message to analyze.";
    return;
  }
  result.textContent = "Analyzing...";
  try {
    const stored = await chrome.storage.local.get({ guardainApiBaseUrl: "https://guardain-api.onrender.com" });
    const response = await fetch(`${String(stored.guardainApiBaseUrl).replace(/\/+$/, "")}/v1/analyzer/message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const patterns = (data.message_breakdown?.patterns || []).map(pattern => pattern.replace(/_/g, " ")).join(", ");
    result.textContent = `${String(data.risk_level || "unknown").toUpperCase()} (${Math.round((data.score || 0) * 100)}%). ${patterns || "No known scam pattern matched."}`;
  } catch (error) {
    result.textContent = `Message analysis unavailable: ${error.message}`;
  }
}

async function setupApiBase() {
  const input = document.getElementById("apiBaseInput");
  const status = document.getElementById("apiBaseStatus");
  const stored = await chrome.storage.local.get({ guardainApiBaseUrl: "https://guardain-api.onrender.com" });
  input.value = stored.guardainApiBaseUrl;
  const report = await chrome.storage.local.get('guardainReportStatus');
  status.textContent = report.guardainReportStatus || 'No reports sent yet';
  document.getElementById("saveApiBase").addEventListener("click", async () => {
    const value = input.value.trim().replace(/\/+$/, "");
    const privateLan = /^http:\/\/(localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(:\d+)?$/i;
    if (!/^https:\/\//i.test(value) && !privateLan.test(value)) {
      status.textContent = "Use HTTPS, or a private-LAN HTTP address for testing.";
      status.className = "mode offline";
      return;
    }
    // Save first. chrome.storage.local survives browser restarts and service
    // worker restarts, so a temporarily offline server never forces the user
    // to type the URL again.
    await chrome.storage.local.set({ guardainApiBaseUrl: value, guardainApiConfigured: true });
    status.textContent = "Saved locally. Testing central server...";
    try {
      const response = await fetch(`${value}/health`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const health = await response.json();
      if (health.status !== "online") throw new Error("Unexpected health response");
      status.textContent = `Connected · ${health.inference?.engine || "server online"}`;
      status.className = "mode online";
    } catch (error) {
      status.textContent = `Saved locally; connection failed: ${error.message}`;
      status.className = "mode offline";
    }
  });
}

(async () => {
  try {
    await render();
    await setupToggle();
    await setupApiBase();
    document.getElementById("messageCheck").addEventListener("click", analyzeMessage);
  } catch (error) {
    console.error("[GuardAIN popup]", error);
  }
})();
