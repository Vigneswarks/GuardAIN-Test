from __future__ import annotations

import base64
import asyncio
import hashlib
import json
import uuid
import time
import ssl
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field, HttpUrl

from .auth import create_access_token, require_admin, verify_password
from .config import settings
from .database import ThreatRepository
from .inference import MuRILInferenceService
from .gnn_engine import MuleAccountScorer
from .pii import redact_pii
from .whois_engine import analyze_domain
from .risk_policy import page_decision, safe_domain
from typing import Literal

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None
try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover
    redis = None

app = FastAPI(title="GuardAIN Central Admin API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
_rate_windows: dict[str, list[float]] = defaultdict(list)

@app.middleware("http")
async def rate_limit(request, call_next):
    if request.url.path.startswith("/v1/"):
        now = time.monotonic()
        key = request.client.host if request.client else "unknown"
        values = [stamp for stamp in _rate_windows[key] if now - stamp < settings.rate_limit_window_seconds]
        if len(values) >= settings.rate_limit_per_minute:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        values.append(now)
        _rate_windows[key] = values
    return await call_next(request)
# ONNX Runtime must be initialized after the Windows asyncio event loop exists;
# constructing a large session during module import can block Proactor loop
# creation. FastAPI startup owns the model lifecycle.
inference: MuRILInferenceService | None = None
gnn_scorer = MuleAccountScorer(settings.gnn_feature_dim, settings.gnn_hops)
incidents: list[dict[str, Any]] = []
whitelist: list[dict[str, str]] = []
db_pool: Any | None = None
db_ready = False
redis_client: Any | None = None
repository = ThreatRepository(database_url=settings.database_url)


def _postgres_connection_options(database_url: str) -> dict[str, Any]:
    """Return asyncpg options while preserving provider URLs safely.

    Managed providers commonly use ``?sslmode=require``.  asyncpg accepts an
    SSL context, which gives us certificate validation rather than silently
    opening a plaintext connection.  Remove libpq-only query switches after
    interpreting them so all supported cloud URLs behave consistently.
    """
    parsed = urlparse(database_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    requested = query.pop("sslmode", query.pop("ssl", "")).lower()
    mode = settings.database_ssl_mode
    require_tls = mode == "require" or (mode == "auto" and requested in {
        "require", "verify-ca", "verify-full", "true", "1",
    })
    clean_url = urlunparse(parsed._replace(query=urlencode(query)))
    options: dict[str, Any] = {"dsn": clean_url}
    if require_tls:
        options["ssl"] = ssl.create_default_context()
    return options


class LoginRequest(BaseModel):
    username: str
    password: str


class VerifyRequest(BaseModel):
    message: str = Field(default="", max_length=20_000)
    url: str = Field(default="", max_length=2048)


class PageSignals(BaseModel):
    credential_form: bool = False
    payment_request: bool = False
    coercion: bool = False
    urgent_demand: bool = False
    insecure_form: bool = False
    cross_origin_form: bool = False


class PageCheck(BaseModel):
    domain: str = Field(min_length=1, max_length=253, pattern=r"^[A-Za-z0-9.-]+$")
    signals: PageSignals = Field(default_factory=PageSignals)


class DomainReview(BaseModel):
    domain: str = Field(min_length=1, max_length=253, pattern=r"^[A-Za-z0-9.-]+$")
    status: Literal["safe", "malicious", "pending"]
    reason: str = Field(min_length=5, max_length=500)


@app.post("/v1/page-check")
async def page_check(payload: PageCheck):
    domain = payload.domain.lower().rstrip(".")
    review = await repository.get_domain_review(domain)
    result = page_decision(domain, payload.signals.model_dump(), review["status"] if review else None)
    result.update(domain=domain, threat_score=result["score"], engine="corroborated-page-policy",
                  review_status=review["status"] if review else "pending")
    if not safe_domain(domain):
        url = f"https://{domain}/"
        await repository.upsert_observation(url_hash=hashlib.sha256(url.encode()).hexdigest(),
            normalized_url=url, domain=domain, threat_score=result["score"], action=result["action"],
            reason=", ".join(result["reasons"]), features=payload.signals.model_dump(), model_version=result["engine"])
    return result


@app.post("/v1/admin/domains/review")
async def review_domain(payload: DomainReview, claims: dict = Depends(require_admin)):
    domain = payload.domain.lower().rstrip(".")
    if safe_domain(domain) and payload.status == "malicious":
        raise HTTPException(409, "Configured safe domains cannot be blocked")
    await repository.review_domain(domain, payload.status, payload.reason, str(claims.get("sub", "unknown")))
    return {"domain": domain, "status": payload.status}


@app.get("/v1/admin/domains/{domain}/audit")
async def domain_audit(domain: str, _: dict = Depends(require_admin)):
    normalized = domain.lower().strip().rstrip(".")
    if not normalized:
        raise HTTPException(status_code=422, detail="A valid domain is required")
    return {"domain": normalized, "entries": await repository.list_domain_audit(normalized)}


class MessageAnalysisRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)


class IncidentRequest(BaseModel):
    client_report_id: uuid.UUID | None = None
    # PWA message/VPA triage can be a legitimate report without a webpage.
    url: HttpUrl | None = None
    clean_url: str | None = Field(default=None, max_length=2048)
    screenshot_base64: str | None = Field(default=None, max_length=14_000_000)
    screenshot_hash: str | None = Field(default=None, max_length=128)
    dom_snapshot: str | None = Field(default=None, max_length=100_000)
    dom_signature: str | None = None
    browser: dict[str, Any] = Field(default_factory=dict)
    analysis: dict[str, Any] = Field(default_factory=dict)
    message: str = Field(default="", max_length=20_000)
    threat_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = Field(default="extension", max_length=40)



class VpaRequest(BaseModel):
    vpa: str = Field(min_length=3, max_length=320)


class WhitelistRequest(BaseModel):
    value: str = Field(min_length=1, max_length=2048)
    reason: str = Field(default="Operator review", max_length=500)


def _safe_screenshot(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.split(",", 1)[-1]
    try:
        data = base64.b64decode(raw, validate=True)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid base64 screenshot") from exc
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Screenshot exceeds 10 MB")
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=422, detail="Screenshot must be PNG")
    return base64.b64encode(data).decode("ascii")


def _screenshot_digest(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.split(",", 1)[-1]
    try:
        data = base64.b64decode(raw, validate=True)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid base64 screenshot") from exc
    return hashlib.sha256(data).hexdigest()


def _url_parts(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    normalized = parsed._replace(fragment="").geturl()
    return normalized, (parsed.hostname or "").lower()


async def _predict_message(message: str) -> dict[str, Any]:
    """Run MuRIL/fallback inference with an optional privacy-limited Redis cache."""
    if inference is None:
        raise HTTPException(status_code=503, detail="Inference service is initializing")
    status = inference.status()
    metadata = status.get("model_metadata", {})
    version = f"{status.get('engine')}:{metadata.get('dataset_sha256', settings.model_version)}"
    cache_key = "guardain:message:" + hashlib.sha256(f"{version}\0{message}".encode("utf-8")).hexdigest()
    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                result = json.loads(cached)
                result["cache_hit"] = True
                return result
        except Exception:
            pass
    result = await inference.predict(message)
    result["cache_hit"] = False
    if redis_client is not None:
        try:
            await redis_client.setex(
                cache_key, settings.redis_cache_ttl_seconds,
                json.dumps(result, ensure_ascii=False),
            )
        except Exception:
            pass
    return result


@app.on_event("startup")
async def connect_services() -> None:
    global db_pool, redis_client, repository, db_ready, inference
    # Test runners and reload servers can execute more than one application
    # lifecycle in the same process. Recreate the bounded worker pool after a
    # prior clean shutdown.
    if inference is None or getattr(inference, "closed", False):
        inference = MuRILInferenceService(allow_synthetic_model=settings.guardain_allow_synthetic_model)
    if asyncpg is not None and settings.database_url.startswith(("postgres://", "postgresql://")):
        production = settings.environment.lower() in {"production", "prod"}
        # A newly-created managed database can take a short time to accept
        # connections. Retry during production startup instead of allowing the
        # API to exit before its Render database is ready.
        attempts = 12 if production else 1
        last_db_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                db_pool = await asyncpg.create_pool(
                    **_postgres_connection_options(settings.database_url),
                    min_size=1,
                    max_size=5,
                    timeout=settings.service_connect_timeout_seconds,
                    command_timeout=settings.service_connect_timeout_seconds,
                )
                repository = ThreatRepository(db_pool)
                await repository.ensure_schema()
                db_ready = True
                break
            except Exception as exc:
                db_pool = None
                last_db_error = exc
                if attempt < attempts:
                    print(f"GuardAIN PostgreSQL connection attempt {attempt}/{attempts} failed: {exc}")
                    await asyncio.sleep(5)
        if not db_ready:
            if production:
                raise RuntimeError(
                    "GuardAIN PostgreSQL is required in production; "
                    f"connection failed after {attempts} attempts: {last_db_error}"
                ) from last_db_error
            print(f"GuardAIN database unavailable; using memory fallback: {last_db_error}")
    if db_pool is None and repository.sqlite_path is not None:
        await repository.ensure_schema()
        db_ready = True
    if redis is not None and settings.redis_url:
        try:
            redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=settings.service_connect_timeout_seconds,
                socket_timeout=settings.service_connect_timeout_seconds,
            )
            await redis_client.ping()
        except Exception as exc:
            redis_client = None
            if settings.environment.lower() in {"production", "prod"}:
                raise RuntimeError("GuardAIN Redis is required in production") from exc
            print(f"GuardAIN Redis unavailable; continuing without cache: {exc}")


@app.on_event("shutdown")
async def disconnect_services() -> None:
    global db_pool, redis_client, db_ready
    if redis_client is not None:
        await redis_client.aclose()
    if db_pool is not None:
        await db_pool.close()
    db_pool = None
    redis_client = None
    db_ready = False
    if inference is not None:
        await inference.close()


@app.get("/health")
async def health() -> dict[str, Any]:
    database_mode = "postgresql" if db_pool is not None else "sqlite" if repository.sqlite_path is not None else "unavailable"
    return {"status": "online", "service": "guardain-api", "database": db_ready,
            "database_mode": database_mode, "redis": redis_client is not None,
            "inference": inference.status() if inference is not None else {"engine": "initializing", "model_loaded": False}}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    """Load-balancer readiness endpoint: cloud persistence must be live."""
    if not db_ready:
        raise HTTPException(status_code=503, detail="Database is not ready")
    if settings.environment.lower() in {"production", "prod"} and redis_client is None:
        raise HTTPException(status_code=503, detail="Redis is not ready")
    return {"status": "ready", "database": True, "redis": redis_client is not None,
            "inference": inference.status() if inference is not None else {"engine": "initializing", "model_loaded": False}}


@app.get("/", response_class=HTMLResponse)
async def portal() -> str:
    path = Path(__file__).resolve().parents[2] / "admin_portal" / "index.html"
    return path.read_text(encoding="utf-8")


@app.get("/config.js")
async def portal_config():
    return FileResponse(Path(__file__).resolve().parents[2] / "admin_portal" / "config.js", media_type="application/javascript")


@app.get("/demo/extension-test")
async def extension_demo() -> FileResponse:
    """Controlled local-only test page for verifying extension policy flow."""
    return FileResponse(
        Path(__file__).resolve().parents[2] / "extension" / "demo-scam-test.html",
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


DEMO_PAGES = {
    "upi-payment": "demo-upi-payment-test.html",
    "review-only": "demo-review-test.html",
    "awareness": "demo-awareness-test.html",
    "normal-login": "demo-normal-login-test.html",
}


@app.get("/demo/{demo_name}")
async def named_demo(demo_name: str) -> FileResponse:
    """Serve allow-listed, harmless extension demonstration fixtures only."""
    filename = DEMO_PAGES.get(demo_name)
    if not filename:
        raise HTTPException(status_code=404, detail="Demo page not found")
    return FileResponse(
        Path(__file__).resolve().parents[2] / "extension" / filename,
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/pwa", response_class=HTMLResponse)
@app.get("/pwa/", response_class=HTMLResponse)
async def pwa() -> str:
    path = Path(__file__).resolve().parents[2] / "pwa" / "index.html"
    return path.read_text(encoding="utf-8")


@app.get("/pwa/{asset_path:path}")
async def pwa_asset(asset_path: str) -> FileResponse:
    root = (Path(__file__).resolve().parents[2] / "pwa").resolve()
    requested = (root / asset_path).resolve()
    if root not in requested.parents:
        raise HTTPException(status_code=404, detail="PWA asset not found")
    if not requested.is_file():
        raise HTTPException(status_code=404, detail="PWA asset not found")
    return FileResponse(requested)


@app.post("/v1/admin/login")
async def admin_login(payload: LoginRequest) -> dict[str, str]:
    if payload.username != settings.admin_username or not verify_password(payload.password, settings.admin_password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_access_token(payload.username), "token_type": "bearer"}


async def _verify(message: str, url: str) -> dict[str, Any]:
    message = redact_pii(message)
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if url and (parsed.scheme not in {"http", "https"} or not host):
            raise ValueError("Expected HTTP(S) URL")
    except ValueError as exc:
        raise HTTPException(422, "Provide a valid HTTP(S) URL") from exc
    review = await repository.get_domain_review(host) if host else None
    decision = page_decision(host, {}, review["status"] if review else None)
    if safe_domain(host) or (review and review["status"] == "safe"):
        return {"url": url, "score": 0.0, "threat_score": 0.0, "action": "ALLOW",
                "label": "benign", "risk_level": "safe", "key_trigger_words": [],
                "matched_categories": [], "engine": "safe-zone-bypass"}
    if inference is None:
        raise HTTPException(status_code=503, detail="Inference service is initializing")
    result = await _predict_message(message) if message.strip() else {
        "score": 0.0, "label": "unknown", "risk_level": "unknown",
        "key_trigger_words": [], "matched_categories": [], "engine": "url-review"}
    effective_score = max(float(result["score"]), float(decision["score"]))
    response = {"url": url, **result, "score": effective_score, "threat_score": effective_score,
                "action": decision["action"], "blocking_reasons": decision["reasons"]}
    if host:
        # Persist a domain observation, never secret-bearing paths or queries.
        normalized = f"https://{host}/"
        await repository.upsert_observation(
            url_hash=hashlib.sha256(normalized.encode()).hexdigest(),
            normalized_url=normalized, domain=host, threat_score=effective_score,
            action=decision["action"], reason=", ".join(result.get("key_trigger_words", [])),
            features={"engine": result["engine"], "action": decision["action"]},
            model_version=result["engine"])
    return response


@app.get("/v1/verify")
async def verify_get(message: str = "", url: str = "") -> dict[str, Any]:
    return await _verify(message, url)


@app.post("/v1/verify")
async def verify_post(payload: VerifyRequest) -> dict[str, Any]:
    return await _verify(payload.message, payload.url)


@app.post("/v1/analyzer/message")
async def analyze_message(payload: MessageAnalysisRequest) -> dict[str, Any]:
    """Return a verdict plus human-readable scam patterns for a message."""
    return await _predict_message(redact_pii(payload.message))


async def _enrich(incident: dict[str, Any]) -> None:
    incident_url = str(incident.get("url") or "")
    if incident_url:
        try:
            incident["whois"] = await asyncio.wait_for(analyze_domain(incident_url), timeout=5)
        except Exception:
            incident["whois"] = {"status": "unavailable"}
    else:
        incident["whois"] = {"status": "not_applicable_message_only"}
    incident["mule_account"] = gnn_scorer.score(incident.get("vpa_features"))
    incident["payload"]["whois"] = incident["whois"]
    normalized, domain = _url_parts(incident_url) if incident_url else ("", "")
    if domain:
        score = float(incident.get("threat_score", 0.0))
        await repository.upsert_observation(
            url_hash=hashlib.sha256(normalized.encode()).hexdigest(),
            normalized_url=normalized,
            domain=domain,
            threat_score=score,
            action="BLOCK" if score >= 0.85 else "REVIEW" if score >= 0.45 else "ALLOW",
            reason=", ".join(incident.get("analysis", {}).get("key_trigger_words", [])) or "extension telemetry",
            features={"source": incident.get("source"), "whois": incident["whois"]},
            model_version=incident.get("analysis", {}).get("engine", settings.model_version),
        )
    await repository.record_incident(incident)


@app.post("/v1/reports/incidents", status_code=202)
@app.post("/v1/report/incident", status_code=202)
async def report_incident(payload: IncidentRequest, tasks: BackgroundTasks) -> dict[str, Any]:
    dom = payload.dom_snapshot or ""
    incident = payload.model_dump(mode="json")
    incident.update({"id": str(payload.client_report_id or uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat(),
                     "screenshot_base64": _safe_screenshot(payload.screenshot_base64),
                     "dom_signature": payload.dom_signature or hashlib.sha256(dom.encode()).hexdigest()})
    computed_screenshot_hash = _screenshot_digest(payload.screenshot_base64)
    if payload.screenshot_hash and computed_screenshot_hash and payload.screenshot_hash.lower() != computed_screenshot_hash:
        raise HTTPException(status_code=422, detail="Screenshot SHA-256 verification failed")
    incident["screenshot_hash"] = computed_screenshot_hash or payload.screenshot_hash
    if not incident["threat_score"] and payload.message:
        prediction = await _verify(payload.message, str(payload.url or ""))
        incident["threat_score"] = prediction["score"]
        incident["analysis"] = prediction
    incident["payload"] = {"url": incident["url"], "clean_url": incident.get("clean_url"),
                            "screenshot_base64": incident.get("screenshot_base64"),
                            "dom_signature": incident["dom_signature"], "browser": incident.get("browser", {}),
                            "analysis": incident.get("analysis", {})}
    incidents.insert(0, incident)
    del incidents[settings.max_incidents:]
    await repository.record_incident(incident)
    tasks.add_task(_enrich, incident)
    return {"incident_id": incident["id"], "status": "accepted", "live_store": db_ready}


@app.post("/v1/telemetry", status_code=202)
async def telemetry(payload: IncidentRequest, tasks: BackgroundTasks) -> dict[str, Any]:
    """Accept extension telemetry through the stable public telemetry contract."""
    return await report_incident(payload, tasks)


@app.post("/v1/analyzer/vpa")
async def analyze_vpa(payload: VpaRequest) -> dict[str, Any]:
    result = await _verify(payload.vpa, "")
    result["vpa"] = payload.vpa
    result["action"] = "BLOCK" if result["threat_score"] >= 0.85 else "REVIEW" if result["threat_score"] >= 0.45 else "ALLOW"
    return result


@app.get("/v1/admin/incidents")
async def admin_incidents(_: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    stored = await repository.list_incidents(settings.max_incidents) if db_ready else []
    merged = stored or incidents
    return {"incidents": merged}


@app.get("/v1/reputation/domain")
async def domain_reputation(domain: str) -> dict[str, Any]:
    normalized = (urlparse(domain if "://" in domain else f"https://{domain}").hostname or "").lower()
    if not normalized:
        raise HTTPException(status_code=422, detail="A valid domain is required")
    record = await repository.domain_reputation(normalized) if db_ready else None
    review = await repository.get_domain_review(normalized) if db_ready else None
    score = float(record["threat_score"]) if record else 0.0
    return {
        "domain": normalized,
        "known": record is not None,
        "threat_score": score,
        "action": page_decision(normalized, {}, review["status"] if review else None)["action"],
        "review_status": review["status"] if review else "pending",
        "last_seen_at": record.get("last_seen_at") if record else None,
        "observation_count": int(record.get("observation_count", 0)) if record else 0,
    }


@app.get("/v1/admin/domains")
async def admin_domains(limit: int = 100, _: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    domains = await repository.list_domains(limit) if db_ready else []
    for domain in domains:
        review = await repository.get_domain_review(domain["domain"])
        domain["review_status"] = review["status"] if review else "pending"
    return {"domains": domains}


@app.get("/v1/admin/whitelist")
async def admin_whitelist(_: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    return {"entries": whitelist}


@app.post("/v1/admin/whitelist")
async def add_whitelist(payload: WhitelistRequest, _: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    entry = payload.model_dump()
    whitelist.append(entry)
    return entry


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
