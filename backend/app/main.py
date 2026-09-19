from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, HttpUrl

from .auth import create_access_token, require_admin, verify_password
from .config import settings
from .inference import MuRILInferenceService
from .whois_engine import analyze_domain

app = FastAPI(title="GuardAIN Central Admin API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
inference = MuRILInferenceService()
incidents: list[dict[str, Any]] = []
whitelist: list[dict[str, str]] = []


class LoginRequest(BaseModel):
    username: str
    password: str


class IncidentRequest(BaseModel):
    url: HttpUrl
    clean_url: str | None = Field(default=None, max_length=2048)
    screenshot_base64: str | None = None
    dom_snapshot: str | None = Field(default=None, max_length=100_000)
    dom_signature: str | None = None
    browser: dict[str, Any] = Field(default_factory=dict)
    message: str = Field(default="", max_length=20_000)
    threat_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = Field(default="extension", max_length=40)


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
    return base64.b64encode(data).decode("ascii")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "online", "service": "guardain-api"}


@app.get("/", response_class=HTMLResponse)
async def portal() -> str:
    path = Path(__file__).resolve().parents[2] / "admin_portal" / "index.html"
    return path.read_text(encoding="utf-8")


@app.post("/v1/admin/login")
async def admin_login(payload: LoginRequest) -> dict[str, str]:
    if payload.username != settings.admin_username or not verify_password(
        payload.password, settings.admin_password_hash
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_access_token(payload.username), "token_type": "bearer"}


@app.get("/v1/verify")
async def verify(message: str = "", url: str = "") -> dict[str, Any]:
    result = await inference.predict(f"{message} {url}".strip())
    return {"url": url, "threat_score": result["score"], **result}


async def _enrich(incident: dict[str, Any]) -> None:
    incident["whois"] = await analyze_domain(incident["url"])
    incident["payload"]["whois"] = incident["whois"]


@app.post("/v1/report/incident", status_code=202)
async def report_incident(payload: IncidentRequest, tasks: BackgroundTasks) -> dict[str, Any]:
    dom = payload.dom_snapshot or ""
    incident = payload.model_dump(mode="json")
    incident.update({
        "id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "screenshot_base64": _safe_screenshot(payload.screenshot_base64),
        "dom_signature": payload.dom_signature or hashlib.sha256(dom.encode()).hexdigest(),
    })
    if not incident["threat_score"] and payload.message:
        prediction = await inference.predict(payload.message)
        incident["threat_score"] = prediction["score"]
        incident["analysis"] = prediction
    incident["payload"] = {
        "url": incident["url"],
        "clean_url": incident.get("clean_url"),
        "screenshot_base64": incident.get("screenshot_base64"),
        "dom_signature": incident["dom_signature"],
        "browser": incident.get("browser", {}),
        "whois": incident.get("whois"),
    }
    incidents.insert(0, incident)
    del incidents[settings.max_incidents:]
    tasks.add_task(_enrich, incident)
    return {"incident_id": incident["id"], "status": "accepted"}


@app.get("/v1/admin/incidents")
async def admin_incidents(_: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    return {"incidents": incidents}


@app.get("/v1/admin/whitelist")
async def admin_whitelist(_: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    return {"entries": whitelist}


class WhitelistRequest(BaseModel):
    value: str = Field(min_length=1, max_length=2048)
    reason: str = Field(default="Operator review", max_length=500)


@app.post("/v1/admin/whitelist")
async def add_whitelist(payload: WhitelistRequest, _: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    entry = payload.model_dump()
    whitelist.append(entry)
    return entry


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
