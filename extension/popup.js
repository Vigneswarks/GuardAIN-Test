// GuardAIN popup — renders the latest local verdict without network calls.

const LABELS = {
  safe: "Looks safe",
  suspicious: "Suspicious signals",
  high_risk: "High risk — be careful",
  unknown: "Not scanned yet"
};

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

(async () => {
  try {
    await render();
    await setupToggle();
  } catch (error) {
    console.error("[GuardAIN popup]", error);
  }
})();
