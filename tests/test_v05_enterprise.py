"""Tests for the v0.5 enterprise control-plane features.

Covers: tenant isolation context, append-only event store, KMS signing,
rate limiting, authorization scopes, and domain control packs.
"""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from second_perspective.api.authz import authz_enforced, require_scope
from second_perspective.api.ratelimit import RateLimitMiddleware, _Bucket
from second_perspective.domain import (
    FinanceRiskControlPack,
    get_registry,
    register_default_packs,
)
from second_perspective.domain.base import DomainViolation
from second_perspective.persistence.event_store import (
    DomainEvent,
    InMemoryEventStore,
)
from second_perspective.security.kms import LocalKmsSigner
from second_perspective.service import DecisionService
from second_perspective.tenant import get_tenant, reset_tenant, set_tenant

EXAMPLE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "examples", "market_entry.json"
)


def _load_request():
    from second_perspective.models.schemas import DecisionRequest

    with open(EXAMPLE_PATH, encoding="utf-8") as fh:
        return DecisionRequest.model_validate(json.load(fh))


# ── Tenant isolation ────────────────────────────────────────────────────────


def test_tenant_context_roundtrip():
    token = set_tenant("acme")
    assert get_tenant() == "acme"
    reset_tenant(token)
    assert get_tenant() == ""


# ── Event store ─────────────────────────────────────────────────────────────


def test_event_store_hash_chain_and_tenant_filter():
    store = InMemoryEventStore()
    assert store.last_hash("") == ""

    e1 = DomainEvent.create("decision.evaluated", "d1", {"r": 1}, "")
    e2 = DomainEvent.create("decision.approved", "d1", {"r": 2}, e1.event_hash)
    store.append(e1)
    store.append(e2)

    # Hash chaining integrity.
    assert e2.prev_hash == e1.event_hash
    assert e2.event_hash != e1.event_hash
    assert store.last_hash("") == e2.event_hash

    # Tenant partitioning.
    store.append(DomainEvent.create("decision.evaluated", "d2", {}, "", tenant_id="t1"))
    assert len(store.stream(tenant_id="t1")) == 1
    assert len(store.stream(tenant_id="")) == 2
    assert len(store.stream(aggregate_id="d1")) == 2


# ── KMS signing ────────────────────────────────────────────────────────────


def test_kms_signer_roundtrip_and_noop_when_unconfigured():
    # Unconfigured: transparent no-op.
    s0 = LocalKmsSigner(secret="")
    assert not s0.is_configured()
    assert s0.sign(b"payload") == ""
    assert not s0.verify(b"payload", "anything")

    # Configured: deterministic sign + verify.
    signer = LocalKmsSigner(secret="super-secret-key")
    assert signer.is_configured()
    sig = signer.sign(b"hello")
    assert sig
    assert signer.verify(b"hello", sig)
    assert not signer.verify(b"hello", sig[:-1] + ("0" if sig[-1] != "0" else "1"))
    assert not signer.verify(b"tampered", sig)


# ── Rate limiting ──────────────────────────────────────────────────────────


def test_rate_limit_bucket_refills():
    bucket = _Bucket(rate=1.0, capacity=2.0)
    assert bucket.allow()  # 1
    assert bucket.allow()  # 2 (capacity)
    assert not bucket.allow()  # exhausted
    # After enough time elapses, tokens refill.
    bucket.last -= 2.0
    assert bucket.allow()


def test_rate_limit_middleware_disabled_passthrough():
    mw = RateLimitMiddleware(app=_noop_app(), rate_per_minute=0)
    import asyncio

    async def run():
        return await mw.__call__(_fake_request(), _call_next_ok())

    asyncio.run(run())


def _noop_app():
    def app(scope, receive, send):
        pass

    return app


def _fake_request():
    class R:
        headers = {}
        client = None
        url = type("U", (), {"path": "/"})()

    return R()


def _call_next_ok():
    async def call(request):
        class Resp:
            status_code = 200
            headers = {}

        return Resp()

    return call


# ── Authorization scopes ───────────────────────────────────────────────────


def test_require_scope_passthrough_when_not_enforced():
    assert not authz_enforced()

    class Req:
        state = type("S", (), {"oidc_claims": None})()

    # No-op when enforcement is off regardless of scopes.
    require_scope("decisions:write")(Req())


def test_require_scope_403_when_enforced_and_missing(monkeypatch):
    monkeypatch.setenv("SP_AUTHZ_ENFORCE", "true")
    try:
        from second_perspective.api import main

        client = TestClient(main.app)
        payload = json.loads(open(EXAMPLE_PATH, encoding="utf-8").read())
        resp = client.post("/v1/decisions/evaluate", json=payload)
        assert resp.status_code == 403
        assert "scope" in resp.json()["detail"].lower()
    finally:
        monkeypatch.delenv("SP_AUTHZ_ENFORCE", raising=False)


# ── Domain control packs ───────────────────────────────────────────────────


def test_finance_risk_control_pack_flags_multi_alt_no_owner():
    from second_perspective.domain.packs import FinanceRiskControlPack

    pack = FinanceRiskControlPack()
    request = _load_request()  # has 2 alternatives, no top-level responsibility
    violations = pack.validate(request)
    assert any(v.code == "NO_EXPLICIT_RISK_OWNER" for v in violations)
    assert all(isinstance(v, DomainViolation) for v in violations)


def test_domain_pack_registry_and_service_default_packs():
    register_default_packs()
    assert any(
        p.id == "finance-risk-control" for p in get_registry().all()
    )


# ── Service event emission ─────────────────────────────────────────────────


def test_service_emits_event_on_evaluate():
    from second_perspective.repository import InMemoryDecisionRepository

    event_store = InMemoryEventStore()
    service = DecisionService(
        repository=InMemoryDecisionRepository(),
        event_store=event_store,
        domain_packs=[],
    )
    record = service.evaluate(_load_request())
    events = event_store.stream(aggregate_id=record.result.decision_id)
    assert len(events) == 1
    assert events[0].event_type == "decision.evaluated"
    assert events[0].payload["record_hash"] == record.record_hash
