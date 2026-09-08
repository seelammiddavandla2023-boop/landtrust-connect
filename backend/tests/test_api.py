"""
API tests, with an emphasis on the guarantees the UI is not allowed to break:
masking, consent, grounding and the enforcement of transaction state.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain import DisclosureItem
from app.main import app

REFERENCE = "LTC-PR-0002"
BUYER = {"X-Demo-Role": "BUYER"}
OWNER = {"X-Demo-Role": "OWNER"}
VERIFIER = {"X-Demo-Role": "VERIFIER"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
def test_health_reports_which_extraction_backends_are_usable(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["extraction_backends"]["DEMO"]["available"] is True
    assert "disclaimer" in body


def test_property_listing_and_filtering(client):
    body = client.get("/api/properties").json()
    assert body["count"] == 6
    held = client.get("/api/properties?state=HOLD").json()
    assert all(p["transaction_state"] == "HOLD" for p in held["items"])
    searched = client.get("/api/properties?q=thiruporur").json()
    assert searched["count"] >= 1


def test_unknown_property_is_a_clean_404(client):
    r = client.get("/api/properties/does-not-exist")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Masking is enforced server-side, not in the browser.
# ---------------------------------------------------------------------------
def test_buyer_cannot_retrieve_a_masked_owner_name(client):
    body = client.get(f"/api/properties/{REFERENCE}/claims", headers=BUYER).json()
    owner_claims = [c for c in body["items"] if c["claim_type"] == "owner_name"]
    assert owner_claims, "the file must contain owner-name claims"
    for c in owner_claims:
        assert c["masked"] is True
        assert "*" in c["value"], "a masked name must not carry the real value"
        assert "Priya Sharma" not in c["value"]
        # The span would leak the value, so it must be withheld too.
        assert c["source_span"] is None


def test_verifier_sees_the_full_value(client):
    body = client.get(f"/api/properties/{REFERENCE}/claims", headers=VERIFIER).json()
    owner_claims = [c for c in body["items"] if c["claim_type"] == "owner_name"]
    assert any(c["masked"] is False for c in owner_claims)


def test_identity_numbers_are_never_disclosed_to_a_buyer(client):
    """
    Restricted attributes come back reduced, each in the way that attribute needs:
    an identity number to its last four characters, a phone to its last four digits,
    an address to its locality. What they have in common is that the buyer cannot
    reconstruct the original from what they are given.
    """
    buyer_view = client.get("/api/properties/LTC-PR-0001/claims", headers=BUYER).json()
    full_view = client.get("/api/properties/LTC-PR-0001/claims", headers=VERIFIER).json()
    originals = {c["id"]: c["value"] for c in full_view["items"]}

    restricted = [
        c for c in buyer_view["items"]
        if c["claim_type"] in {"identity_number", "owner_phone", "owner_address"}
    ]
    assert restricted, "the corpus must contain restricted attributes to test against"

    import re

    for c in restricted:
        assert c["masked"] is True
        assert c["mask_reason"], "a masked value must explain why it is masked"

        if c["claim_type"] == "owner_address":
            # Reduced to the locality: the postcode may remain, the street may not.
            assert "Second Cross Street" not in c["value"]
            assert c["value"] != originals.get(c["id"]), "the address was not reduced"
        elif c["claim_type"] == "owner_phone":
            assert "9840112233" not in c["value"]
            assert c["value"] != originals.get(c["id"]), "the phone number was not reduced"
            assert not re.search(r"\d{5,}", c["value"].replace(" ", "")), (
                f"a dialable number survived masking: {c['value']}"
            )
        elif c["claim_type"] == "identity_number":
            # The synthetic identity document is itself only partial — the platform never
            # holds a full number to leak. Confirm that remains true end to end.
            assert c["value"].count("X") >= 4
            assert not re.search(r"\d{5,}", c["value"].replace(" ", ""))


def test_identity_documents_cannot_be_requested_even_by_asking(client):
    catalogue = client.get("/api/consent/items").json()
    identity = next(
        i for i in catalogue["items"] if i["item"] == DisclosureItem.IDENTITY_DOCUMENT.value
    )
    assert identity["requestable"] is False

    created = client.post(
        "/api/consent",
        headers=BUYER,
        json={
            "property_id": REFERENCE,
            "items": [DisclosureItem.IDENTITY_DOCUMENT.value,
                      DisclosureItem.LATEST_EC.value],
            "purpose": "test",
        },
    ).json()
    assert created["notice"], "the buyer must be told identity documents are excluded"

    # Even an owner approving everything cannot release it.
    request_id = created["request"]["id"]
    decided = client.post(
        f"/api/consent/{request_id}/decision",
        headers=OWNER,
        json={"approve": True},
    ).json()
    granted = {i["item"] for i in decided["granted_items"]}
    denied = {i["item"] for i in decided["denied_items"]}
    assert DisclosureItem.IDENTITY_DOCUMENT.value not in granted
    assert DisclosureItem.IDENTITY_DOCUMENT.value in denied
    assert DisclosureItem.LATEST_EC.value in granted, (
        "withholding the identity document must not block the legitimate request"
    )


# ---------------------------------------------------------------------------
# The evidence gate
# ---------------------------------------------------------------------------
def test_gated_profile_separates_verified_from_owner_provided(client):
    body = client.get(f"/api/properties/LTC-PR-0004/profile", headers=BUYER).json()
    sections = body["sections"]
    assert sections["verified"], "a clean attribute should be in the verified section"
    owner_provided = [f["claim_type"] for f in sections["owner_provided"]]
    assert "mortgage_status" in owner_provided, (
        "an owner's unsupported 'no encumbrance' claim must not sit among verified facts"
    )
    for field in sections["verified"]:
        assert field["verification_status"] == "VERIFIED"


def test_pending_attributes_are_shown_rather_than_omitted(client):
    body = client.get(f"/api/properties/LTC-PR-0003/profile", headers=BUYER).json()
    pending = [f["claim_type"] for f in body["sections"]["pending"]]
    assert pending, "an attribute with no evidence must be shown as pending, not hidden"


# ---------------------------------------------------------------------------
# Transaction state enforcement
# ---------------------------------------------------------------------------
def test_blocked_action_is_refused_with_a_reason(client):
    r = client.post(f"/api/transactions/{REFERENCE}/attempt/INITIATE_PAYMENT", headers=BUYER)
    body = r.json()
    assert body["allowed"] is False
    assert body["state"] == "HOLD"
    assert len(body["reason"]) > 40
    assert "payment" in body["note"].lower()


def test_applying_a_resolution_step_is_a_privileged_action(client):
    """
    Applying a step changes the evidence set and can move a held transaction toward
    PROCEED. A buyer — or an unauthenticated caller, who defaults to the buyer role —
    must not be able to do that to someone else's file.
    """
    body = {"property_id": "LTC-PR-0002", "action_key": "OBTAIN_BANK_NOC"}

    refused = client.post("/api/resolution/apply", headers=BUYER, json=body)
    assert refused.status_code == 403
    assert "owner" in refused.json()["detail"].lower()

    # No header at all resolves to BUYER and must be refused the same way.
    anonymous = client.post("/api/resolution/apply", json=body)
    assert anonymous.status_code == 403

    # And the refusal must have changed nothing.
    risk = client.get("/api/properties/LTC-PR-0002/risk").json()
    assert risk["state"] == "HOLD"


def test_permitted_action_on_a_clean_file(client):
    body = client.post(
        "/api/transactions/LTC-PR-0001/attempt/PROCEED_TO_AGREEMENT", headers=BUYER
    ).json()
    assert body["allowed"] is True
    assert body["state"] == "PROCEED"


# ---------------------------------------------------------------------------
# The relay redacts before delivery
# ---------------------------------------------------------------------------
def test_relay_removes_contact_details_before_delivering_a_message(client):
    body = client.post(
        "/api/messages",
        headers=OWNER,
        json={
            "property_id": "LTC-PR-0006",
            "body": "Call me on 9840112233 or email seller@example.com, my PAN is ABCDE1234F.",
        },
    ).json()
    delivered = body["message"]["body"]
    assert "9840112233" not in delivered
    assert "seller@example.com" not in delivered
    assert "ABCDE1234F" not in delivered
    assert body["message"]["contained_sensitive"] is True
    assert set(body["message"]["sensitive_kinds"]) >= {"PHONE", "EMAIL"}
    assert body["warning"]


# ---------------------------------------------------------------------------
# The assistant
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "question",
    [
        "Who is the verified owner?",
        "Why is the area marked conflicting?",
        "Which document contains the mortgage?",
        "What evidence is still missing?",
    ],
)
def test_answerable_questions_are_grounded(client, question):
    body = client.post(
        "/api/assistant/ask", headers=BUYER,
        json={"property_id": REFERENCE, "question": question},
    ).json()
    assert body["kind"] == "GROUNDED", f"{question} → {body['kind']}: {body['answer']}"
    assert body["answer"]
    assert body["disclaimer"]


@pytest.mark.parametrize(
    "question",
    [
        "What will this property be worth in 2030?",
        "Should I buy this property?",
        "Who is the neighbouring plot's owner?",
        "What is the seller's bank account number?",
        "How many trees are on the property?",
        "Can you certify that this title is legally valid?",
    ],
)
def test_unanswerable_questions_are_refused(client, question):
    body = client.post(
        "/api/assistant/ask", headers=BUYER,
        json={"property_id": REFERENCE, "question": question},
    ).json()
    assert body["kind"] in {"REFUSED", "OUT_OF_SCOPE"}, (
        f"{question} was answered: {body['answer']}"
    )
    # A refusal must not smuggle the file's contents out anyway.
    assert "Priya" not in body["answer"]


def test_the_assistant_never_claims_legal_verification(client):
    body = client.post(
        "/api/assistant/ask", headers=BUYER,
        json={"property_id": "LTC-PR-0001", "question": "Who is the verified owner?"},
    ).json()
    lowered = body["answer"].lower()
    assert "legally verified" not in lowered
    assert "guaranteed" not in lowered


def test_every_grounded_claim_answer_cites_a_document_and_page(client):
    body = client.post(
        "/api/assistant/ask", headers=BUYER,
        json={"property_id": REFERENCE, "question": "Who is the verified owner?"},
    ).json()
    assert body["evidence"], "a grounded answer must cite its evidence"
    for ref in body["evidence"]:
        assert ref["document_name"]
        assert ref["page"] is None or ref["page"] >= 1


# ---------------------------------------------------------------------------
# Provenance and simulation
# ---------------------------------------------------------------------------
def test_claim_evidence_returns_the_source_page_and_region(client):
    claims = client.get(f"/api/properties/{REFERENCE}/claims", headers=VERIFIER).json()
    area = next(c for c in claims["items"] if c["claim_type"] == "property_area")
    body = client.get(
        f"/api/properties/{REFERENCE}/claims/{area['id']}/evidence", headers=VERIFIER
    ).json()
    assert body["source"]["page"] >= 1
    assert body["source"]["page_text"], "the drawer must be able to show the source page"
    assert body["source"]["region"].get("w")
    assert body["conflicting"], "the 1650 sq.ft assertion must appear as conflicting evidence"


def test_simulation_writes_nothing(client):
    before = client.get(f"/api/properties/{REFERENCE}/risk").json()
    sim = client.post(
        "/api/resolution/simulate",
        json={"property_id": REFERENCE, "action_keys": ["OBTAIN_BANK_NOC"]},
    ).json()
    assert sim["after"]["overall_score"] < sim["before"]["overall_score"]
    assert "ACTIVE_MORTGAGE" in sim["resolved_rules"]

    after = client.get(f"/api/properties/{REFERENCE}/risk").json()
    assert after["overall_score"] == before["overall_score"], (
        "a simulation must not change the stored assessment"
    )


def test_graph_and_timeline_are_evidence_backed(client):
    body = client.get("/api/properties/LTC-PR-0001/graph").json()
    assert body["nodes"] and body["edges"]
    assert body["current_owner"]
    assert body["chain_complete"] is True
    dated = [t for t in body["timeline"] if t["evidence"]]
    assert dated, "timeline entries must cite the document that evidences them"


def test_research_endpoints_are_available(client):
    gap = client.get("/api/research/gap").json()
    assert len(gap["rows"]) == 5
    assert "rarely combine" in gap["novelty_wording"]

    arch = client.get("/api/research/architecture").json()
    assert len(arch["layers"]) == 5
    statuses = {c["status"] for layer in arch["layers"] for c in layer["components"]}
    assert statuses <= {"WORKING", "PROTOTYPE", "REVIEW_3"}


def test_metrics_endpoint_returns_computed_results(client):
    r = client.get("/api/research/metrics")
    if r.status_code == 404:
        pytest.skip("evaluation has not been run; `python -m app.eval.run_eval`")
    body = r.json()
    assert body["headline"]["documents_tested"] > 0
    assert body["meta"]["caveat"], "the metrics must ship with their own caveat"
