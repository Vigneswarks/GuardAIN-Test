// GuardAIN MV3 service worker
// Local-first fraud detection
// High-risk warning -> content.js -> 8s countdown -> AUTO_CLOSE_WARNING_TAB

const tier0Cache = new Map();
const TIER0_TTL_MS = 5 * 60 * 1000;

// ------------------------------------------------------------
// CACHE
// ------------------------------------------------------------

function cacheKey(host, path) {
  return `${host || "<file>"}${path || "/"}`;
}

// ------------------------------------------------------------
// OFFLINE DETECTION RULES
// ------------------------------------------------------------

const OFFLINE_KEYWORD_RULES = [
  [
    ["digital arrest", "cbi", "narcotics", "video call", "aadhaar linked"],
    "digital_arrest",
    0.93
  ],
  [
    ["guaranteed return", "double your money", "sebi registered", "invest now", "trading tips"],
    "fake_investment",
    0.88
  ],
  [
    ["kyc update", "account blocked", "click link", "verify immediately", "suspend", "kyc blocked"],
    "phishing",
    0.80
  ],
  [
    ["bill payment overdue", "electricity disconnect", "pay now to avoid"],
    "bill_scam",
    0.82
  ],
  [
    ["earn from home", "part time job", "whatsapp group", "task complete payment"],
    "mule_recruitment",
    0.76
  ],
  [
    ["power cut", "transfer funds immediately", "digital arrest warrant"],
    "coercion",
    0.90
  ]
];

// ------------------------------------------------------------
// TRUSTED HOSTS
// ------------------------------------------------------------

const OFFLINE_SAFE_HOSTS = [
  "wikipedia.org",
  "github.com",
  "google.com",
  "microsoft.com",
  "apple.com",
  "android.com",
  "youtube.com",
  "stackoverflow.com",
  "gov.in",
  "whatsapp.com",
  "telegram.org"
];

// Exact safe-zone bypass list.  The content script also sets
// sessionStorage.guardain_bypass_active so these domains incur no DOM scan.
const GUARDAIN_SAFE_ZONE_HOSTS = [
  "google.com",
  "bing.com",
  "duckduckgo.com",
  "thehindu.com",
  "timesofindia.indiatimes.com",
  "gov.in",
  "nic.in"
];

// ------------------------------------------------------------
// SUSPICIOUS TLDs
// ------------------------------------------------------------

const SUSPICIOUS_TLDS = [
  ".xyz",
  ".top",
  ".click",
  ".link",
  ".icu",
  ".tk",
  ".ml",
  ".ga",
  ".cf",
  ".gq",
  ".zip",
  ".mov",
  ".country",
  ".stream",
  ".loan",
  ".gdn",
  ".rest"
];

// ------------------------------------------------------------
// TRUSTED HOST CHECK
// ------------------------------------------------------------

function hostLooksTrusted(host) {
  const h = String(host || "")
    .toLowerCase()
    .replace(/^www\./, "");

  return OFFLINE_SAFE_HOSTS.some(
    domain =>
      h === domain ||
      h.endsWith(`.${domain}`)
  );
}

function isGuardainSafeZone(host) {
  const normalized = String(host || "").toLowerCase().replace(/^www\./, "");
  return GUARDAIN_SAFE_ZONE_HOSTS.some(domain =>
    normalized === domain || normalized.endsWith(`.${domain}`)
  );
}

// ------------------------------------------------------------
// DOMAIN SIGNALS
// ------------------------------------------------------------

function domainSignals(host) {
  const h = String(host || "")
    .toLowerCase()
    .replace(/^www\./, "");

  if (!h) {
    return {
      score: 0,
      reasons: []
    };
  }

  const reasons = [];
  let score = 0;

  // Raw IP address
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(h)) {
    score += 0.30;
    reasons.push("raw_ip_host");
  }

  // Punycode
  if (h.includes("xn--")) {
    score += 0.30;
    reasons.push("punycode_domain");
  }

  // Suspicious TLD
  const dot = h.lastIndexOf(".");

  if (dot >= 0) {
    const tld = h.slice(dot);

    if (SUSPICIOUS_TLDS.includes(tld)) {
      score += 0.15;
      reasons.push(`suspicious_tld_${tld}`);
    }
  }

  // Suspicious/high entropy labels
  const labels = h.split(".");

  const suspiciousLabels = labels.filter(
    label =>
      label.length >= 12 &&
      (
        /^[a-z0-9]+$/.test(label) ||
        /\d{3,}/.test(label)
      )
  );

  if (suspiciousLabels.length) {
    score += 0.20;
    reasons.push("high_entropy_domain");
  }

  return {
    score,
    reasons
  };
}

// ------------------------------------------------------------
// LOCAL CLASSIFIER
// ------------------------------------------------------------

function offlineClassify(signal = {}) {

  const host = String(
    signal.url_host || ""
  ).toLowerCase();

  const path = String(
    signal.url_path || ""
  ).toLowerCase();

  const title = String(
    signal.title || ""
  ).toLowerCase();

  const text = String(
    signal.text_sample || ""
  ).toLowerCase();

  const url = String(
    signal.url || ""
  );

  if (isGuardainSafeZone(host)) {
    return {
      risk_level: "safe",
      threat_score: 0,
      reasons: ["safe_zone_bypass"],
      tier: "safe_zone_bypass",
      host
    };
  }

  const haystack =
    `${title}\n${path}\n${text}`;

  // Trusted domains
  if (
    host &&
    hostLooksTrusted(host)
  ) {
    return {
      risk_level: "safe",
      threat_score: 0.02,
      reasons: [],
      tier: "offline_heuristic",
      host
    };
  }

  let score = 0;
  const reasons = [];

  // Keyword rules
  for (
    const [keywords, label, baseScore]
    of OFFLINE_KEYWORD_RULES
  ) {

    const hits =
      keywords.filter(
        keyword =>
          haystack.includes(keyword)
      ).length;

    if (hits > 0) {

      const contribution =
        Math.min(
          baseScore,
          baseScore *
          (0.65 + hits * 0.18)
        );

      score =
        Math.max(
          score,
          contribution
        );

      if (!reasons.includes(label)) {
        reasons.push(label);
      }
    }
  }

  // Domain signals
  const ds =
    domainSignals(host);

  score =
    Math.min(
      1,
      score + ds.score
    );

  for (const reason of ds.reasons) {
    if (!reasons.includes(reason)) {
      reasons.push(reason);
    }
  }

  // HTTP + credential/payment page
  if (
    /^http:\/\//i.test(url) &&
    /(login|signin|password|otp|kyc|payment)/i.test(haystack)
  ) {
    score =
      Math.min(
        1,
        score + 0.25
      );

    reasons.push(
      "http_credential_or_payment"
    );
  }

  // UPI
  if (
    (signal.upi_links || []).length > 0 ||
    /upi:\/\/pay\b/i.test(text)
  ) {
    score =
      Math.min(
        1,
        score + 0.20
      );

    reasons.push(
      "upi_payment_link"
    );
  }

  // Credential collection
  if (
    /(password|passwd|otp|pin|cvv|card number|bank account|upi id)/i
      .test(haystack)
  ) {
    score =
      Math.min(
        1,
        score + 0.15
      );

    reasons.push(
      "credential_collection"
    );
  }

  // Normalize
  score =
    Math.round(
      Math.min(score, 1) * 100
    ) / 100;

  let risk_level = "safe";

  if (score >= 0.85) {
    risk_level = "high_risk";
  } else if (score >= 0.50) {
    risk_level = "suspicious";
  } else {
    score = 0.05;
  }

  return {
    risk_level,
    threat_score: score,
    reasons: [...new Set(reasons)],
    tier: "offline_heuristic",
    host
  };
}

// ------------------------------------------------------------
// SCAN
// ------------------------------------------------------------

async function scanSignal(
  signal,
  tabId
) {

  if (!signal || tabId == null) {
    return;
  }

  const {
    heuristic_enabled = true
  } = await chrome.storage.local.get({
    heuristic_enabled: true
  });

  // Local detection disabled
  if (!heuristic_enabled) {

    applyVerdict(
      {
        risk_level: "safe",
        threat_score: 0,
        reasons: [
          "local_heuristic_disabled"
        ],
        tier: "offline_disabled",
        host: signal.url_host || ""
      },
      tabId
    );

    return;
  }

  // Cache
  const key =
    cacheKey(
      signal.url_host,
      signal.url_path
    );

  const cached =
    tier0Cache.get(key);

  if (
    cached &&
    Date.now() - cached.ts <
      TIER0_TTL_MS
  ) {

    applyVerdict(
      cached.verdict,
      tabId
    );

    return;
  }

  // Local classification
  const verdict =
    offlineClassify(signal);

  tier0Cache.set(
    key,
    {
      verdict,
      ts: Date.now()
    }
  );

  applyVerdict(
    verdict,
    tabId
  );
}

// ------------------------------------------------------------
// APPLY VERDICT
// ------------------------------------------------------------

function applyVerdict(
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
  chrome.storage.session
    .set({
      [`verdict:${tabId}`]: {
        ...verdict,
        scannedAt: Date.now()
      }
    })
    .catch(() => {});

  // Send scan result
  chrome.tabs
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
  (message, sender) => {
    if (message?.type === "CAPTURE_SCREENSHOT") {
      const tabId = sender.tab?.id ?? message.tabId;
      if (tabId == null) return false;
      chrome.tabs.captureVisibleTab(sender.tab?.windowId, {format: "png", quality: 100})
        .then(async dataUrl => {
          const telemetry = message.telemetry || {};
          const payload = {
            url: telemetry.url || "",
            clean_url: telemetry.clean_url || null,
            screenshot_base64: dataUrl,
            dom_snapshot: telemetry.dom_snapshot || null,
            dom_signature: telemetry.dom_signature || null,
            browser: telemetry.browser || {},
            threat_score: Number(message.threat_score || 0.85),
            source: "extension"
          };
          await fetch("http://127.0.0.1:8080/v1/report/incident", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
          });
          await chrome.tabs.sendMessage(tabId, {type: "SCREENSHOT_CAPTURED", dataUrl});
        })
        .catch(error => console.warn("[GuardAIN] screenshot capture failed:", error));
      return false;
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
        message.payload,
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

        chrome.tabs
          .remove(tabId)
          .catch(error => {
            console.warn(
              "[GuardAIN] Could not close tab:",
              error
            );
          });
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

    tier0Cache.delete(
      `tab:${tabId}`
    );

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