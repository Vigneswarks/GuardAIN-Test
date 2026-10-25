"""Page actions require corroborating evidence; scores alone never close tabs."""
SAFE_DOMAINS = ("google.com", "google.co.in", "bing.com", "duckduckgo.com",
                "thehindu.com", "timesofindia.indiatimes.com", "gov.in", "nic.in")


def safe_domain(host: str) -> bool:
    host = host.lower().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in SAFE_DOMAINS)


def page_decision(host: str, signals: dict, review: str | None = None) -> dict:
    if safe_domain(host) or review == "safe":
        return dict(action="ALLOW", score=0.0, reasons=["safe_domain_bypass"])
    if review == "malicious":
        return dict(action="BLOCK", score=0.99, reasons=["analyst_confirmed_domain"])
    # A lexical mention, TLD, or model probability cannot independently block.
    collection = signals.get("credential_form") or signals.get("payment_request")
    coercion = signals.get("coercion") and signals.get("urgent_demand")
    url_evidence = signals.get("insecure_form") or signals.get("cross_origin_form")
    if collection and coercion and url_evidence:
        return dict(action="BLOCK", score=0.92, reasons=["coercive_demand", "collection_form", "unsafe_form_destination"])
    if collection and (coercion or url_evidence):
        return dict(action="REVIEW", score=0.6, reasons=["corroborated_warning"])
    return dict(action="ALLOW", score=0.1, reasons=["insufficient_blocking_evidence"])
