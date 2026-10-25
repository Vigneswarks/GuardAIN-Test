"""Shared DPDP-safe redaction for client and server boundaries."""
from __future__ import annotations

import re

_PATTERNS = (
    (re.compile(r"(?<!\d)(?:\+?91[\s.-]?)?[6-9]\d{4}[\s.-]?\d{5}(?!\d)"), "[PHONE]"),
    (re.compile(r"(?<!\d)(?:\d{4}[\s-]?){2}\d{4}(?!\d)"), "[AADHAAR]"),
    (re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"), "[CARD]"),
)


def redact_pii(value: str) -> str:
    result = str(value or "")
    for pattern, replacement in _PATTERNS:
        result = pattern.sub(replacement, result)
    return result
