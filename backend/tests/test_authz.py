"""
Role capability enforcement.

The platform's claim is that a party's position decides what they may do, not
only what they may see. These tests hold the two apart: a buyer is refused the
owner's actions by *role*, and is refused a payment by transaction *state* — two
different mechanisms that must not be confused with each other.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

CLEAN = "LTC-PR-0001"   # PROCEED — nothing is blocked by state here
HELD = "LTC-PR-0002"    # HOLD — payment is blocked by state, for everyone

OWNER = {"X-Demo-Role": "OWNER"}
BUYER = {"X-Demo-Role": "BUYER"}
VERIFIER = {"X-Demo-Role": "VERIFIER"}
LEGAL = {"X-Demo-Role": "LEGAL_REVIEWER"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _upload(client, headers, name="authz_probe.txt"):
    return client.post(
        "/api/documents/upload",
        data={"property_id": CLEAN, "mode": "DEMO"},
        files={"file": (name, b"Owner Name: Ravi Kumar\nSurvey No: 142/3A\n", "text/plain")},
        headers=headers,
    )


# --------------------------------------------------------------- adding evidence

def test_buyer_cannot_upload_evidence(client):
    r = _upload(client, BUYER)
    assert r.status_code == 403
    assert "owner" in r.json()["detail"].lower()


def test_owner_may_upload_evidence(client):
    assert _upload(client, OWNER, "authz_owner_probe.txt").status_code == 200


def test_verifier_cannot_upload_evidence(client):
    """A verifier examines what is on file; they are not the source of it."""
    assert _upload(client, VERIFIER, "authz_verifier_probe.txt").status_code == 403


# ------------------------------------------------------------------ recomputing

def test_buyer_cannot_reassess(client):
    assert client.post(f"/api/properties/{CLEAN}/reassess", headers=BUYER).status_code == 403


def test_verifier_may_reassess(client):
    assert client.post(f"/api/properties/{CLEAN}/reassess", headers=VERIFIER).status_code == 200


# ----------------------------------------------------------------- transacting

def test_owner_cannot_attempt_a_transaction(client):
    r = client.post(f"/api/transactions/{CLEAN}/attempt/INITIATE_PAYMENT", headers=OWNER)
    assert r.status_code == 403
    assert "buyer" in r.json()["detail"].lower()


def test_buyer_is_refused_by_state_rather_than_by_role(client):
    """
    The distinction that matters: this is a 200 carrying a refusal, not a 403.
    The buyer is entitled to try; the evidence is what stops them.
    """
    r = client.post(f"/api/transactions/{HELD}/attempt/INITIATE_PAYMENT", headers=BUYER)
    assert r.status_code == 200
    assert r.json()["allowed"] is False


# --------------------------------------------------------------------- consent

def test_owner_cannot_request_access_to_their_own_property(client):
    r = client.post("/api/consent", headers=OWNER, json={
        "property_id": CLEAN, "items": ["LATEST_EC"], "purpose": "probe"})
    assert r.status_code == 403


def test_buyer_requests_and_only_the_owner_decides(client):
    created = client.post("/api/consent", headers=BUYER, json={
        "property_id": CLEAN, "items": ["LATEST_EC"], "purpose": "authz probe"})
    assert created.status_code == 200
    request_id = created.json()["request"]["id"]

    refused = client.post(f"/api/consent/{request_id}/decision", headers=BUYER,
                          json={"approve": True})
    assert refused.status_code == 403

    allowed = client.post(f"/api/consent/{request_id}/decision", headers=OWNER,
                          json={"approve": True})
    assert allowed.status_code == 200


# ------------------------------------------------------------------- resolution

def test_legal_reviewer_examines_but_does_not_clear(client):
    r = client.post("/api/resolution/apply", headers=LEGAL,
                    json={"property_id": HELD, "action_key": "OBTAIN_CURRENT_EC"})
    assert r.status_code == 403


def test_simulation_is_open_to_everyone_because_it_writes_nothing(client):
    r = client.post("/api/resolution/simulate", headers=BUYER,
                    json={"property_id": HELD, "action_keys": ["OBTAIN_CURRENT_EC"]})
    assert r.status_code == 200


# ---------------------------------------------------------------- demo control

def test_only_an_administrator_rebuilds_the_demonstration(client):
    assert client.post("/api/demo/reset", headers=BUYER).status_code == 403


# ------------------------------------------------- the table the UI is given

def test_capability_table_is_published_and_matches_enforcement(client):
    caps = client.get("/api/roles").json()["capabilities"]
    assert "UPLOAD_EVIDENCE" in caps["OWNER"]["capabilities"]
    assert "UPLOAD_EVIDENCE" not in caps["BUYER"]["capabilities"]
    assert "ATTEMPT_TRANSACTION" in caps["BUYER"]["capabilities"]
    assert "ATTEMPT_TRANSACTION" not in caps["OWNER"]["capabilities"]
    # Every denial carries the sentence the interface shows, so a disabled
    # control can always explain itself.
    for role in caps.values():
        assert all(reason for reason in role["denied"].values())
