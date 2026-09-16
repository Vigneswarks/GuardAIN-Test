from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
import math
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

try:
    import jwt
except ImportError:  # pragma: no cover - a small fallback keeps local imports usable
    jwt = None

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None
try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover
    redis = None
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:  # pragma: no cover
    pa = pq = None

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator

from .config import settings
from .database import ThreatRepository
from .gnn_engine import UPIMuleTopologyScorer
from .inference import MuRILInferenceService
from .security import (
    build_blacklist_hash, create_access_token as secure_create_access_token,
    decode_access_token, normalize_for_lookup, sanitize_for_backend,
)

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("guardain")
bearer = HTTPBearer(auto_error=False)


class PredictionRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=5000)
    channel: str = "web"
    metadata: dict[str, Any] = Field(default_factory=dict)


class VerifyRequest(BaseModel):
    text_content: str | None = Field(default=None, max_length=5000)
    vpa_handle: str | None = Field(default=None, max_length=255)
    domain: str | None = Field(default=None, max_length=2048)
    page_context: dict[str, Any] = Field(default_factory=dict)


class URLScanRequest(BaseModel):
    url: str = Field(..., min_length=3, max_length=2048)
    vpa: str | None = None


class VPAAnalyzerRequest(BaseModel):
    vpa: str | None = Field(default=None, min_length=3, max_length=320)
    vpa_handle: str | None = Field(default=None, min_length=3, max_length=320)
    context: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def require_vpa(self) -> "VPAAnalyzerRequest":
        if not (self.vpa or self.vpa_handle):
            raise ValueError("vpa is required")
        return self


class APKAnalyzerRequest(BaseModel):
    sha256: str | None = Field(default=None, pattern=r"^[A-Fa-f0-9]{64}$")
    package_name: str | None = Field(default=None, max_length=255)
    permissions: list[str] = Field(default_factory=list, max_length=200)
    urls: list[str] = Field(default_factory=list, max_length=100)
    file_name: str | None = Field(default=None, max_length=255)


class GNNRequest(BaseModel):
    edges: list[list[float | int]] = Field(default_factory=list)
    seed_nodes: list[int] = Field(default_factory=list)
    hops: int = Field(default=3, ge=1, le=10)
    num_nodes: int | None = Field(default=None, ge=1)


class FalseNegativeReport(BaseModel):
    sample_text: str = Field(..., min_length=3, max_length=10000)
    category: Literal["digital_arrest", "utility_disconnection", "upi_collect", "phishing"]
    model_output: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenRequest(BaseModel):
    api_key: str = Field(..., min_length=8, max_length=256)


class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class TelemetryEvent(BaseModel):
    event: str = Field(..., min_length=1, max_length=100)
    source: str = Field(default="client", max_length=40)
    properties: dict[str, Any] = Field(default_factory=dict)


class WhitelistEntry(BaseModel):
    value: str = Field(..., min_length=2, max_length=2048)
    reason: str = Field(default="approved false positive", max_length=500)
    expires_at: datetime | None = None


def _model_dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _jwt_encode(payload: dict[str, Any]) -> str:
    if jwt is not None:
        return str(jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm))
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    body = {**payload, "iat": int(time.time())}
    first = _b64(json.dumps(header, separators=(",", ":")).encode())
    second = _b64(json.dumps(body, separators=(",", ":")).encode())
    signature = _b64(hmac.new(settings.jwt_secret_key.encode(), f"{first}.{second}".encode(), hashlib.sha256).digest())
    return f"{first}.{second}.{signature}"


def _jwt_decode(token: str) -> dict[str, Any]:
    if jwt is not None:
        try:
            return dict(jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]))
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Invalid authentication token") from exc
    try:
        first, second, signature = token.split(".")
        expected = _b64(hmac.new(settings.jwt_secret_key.encode(), f"{first}.{second}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        payload = json.loads(base64.urlsafe_b64decode(second + "=" * (-len(second) % 4)))
        if payload.get("exp", 0) < time.time():
            raise ValueError("expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token") from exc


def create_access_token(subject: str, role: str = "client", expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    ttl = expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    return _jwt_encode({"sub": subject, "role": role, "iat": int(now.timestamp()), "exp": int((now + ttl).timestamp())})


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = None
    database_pool = None
    repository = ThreatRepository()
    try:
        if redis is not None:
            redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            await redis_client.ping()
    except Exception as exc:
        redis_client = None
        logger.info("Redis unavailable; using in-memory cache: %s", exc)
    try:
        if asyncpg is not None:
            database_pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5, command_timeout=2)
            repository = ThreatRepository(database_pool)
            await repository.ensure_schema()
    except Exception as exc:
        database_pool = None
        logger.info("PostgreSQL unavailable; using in-memory persistence: %s", exc)
    app.state.redis = redis_client
    app.state.database_pool = database_pool
    app.state.repository = repository
    app.state.inference = MuRILInferenceService(settings.onnx_model_path, settings.onnx_tokenizer_path, settings.onnx_execution_providers)
    app.state.gnn = UPIMuleTopologyScorer(settings.gnn_feature_dim)
    app.state.incidents = []
    app.state.telemetry = []
    app.state.whitelist = {}
    app.state.rate_limits = {}
    yield
    if database_pool is not None:
        await database_pool.close()
    if redis_client is not None:
        await redis_client.aclose()
    await app.state.inference.close()


app = FastAPI(title=settings.app_name, version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"(chrome-extension|moz-extension)://.*|https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=settings.allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return _jwt_decode(credentials.credentials)


async def require_admin(user: dict[str, Any] = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


async def enforce_rate_limit(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    now = time.time()
    bucket = app.state.rate_limits
    timestamps = [stamp for stamp in bucket.get(x_api_key, []) if stamp > now - settings.rate_limit_window_seconds]
    if len(timestamps) >= settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    timestamps.append(now)
    bucket[x_api_key] = timestamps


def normalize_url(value: str) -> tuple[str, str]:
    candidate = value.strip()
    if "://" not in candidate:
        candidate = "https://" + candidate
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=422, detail="Only valid HTTP(S) URLs are accepted")
    hostname = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    return urlunsplit((parsed.scheme.lower(), hostname, parsed.path or "/", parsed.query, "")), hostname


SAFE_ZONE_DOMAINS = (
    "google.com",
    "bing.com",
    "duckduckgo.com",
    "thehindu.com",
    "timesofindia.indiatimes.com",
    "gov.in",
    "nic.in",
)


def is_safe_zone_hostname(hostname: str) -> bool:
    normalized = hostname.lower().removeprefix("www.").rstrip(".")
    return any(normalized == domain or normalized.endswith(f".{domain}") for domain in SAFE_ZONE_DOMAINS)


def _entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {char: value.count(char) for char in set(value)}
    length = len(value)
    return round(-sum((count / length) * math.log2(count / length) for count in counts.values()), 4)


def _levenshtein(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for row, char_left in enumerate(left, 1):
        current = [row]
        for column, char_right in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[column] + 1,
                               previous[column - 1] + (char_left != char_right)))
        previous = current
    return previous[-1]


def _domain_age_days(hostname: str) -> int | None:
    """Best-effort WHOIS age; an unavailable WHOIS service never blocks scans."""
    try:
        import whois  # type: ignore
        created = whois.whois(hostname).creation_date
        if isinstance(created, list):
            created = next((item for item in created if item), None)
        if created is None:
            return None
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - created).days)
    except Exception:
        return None


# Public utility names for integrations and small offline test harnesses.
shannon_entropy = _entropy
levenshtein_distance = _levenshtein
whois_age_days = _domain_age_days


def analyze_domain(value: str) -> dict[str, Any]:
    normalized, hostname = normalize_url(value)
    labels = hostname.split(".")
    entropy = _entropy(hostname.replace(".", ""))
    suspicious_tlds = {".xyz", ".top", ".click", ".link", ".icu", ".tk", ".ml", ".ga", ".cf", ".gq", ".zip"}
    reasons: list[str] = []
    score = 0.0
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", hostname):
        score += 0.3
        reasons.append("raw_ip_host")
    if "xn--" in hostname:
        score += 0.25
        reasons.append("punycode_domain")
    if is_safe_zone_hostname(hostname):
        score = 0.0
        reasons = ["safe_zone_domain"]
    if any(hostname.endswith(tld) for tld in suspicious_tlds):
        score += 0.15
        reasons.append("suspicious_tld")
    if entropy >= 3.7 or any(len(label) >= 24 for label in labels):
        score += 0.18
        reasons.append("high_entropy_domain")
    age_days = _domain_age_days(hostname)
    if age_days is not None and age_days < 30:
        score += 0.25
        reasons.append("new_domain")
    known = ("google", "microsoft", "paypal", "amazon", "facebook", "instagram", "sbi", "hdfc", "icici")
    registered = labels[-2] if len(labels) > 1 else hostname
    candidates = [registered] + [part for part in re.split(r"[-_]", registered) if part]
    typos = []
    for brand in known:
        distance = min(_levenshtein(candidate, brand) for candidate in candidates)
        if 0 < distance <= 2:
            typos.append({"target": brand, "distance": distance})
    if typos:
        score += 0.3
        reasons.append("typosquatting")
    return {
        "url": normalized, "domain": hostname, "whois_age_days": age_days,
        "entropy": entropy, "typosquatting": typos, "reasons": reasons,
        "threat_score": round(min(1.0, score), 4),
        "action": "BLOCK" if score >= 0.56 else "REVIEW" if score >= 0.3 else "ALLOW",
    }


def _whitelist_hit(value: str) -> bool:
    if not value:
        return False
    normalized = normalize_for_lookup(value)
    entry = app.state.whitelist.get(normalized)
    if not entry:
        return False
    if entry.get("expires_at") and entry["expires_at"] < datetime.now(timezone.utc):
        app.state.whitelist.pop(normalized, None)
        return False
    return True


def _append_incident(action: str, score: float, reason: str, payload: dict[str, Any]):
    if action == "ALLOW":
        return
    incident = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "verify",
        "action": action,
        "threat_score": round(score, 4),
        "reason": reason,
        "payload": payload,
        "resolved": False,
    }
    app.state.incidents.insert(0, incident)
    del app.state.incidents[settings.max_incidents:]
    return incident


async def _persist_incident(incident):
    if incident:
        try:
            await app.state.repository.record_incident(incident)
        except Exception:
            logger.exception("incident persistence failed")


@app.middleware("http")
async def request_logging(request: Request, call_next):
    started = time.perf_counter()
    if request.url.path.startswith("/v1/") and request.url.path not in {"/v1/token"}:
        # Public analyzers do not require an API key, so enforce a conservative
        # per-client window at the HTTP boundary as well.
        limits = getattr(app.state, "rate_limits", {})
        client_key = f"ip:{request.client.host if request.client else 'unknown'}"
        now = time.time()
        stamps = [stamp for stamp in limits.get(client_key, []) if stamp > now - settings.rate_limit_window_seconds]
        if len(stamps) >= settings.rate_limit_per_minute:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        stamps.append(now)
        limits[client_key] = stamps
    response = await call_next(request)
    response.headers["X-Request-ID"] = uuid.uuid4().hex
    logger.info("%s %s %s %.2fms", request.method, request.url.path, response.status_code, (time.perf_counter() - started) * 1000)
    return response


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment, "fallback": app.state.redis is None or app.state.database_pool is None}


@app.post("/v1/token")
async def issue_token(request: TokenRequest):
    return {"access_token": create_access_token(request.api_key), "token_type": "bearer"}


@app.post("/v1/admin/login")
async def admin_login(request: AdminLoginRequest):
    username_ok = hmac.compare_digest(request.username, settings.admin_username)
    password_ok = hmac.compare_digest(request.password, settings.admin_password)
    if not username_ok or not password_ok:
        raise HTTPException(status_code=401, detail="Invalid administrator credentials")
    return {"access_token": create_access_token(request.username, "admin"), "token_type": "bearer", "expires_in": settings.jwt_access_token_expire_minutes * 60}


@app.post("/v1/telemetry")
async def telemetry(event: TelemetryEvent, request: Request):
    record = {"id": uuid.uuid4().hex, "timestamp": datetime.now(timezone.utc).isoformat(), "ip": request.client.host if request.client else None, **_model_dump(event)}
    record["properties"] = sanitize_for_backend(record["properties"])
    app.state.telemetry.insert(0, record)
    del app.state.telemetry[settings.max_telemetry_events:]
    return {"status": "accepted", "id": record["id"]}


@app.post("/v1/verify")
async def verify(request: VerifyRequest):
    started = time.perf_counter()
    sanitized = sanitize_for_backend(_model_dump(request))
    text = (sanitized.get("text_content") or "").strip()
    domain = (request.domain or "").strip()
    vpa = (sanitized.get("vpa_handle") or "").strip()
    normalized_url = ""
    hostname = ""
    if domain:
        normalized_url, hostname = normalize_url(domain)
        if is_safe_zone_hostname(hostname):
            return {"action": "ALLOW", "threat_score": 0.0, "reason": "Domain is in the GuardAIN safe zone.", "execution_time_ms": round((time.perf_counter() - started) * 1000, 2), "engine": "safe_zone"}
        if _whitelist_hit(hostname) or _whitelist_hit(normalized_url):
            return {"action": "ALLOW", "threat_score": 0.0, "reason": "Domain is on the false-positive whitelist.", "execution_time_ms": round((time.perf_counter() - started) * 1000, 2), "engine": "whitelist"}
    combined = " ".join(part for part in [text, vpa, normalized_url, json.dumps(sanitized.get("page_context") or {}, ensure_ascii=False)] if part)
    cache_key = "verify:" + build_blacklist_hash(combined)
    client = app.state.redis
    if client is not None:
        try:
            cached = await client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
    prediction = await app.state.inference.predict(combined)
    score = float(prediction.get("score", 0.0))
    action = "BLOCK" if score >= 0.56 else "REVIEW" if score >= 0.35 else "ALLOW"
    reason = "High risk scam or credential-collection indicators detected." if action == "BLOCK" else "Suspicious indicators require review." if action == "REVIEW" else "No malicious indicators detected in the supplied content."
    response = {"action": action, "threat_score": round(score, 4), "reason": reason, "execution_time_ms": round((time.perf_counter() - started) * 1000, 2), "engine": prediction.get("engine", "fallback")}
    incident = _append_incident(action, score, reason, {"domain": hostname, "text": text[:500], "vpa": vpa})
    await _persist_incident(incident)
    if client is not None:
        try:
            await client.setex(cache_key, settings.redis_cache_ttl_seconds, json.dumps(response))
        except Exception:
            pass
    return response


@app.post("/v1/predict")
async def predict(request: PredictionRequest, _: dict[str, Any] = Depends(get_current_user), __: None = Depends(enforce_rate_limit)):
    payload = sanitize_for_backend(_model_dump(request))
    result = await app.state.inference.predict(payload["text"])
    return {"status": "ok", "prediction": result, "channel": payload["channel"], "risk": result.get("risk_level", "low")}


@app.post("/v1/analyzer/url")
async def analyzer_url(request: URLScanRequest):
    analysis = analyze_domain(request.url)
    analysis.update({"status": "ok", "vpa": request.vpa,
                     "blacklist": {"domain_hit": _whitelist_hit(analysis["domain"]),
                                   "vpa_hit": False, "blacklisted": False}})
    return analysis


@app.post("/v1/scan-url")
async def scan_url(request: URLScanRequest, _: dict[str, Any] = Depends(get_current_user), __: None = Depends(enforce_rate_limit)):
    normalized, hostname = normalize_url(request.url)
    analysis = analyze_domain(normalized)
    analysis.update({"status": "ok", "vpa": request.vpa,
                     "blacklist": {"domain_hit": _whitelist_hit(hostname), "vpa_hit": False, "blacklisted": False}})
    return analysis


@app.post("/v1/analyzer/vpa")
async def analyze_vpa(request: VPAAnalyzerRequest):
    """Validate a VPA and score common mule/impersonation indicators."""
    value = (request.vpa or request.vpa_handle or "").strip().lower()
    valid = bool(re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,254}@[a-z0-9.-]{2,}", value))
    local, _, provider = value.partition("@")
    reasons: list[str] = []
    score = 0.05 if valid else 0.65
    if not valid:
        reasons.append("invalid_vpa_format")
    if local and (len(local) > 25 or re.search(r"\d{5,}", local)):
        score += 0.15
        reasons.append("synthetic_or_high_volume_handle")
    if provider in {"upi", "paytm", "ybl", "oksbi", "okaxis", "okicici", "okhdfcbank"}:
        score = max(0.0, score - 0.05)
    context_prediction = await app.state.inference.predict(request.context) if request.context else None
    if context_prediction and context_prediction.get("score", 0) >= 0.5:
        score = max(score, float(context_prediction["score"]))
        reasons.append("suspicious_context")
    score = round(min(1.0, score), 4)
    return {"status": "ok", "vpa": "[UPI]" if valid else value, "valid": valid,
            "provider": provider, "local_part": local, "threat_score": score,
            "action": "BLOCK" if score >= 0.56 else "REVIEW" if score >= 0.35 else "ALLOW",
            "reasons": reasons}


@app.post("/v1/analyzer/apk")
async def analyze_apk(request: APKAnalyzerRequest):
    """Static APK triage; no uploaded binary is persisted by the API."""
    suspicious_permissions = {
        "android.permission.READ_SMS", "android.permission.RECEIVE_SMS",
        "android.permission.REQUEST_INSTALL_PACKAGES", "android.permission.SYSTEM_ALERT_WINDOW",
        "android.permission.BIND_ACCESSIBILITY_SERVICE", "android.permission.READ_CALL_LOG",
    }
    permission_hits = sorted({item for item in request.permissions if item in suspicious_permissions})
    url_results = []
    for item in request.urls[:50]:
        try:
            url_results.append(analyze_domain(item))
        except HTTPException:
            continue
    score = min(1.0, len(permission_hits) * 0.32 + max(
        (result["threat_score"] for result in url_results), default=0.0))
    if request.file_name and re.search(r"(update|kyc|bank|loan|reward|prize)", request.file_name, re.I):
        score = min(1.0, score + 0.15)
    return {"status": "ok", "sha256": request.sha256, "package_name": request.package_name,
            "permission_hits": permission_hits, "url_analysis": url_results,
            "threat_score": round(score, 4),
            "action": "BLOCK" if score >= 0.56 else "REVIEW" if score >= 0.3 else "ALLOW"}


@app.post("/v1/gnn-score")
async def gnn_score(request: GNNRequest, _: dict[str, Any] = Depends(get_current_user), __: None = Depends(enforce_rate_limit)):
    return {"status": "ok", "network_score": app.state.gnn.score_from_edges(request.edges, request.seed_nodes, request.hops, request.num_nodes)}


def _append_buffer(sample: dict[str, Any]) -> Path:
    path = Path(settings.model_retrain_buffer)
    path.parent.mkdir(parents=True, exist_ok=True)
    if pa is not None and pq is not None:
        table = pa.Table.from_pylist([sample])
        if path.exists():
            table = pa.concat_tables([pq.read_table(path), table])
        pq.write_table(table, path)
        return path
    path = path.with_suffix(".jsonl")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(sample, ensure_ascii=False) + "\n")
    return path


@app.post("/v1/report-false-negative")
async def report_false_negative(request: FalseNegativeReport, _: dict[str, Any] = Depends(get_current_user), __: None = Depends(enforce_rate_limit)):
    sample = _model_dump(request)
    sample["sample_text"] = sanitize_for_backend(sample["sample_text"])
    sample["timestamp"] = datetime.now(timezone.utc).isoformat()
    path = await asyncio.to_thread(_append_buffer, sample)
    return {"status": "ok", "buffer_path": str(path)}


@app.get("/v1/admin/incidents")
async def admin_incidents(limit: int = 100, _: dict[str, Any] = Depends(require_admin)):
    incidents = app.state.incidents[: max(1, min(limit, settings.max_incidents))]
    if not incidents:
        incidents = await app.state.repository.list_incidents(limit)
    return {"status": "ok", "count": len(incidents), "incidents": incidents}


@app.get("/v1/admin/whitelist")
@app.get("/v1/admin/false-positive-whitelist")
@app.get("/v1/admin/false-positives")
@app.get("/v1/false-positive-whitelist")
async def list_whitelist(_: dict[str, Any] = Depends(require_admin)):
    return {"status": "ok", "entries": list(app.state.whitelist.values())}


@app.post("/v1/admin/whitelist")
@app.post("/v1/admin/false-positive-whitelist")
@app.post("/v1/admin/false-positives")
@app.post("/v1/false-positive-whitelist")
async def add_whitelist(entry: WhitelistEntry, _: dict[str, Any] = Depends(require_admin)):
    normalized = normalize_for_lookup(entry.value)
    expiry = entry.expires_at
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    record = {"value": entry.value, "key": normalized, "reason": entry.reason, "expires_at": expiry}
    app.state.whitelist[normalized] = record
    return {"status": "ok", "entry": record}


@app.delete("/v1/admin/whitelist/{value:path}")
@app.delete("/v1/admin/false-positive-whitelist/{value:path}")
async def remove_whitelist(value: str, _: dict[str, Any] = Depends(require_admin)):
    removed = app.state.whitelist.pop(normalize_for_lookup(value), None)
    if removed is None:
        raise HTTPException(status_code=404, detail="Whitelist entry not found")
    return {"status": "ok", "removed": removed["value"]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
