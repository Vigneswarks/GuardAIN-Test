/* GuardAIN content scanner: narrow, privacy-first DOM collection. */
let warningShown = false;
let scanTimer = null;
let userBypass = false;
const scopeObservers = new Map();

const SAFE_ZONES = [
  "google.com", "google.co.in", "bing.com", "duckduckgo.com", "thehindu.com",
  "timesofindia.indiatimes.com", "gov.in", "nic.in"
];

function isSafeZone(host = location.hostname) {
  const normalized = host.toLowerCase().replace(/\.$/, "");
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
  return userBypass || isSafeZone();
}

function exempt(element) {
  return bypassActive();
}

function redactPII(value) {
  return String(value || "")
    .replace(/(?<!\d)(?:\+?91[\s.-]?)?[6-9]\d{4}[\s.-]?\d{5}(?!\d)/g, "[PHONE]")
    .replace(/(?<!\d)(?:\d{4}[\s-]?){2}\d{4}(?!\d)/g, "[AADHAAR]")
    .replace(/(?<!\d)(?:\d[ -]?){13,19}(?!\d)/g, "[CARD]");
}

function scopedText() {
  const selectors = [
    "main", "form",
    "#main", ".chat-content", "input[type='password']", "input[type='tel']",
    "[role='dialog'][aria-label*='pay' i]", "[role='dialog'][class*='payment' i]",
    ".payment-modal", "#payment-modal"
  ];
  const roots = selectors.flatMap(selector => [...document.querySelectorAll(selector)]);
  const unique = [...new Set(roots)].filter(node => !exempt(node));
  return unique.filter(node => !node.matches("input,textarea,select"))
    .map(node => node.innerText || node.textContent || "")
    .join("\n").slice(0, 5000);
}

function getPageSignal() {
  const text = redactPII(scopedText());
  const forms = [...document.forms];
  const credential = Boolean(document.querySelector("input[type='password']"));
  const payment = Boolean(document.querySelector("a[href^='upi://'],.payment-modal,#payment-modal"));
  const relevantForms = forms.filter(form => form.querySelector("input[type='password'],input[autocomplete='cc-number']"));
  const insecure = relevantForms.some(form => { try { return new URL(form.action || location.href, location.href).protocol === "http:"; } catch { return false; } });
  const crossOrigin = relevantForms.some(form => { try { return new URL(form.action || location.href, location.href).origin !== location.origin; } catch { return false; } });
  return {
    signals: {
      credential_form: credential, payment_request: payment,
      coercion: /(?:digital arrest|arrest warrant|pay bail|account will be blocked|गिरफ्तार)/i.test(text),
      urgent_demand: /(?:pay now|transfer.*immediately|send.*otp|enter.*password|तुरंत.*पैसे)/i.test(text),
      insecure_form: insecure, cross_origin_form: crossOrigin
    },
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

function scopedNodes() {
  const selectors = [
    "main", "form",
    "#main", ".chat-content", "input[type='password']", "input[type='tel']",
    "[role='dialog'][aria-label*='pay' i]", "[role='dialog'][class*='payment' i]",
    ".payment-modal", "#payment-modal"
  ];
  return [...new Set(selectors.flatMap(selector => [...document.querySelectorAll(selector)]))]
    .filter(node => !exempt(node));
}

function bindScopedObservers() {
  for (const [node, observer] of scopeObservers) {
    if (!node.isConnected || exempt(node)) {
      observer.disconnect();
      scopeObservers.delete(node);
    }
  }
  for (const node of scopedNodes()) {
    if (scopeObservers.has(node)) continue;
    const observer = new MutationObserver(scanPage);
    observer.observe(node, { childList: true, subtree: true, characterData: true, attributes: true });
    scopeObservers.set(node, observer);
  }
}

function scanPage() {
  clearTimeout(scanTimer);
  if (warningShown) return;
  if (bypassActive()) return;
  if (isSafeZone()) {
    markBypass(true);
    for (const observer of scopeObservers.values()) observer.disconnect();
    scopeObservers.clear();
    return;
  }
  bindScopedObservers();
  try {
    if (Number(sessionStorage.getItem("guardain_circuit_open_until") || 0) > Date.now()) return;
  } catch (_) {}
  scanTimer = setTimeout(() => {
    if (!bypassActive()) {
      chrome.runtime.sendMessage({ type: "PAGE_SIGNAL", payload: getPageSignal() }).catch(() => {});
    }
  }, 500);
}

scanPage();
// Discover forms inserted after initial page load without scanning input values.
setInterval(scanPage, 15000);

chrome.runtime.onMessage.addListener(message => {
  if (message?.type === "REQUEST_SCAN") scanPage();
  if (message?.type === "BLOCK_PAGE") {
    showWarning(message.payload || {}).catch(error => {
      warningShown = false;
      console.warn("[GuardAIN] warning UI failed:", error);
    });
  }
  if (message?.type === "SCAN_RESULT") {
    const verdict = message.payload || {};
    if (!isSafeZone()) showBadge(verdict.risk_level === "high_risk" ? "High risk" : verdict.risk_level === "suspicious" ? "Review recommended" : verdict.risk_level === "unknown" ? "Server unavailable — unverified" : "No blocking evidence");
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

async function showWarning(data) {
  if (warningShown || bypassActive()) return;
  warningShown = true;
  const frozenElements = [...document.querySelectorAll("input, textarea, select, button")];
  const priorDisabled = new Map(frozenElements.map(element => [element, element.disabled]));
  frozenElements.forEach(element => {
    element.setAttribute("data-guardain-frozen", "true");
    element.disabled = true;
  });
  const domSnapshot = JSON.stringify({signals: getPageSignal().signals});
  const telemetry = {
    url: `${location.origin}/`,
    clean_url: `${location.origin}/`,
    dom_snapshot: domSnapshot,
    browser: { userAgent: navigator.userAgent, language: navigator.language }
  };
  // Capture before the warning covers the page. Bound the wait so protection
  // does not depend on screenshot or network availability.
  await Promise.race([
    chrome.runtime.sendMessage({action: 'capture_tab', telemetry}).catch(() => {}),
    new Promise(resolve => setTimeout(resolve, 1500))
  ]);
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
  document.getElementById("guardain-back").onclick = () => { cancelled = true; location.replace("about:blank"); };
  document.getElementById("guardain-proceed").onclick = () => {
    cancelled = true;
    userBypass = true;
    chrome.runtime.sendMessage({type: 'CANCEL_WARNING'}).catch(() => {});
    markBypass(true);
    frozenElements.forEach(element => {
      if (element.isConnected) {
        element.disabled = priorDisabled.get(element);
        element.removeAttribute("data-guardain-frozen");
      }
    });
    overlay.remove();
    warningShown = false;
    for (const observer of scopeObservers.values()) observer.disconnect();
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
