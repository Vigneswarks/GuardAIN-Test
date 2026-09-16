"""Privacy and authentication primitives used by every GuardAIN surface."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

try:
    import jwt
except ImportError:  # pragma: no cover
    jwt = None

from .config import settings


def sha256_hash(value: Any) -> str:
    """Return a deterministic, normalized SHA-256 digest for lookup/storage."""
    normalized = unicodedata.normalize("NFKC", "" if value is None else str(value)).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s.-]?)?[6-9]\d{4}[\s.-]?\d{5}(?!\d)")
AADHAAR_RE = re.compile(r"(?<!\d)(?:\d{4}[\s-]?){2}\d{4}(?!\d)")
CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
BANK_ACCOUNT_RE = re.compile(
    r"(?i)(?:account(?:\s*(?:no|number))?|a/c|acct|iban)\s*[:=#-]?\s*([0-9]{8,20})"
)
UPI_RE = re.compile(r"(?i)(?:(?:upi|vpa|virtual\s*payment\s*address)\s*[:=]?\s*)?"
                    r"([a-zA-Z0-9][a-zA-Z0-9._-]{1,254}@[a-zA-Z0-9.-]{2,})")
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PAN_RE = re.compile(r"(?i)\b[A-Z]{5}[0-9]{4}[A-Z]\b")


def _valid_card(raw: str) -> bool:
    digits = re.sub(r"\D", "", raw)
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total, parity = 0, len(digits) % 2
    for index, char in enumerate(digits):
        value = int(char)
        if index % 2 == parity:
            value *= 2
            value = value - 9 if value > 9 else value
        total += value
    return total % 10 == 0


def redact_text(value: Any) -> str:
    """Redact Indian PII and payment identifiers without retaining source data."""
    text = unicodedata.normalize("NFKC", "" if value is None else str(value))
    text = PHONE_RE.sub("[PHONE]", text)
    # Card first: otherwise a spaced 16-digit card can expose its final group
    # after the Aadhaar expression matches the first twelve digits.
    text = CARD_RE.sub(lambda match: "[CARD]" if _valid_card(match.group(0)) else match.group(0), text)
    text = AADHAAR_RE.sub("[AADHAAR]", text)
    text = BANK_ACCOUNT_RE.sub("[BANK_ACCOUNT]", text)
    text = UPI_RE.sub("[UPI]", text)
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = PAN_RE.sub("[PAN]", text)
    return text


def scrub_text(value: Any) -> str:
    return redact_text(value)


redact_pii = redact_text


def scrub_object(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): scrub_object(item) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub_object(item) for item in value]
    if isinstance(value, tuple):
        return tuple(scrub_object(item) for item in value)
    return redact_text(value) if isinstance(value, str) else value


def hash_sensitive_fields(payload: Any, fields: Iterable[str] | None = None) -> Any:
    names = {name.lower() for name in (fields or {
        "phone", "mobile", "aadhaar", "card", "card_number", "account_number",
        "bank_account", "account", "ifsc", "upi", "vpa", "upi_id",
        "vpa_handle",
    })}
    if isinstance(payload, dict):
        return {
            key: sha256_hash(value) if isinstance(key, str) and key.lower() in names
            else hash_sensitive_fields(value, names)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [hash_sensitive_fields(item, names) for item in payload]
    return payload


def sanitize_for_backend(payload: Any) -> Any:
    return hash_sensitive_fields(scrub_object(payload))


def normalize_for_lookup(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", "" if value is None else str(value)).strip().lower()
    return re.sub(r"\s+", "", normalized)


def build_blacklist_hash(value: Any) -> str:
    return sha256_hash(normalize_for_lookup(value))


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def create_access_token(subject: str, role: str = "client",
                        expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    expiry = now + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))
    payload = {"sub": subject, "role": role, "iat": int(now.timestamp()), "exp": int(expiry.timestamp())}
    if jwt is not None:
        return str(jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm))
    header = _b64(json.dumps({"alg": settings.jwt_algorithm, "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64(hmac.new(settings.jwt_secret_key.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest())
    return f"{header}.{body}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    if not token or not isinstance(token, str):
        raise ValueError("Missing token")
    try:
        if jwt is not None:
            return dict(jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]))
        first, second, signature = token.split(".")
        expected = _b64(hmac.new(settings.jwt_secret_key.encode(), f"{first}.{second}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        payload = json.loads(base64.urlsafe_b64decode(second + "=" * (-len(second) % 4)))
        if float(payload.get("exp", 0)) < time.time():
            raise ValueError("Expired token")
        return payload
    except Exception as exc:
        raise ValueError("Invalid authentication token") from exc


def verify_access_token(token: str, required_role: str | None = None) -> dict[str, Any]:
    payload = decode_access_token(token)
    if required_role and payload.get("role") != required_role:
        raise ValueError("Insufficient role")
    return payload


# Short aliases used by integrations and older clients.
generate_jwt = create_access_token
validate_jwt = decode_access_token
