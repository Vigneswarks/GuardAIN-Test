"""Regression tests for costly false blocks and poisoned shared reputation."""
from backend.app.risk_policy import page_decision


def test_keywords_do_not_block():
    assert page_decision('awareness.example', {'coercion': True})['action'] == 'ALLOW'
    assert page_decision('fraud-awareness.example', {})['action'] == 'ALLOW'


def test_collection_needs_corroboration():
    assert page_decision('bank.example', {'credential_form': True})['action'] == 'ALLOW'
    assert page_decision('shop.example', {'payment_request': True, 'insecure_form': True})['action'] == 'REVIEW'
    assert page_decision('unknown.example', dict(credential_form=True, coercion=True, urgent_demand=True, cross_origin_form=True))['action'] == 'BLOCK'


def test_safe_domain_boundary():
    signals = dict(credential_form=True, coercion=True, urgent_demand=True, cross_origin_form=True)
    for domain in ['google.com', 'www.google.com', 'GOOGLE.COM.', 'nic.in', 'services.gov.in']:
        assert page_decision(domain, signals, 'malicious')['action'] == 'ALLOW'
    assert page_decision('google.com.attacker.example', signals)['action'] == 'BLOCK'


def test_only_confirmed_reviews_block():
    assert page_decision('unknown.example', {}, 'pending')['action'] == 'ALLOW'
    assert page_decision('unknown.example', {}, 'malicious')['action'] == 'BLOCK'
    assert page_decision('unknown.example', {}, 'safe')['action'] == 'ALLOW'
