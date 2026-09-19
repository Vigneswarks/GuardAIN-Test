from __future__ import annotations

import asyncio
import socket
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

try:
    import whois
except ImportError:  # pragma: no cover
    whois = None


def _iso(value: Any) -> str | None:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple)) and value:
        return _iso(value[0])
    return str(value) if value else None


def _lookup(domain: str) -> dict[str, Any]:
    result: dict[str, Any] = {"domain": domain, "creation_date": None, "expiry_date": None,
                              "registrar": None, "name_servers": [], "host_ip": None}
    try:
        result["host_ip"] = socket.gethostbyname(domain)
    except socket.gaierror:
        pass
    if whois is None:
        return result
    try:
        record = whois.whois(domain)
        result.update({
            "creation_date": _iso(getattr(record, "creation_date", None)),
            "expiry_date": _iso(getattr(record, "expiration_date", None)),
            "registrar": getattr(record, "registrar", None),
            "name_servers": sorted({str(item).lower() for item in (getattr(record, "name_servers", None) or [])}),
        })
    except Exception as exc:  # lookup failures must not fail incident intake
        result["error"] = str(exc)
    return result


async def analyze_domain(url: str) -> dict[str, Any]:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    domain = (parsed.hostname or "").lower().strip(".")
    if not domain:
        return {"domain": None, "error": "URL has no hostname"}
    return await asyncio.to_thread(_lookup, domain)
