/* GuardAIN content scanner: narrow, privacy-first DOM collection. */
let warningShown = false;
let scanTimer = null;
let observer;

const SAFE_ZONES = [
  "google.com", "bing.com", "duckduckgo.com", "thehindu.com",
  "timesofindia.indiatimes.com", "gov.in", "nic.in"
];

function isSafeZone(host = location.hostname) {
  const normalized = host.toLowerCase().replace(/^www\./, "");
  return SAFE_ZONES.some(domain => normalized === domain || normalized.endsWith(`.${domain}`));
}

function markBypass(active) {
  try {
    if (active) {
      sessionStorage.setItem("guardain_bypass_active", "true");
      document.documentElement?.setAttribute("data-guardain-exempt", "true");
    }
  } catch (_) { /* restricted documents may deny sessionStorage */ }
}

function bypassActive() {
  if (document.documentElement?.getAttribute("data-guardain-exempt") === "true") return true;
  try {
    return sessionStorage.getItem("guardain_bypass_active") === "true";
  } catch (_) {
    return false;
  }
}

function exempt(element) {
  return bypassActive() || element.closest?.("[data-guardain-exempt]") != null;
}

function redactPII(value) {
  return String(value || "")
    .replace(/(?<!\d)(?:\+?91[\s.-]?)?[6-9]\d{4}[\s.-]?\d{5}(?!\d)/g, "[PHONE]")
    .replace(/(?<!\d)(?:\d{4}[\s-]?){2}\d{4}(?!\d)/g, "[AADHAAR]")
    .replace(/(?<!\d)(?:\d[ -]?){13,19}(?!\d)/g, "[CARD]");
}

function scopedText() {
  const selectors = [
    "#main", ".chat-content", "input[type='password']", "input[type='tel']",
    "[role='dialog'][aria-label*='pay' i]", "[role='dialog'][class*='payment' i]",
    ".payment-modal", "#payment-modal"
  ];
  const roots = selectors.flatMap(selector => [...document.querySelectorAll(selector)]);
  const unique = [...new Set(roots)].filter(node => !exempt(node));
  return unique.map(node => node.value || node.innerText || node.textContent || "")
    .join("\n").slice(0, 5000);
}

function getPageSignal() {
  const text = redactPII(scopedText());
  return {
    url_host: location.hostname,
    url_path: location.pathname,
    url: location.href.slice(0, 500),
    title: document.title || "",
    text_sample: text,
    has_password: Boolean(document.querySelector("input[type='password']")),
    has_payment: Boolean(document.querySelector(".payment-modal,#payment-modal,[role='dialog'][aria-label*='pay' i]")),
    upi_links: [...document.querySelectorAll("a[href^='upi://']:not([data-guardain-exempt])")]
      .slice(0, 20).map(a => a.getAttribute("href")?.slice(0, 200)).filter(Boolean),
    ts: Date.now()
  };
}

function scanPage() {
  clearTimeout(scanTimer);
  if (bypassActive()) return;
  if (isSafeZone()) {
    markBypass(true);
    observer?.disconnect();
    return;
  }
  try {
    if (Number(sessionStorage.getItem("guardain_circuit_open_until") || 0) > Date.now()) return;
  } catch (_) {}
  scanTimer = setTimeout(() => {
    if (!bypassActive() && scopedText()) {
      chrome.runtime.sendMessage({ type: "PAGE_SIGNAL", payload: getPageSignal() }).catch(() => {});
    }
  }, 500);
}

scanPage();
if (document.body) {
  observer = new MutationObserver(scanPage);
  observer.observe(document.body, { childList: true, subtree: true, characterData: true });
}

chrome.runtime.onMessage.addListener(message => {
  if (message?.type === "REQUEST_SCAN") scanPage();
  if (message?.type === "BLOCK_PAGE") showWarning(message.payload || {});
  if (message?.type === "SCAN_RESULT") {
    const verdict = message.payload || {};
    showBadge(verdict.risk_level === "suspicious" ? "⚠ Suspicious signals" : "✓ Looks safe");
  }
});

function showBadge(text) {
  let badge = document.getElementById("guardain-badge");
  if (!badge) {
    badge = document.createElement("div");
    badge.id = "guardain-badge";
    Object.assign(badge.style, { position: "fixed", top: "12px", right: "12px", zIndex: "2147483646",
      padding: "7px 12px", borderRadius: "20px", background: "#111827", color: "#fff",
      font: "600 12px Arial", boxShadow: "0 2px 10px #0005" });
    document.documentElement.appendChild(badge);
  }
  badge.textContent = text;
}

function showWarning(data) {
  if (warningShown || bypassActive()) return;
  warningShown = true;
  try { sessionStorage.setItem("guardain_circuit_open_until", String(Date.now() + 8000)); } catch (_) {}
  const overlay = document.createElement("div");
  overlay.id = "guardain-warning";
  Object.assign(overlay.style, { position: "fixed", inset: "0", zIndex: "2147483647",
    background: "rgba(0,0,0,.82)", display: "flex", alignItems: "center",
    justifyContent: "center", fontFamily: "Arial,sans-serif" });
  const box = document.createElement("div");
  Object.assign(box.style, { width: "min(500px,90%)", padding: "28px", background: "#17171c",
    color: "#fff", borderRadius: "16px", textAlign: "center" });
  const score = Math.round(Number(data.threat_score || 0) * 100);
  box.innerHTML = `<h2>⚠️ GuardAIN Security Warning</h2>
    <p>Potentially dangerous content detected on <b>${escapeHtml(location.hostname)}</b>.</p>
    <p>Threat score: <strong>${score}%</strong></p>
    <p>${(data.reasons || ["Potential fraud detected"]).map(reason =>
      `<span style="display:inline-block;margin:3px;padding:5px 9px;background:#35191d;border-radius:15px">${escapeHtml(String(reason))}</span>`).join("")}</p>
    <p id="guardain-countdown">Circuit breaker closes this tab in 8 seconds.</p>
    <button id="guardain-back">Go back</button>
    <button id="guardain-proceed">Proceed anyway</button>`;
  overlay.appendChild(box);
  document.documentElement.appendChild(overlay);
  let cancelled = false;
  document.getElementById("guardain-back").onclick = () => { cancelled = true; history.back(); };
  document.getElementById("guardain-proceed").onclick = () => {
    cancelled = true;
    markBypass(true);
    overlay.remove();
    warningShown = false;
    observer?.disconnect();
  };
  let seconds = 8;
  const timer = setInterval(() => {
    if (cancelled) return clearInterval(timer);
    seconds -= 1;
    const counter = document.getElementById("guardain-countdown");
    if (counter) counter.textContent = `Circuit breaker closes this tab in ${seconds} seconds.`;
    if (seconds <= 0) { clearInterval(timer); chrome.runtime.sendMessage({ type: "AUTO_CLOSE_WARNING_TAB" }).catch(() => {}); }
  }, 1000);
}

function escapeHtml(value) {
  return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
