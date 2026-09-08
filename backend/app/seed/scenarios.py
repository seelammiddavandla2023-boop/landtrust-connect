"""
The synthetic evaluation corpus.

Six properties spanning the risk spectrum, each with a documented anomaly profile
and an expected outcome.  The expectations recorded here are the **ground truth**
used by `app/eval/run_eval.py`: extraction accuracy, contradiction precision and
recall, verification agreement and transaction-state accuracy are all measured
against these declarations, not asserted.

Every name, survey number, document number and institution is fictitious.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..domain import (
    ClaimType,
    ContradictionType,
    DocumentType,
    TransactionState,
    VerificationStatus,
)
from .documents import DocSpec, Field, Para, Tamper, recitals_for

TODAY = date(2026, 9, 7)


@dataclass
class DocPlan:
    spec: DocSpec
    # claim_type -> expected extracted value (the answer key for extraction accuracy)
    expected_claims: dict[str, str] = field(default_factory=dict)
    anomalies: list[str] = field(default_factory=list)


@dataclass
class ScenarioPlan:
    key: str
    label: str
    reference: str
    survey_number: str
    district: str
    village: str
    property_type: str
    claimed_area_sqft: float
    guideline_value_inr: float
    asking_price_inr: float
    listed_owner_name: str
    owner_name: str
    owner_email: str
    owner_phone: str
    owner_identity: str
    summary: str
    documents: list[DocPlan] = field(default_factory=list)
    expected_state: TransactionState = TransactionState.PROCEED
    expected_risk_band: str = "LOW"
    expected_statuses: dict[str, VerificationStatus] = field(default_factory=dict)
    expected_contradiction_types: list[str] = field(default_factory=list)
    injected_anomalies: list[str] = field(default_factory=list)
    demo_note: str = ""
    # Whether uploading further evidence can, in principle, reach PROCEED. Where
    # ownership itself is contradicted the correct outcome is escalation to an
    # authorised reviewer, and a plan that stops short of PROCEED is right, not a
    # failure — the evaluation harness scores those cases separately.
    expected_resolvable: bool = True


def _d(day: int, month: int, year: int) -> str:
    return f"{day:02d}-{month:02d}-{year}"


# ===========================================================================
# CASE A — clean, consistent title with a full chain
# ===========================================================================
def case_a() -> ScenarioPlan:
    owner = "Ravi Kumar"
    survey = "142/3A"
    area = "2400 sq.ft"

    deed_2017 = DocPlan(
        DocSpec(
            filename="Sale_Deed_2017_Rajesh_to_Mohan.pdf",
            doc_type=DocumentType.SALE_DEED,
            title="DEED OF SALE",
            authority="Office of the Sub-Registrar, Katpadi, Vellore District",
            reference="DOC-2017-20914",
            issued_on=date(2017, 8, 11),
            pages=2,
            fields=[
                Field("Document Number", "DOC-2017-20914", 1),
                Field("Date of Registration", _d(11, 8, 2017), 1),
                Field("Vendor / Transferor", "Rajesh Kumar", 1),
                Field("Purchaser / Transferee", "Mohan Reddy", 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", area, 1),
                Field("District", "Vellore", 1),
                Field("Village", "Sathuvachari", 1),
                Field("Sale Consideration", "Rs. 24,00,000", 2),
                Field("Boundaries", "North: Survey 142/2; South: Road; East: 142/3B; West: Canal", 2),
            ],
            paragraphs=recitals_for(DocumentType.SALE_DEED, 2, seed=17),
            seal_text="Sub-Registrar, Katpadi",
        ),
        expected_claims={
            ClaimType.DOCUMENT_NUMBER.value: "DOC-2017-20914",
            ClaimType.REGISTRATION_DATE.value: _d(11, 8, 2017),
            ClaimType.SELLER_NAME.value: "Rajesh Kumar",
            ClaimType.OWNER_NAME.value: "Mohan Reddy",
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: area,
            ClaimType.DISTRICT.value: "Vellore",
            ClaimType.VILLAGE.value: "Sathuvachari",
        },
        anomalies=["historical_instrument"],
    )

    deed_2021 = DocPlan(
        DocSpec(
            filename="Sale_Deed_2021.pdf",
            doc_type=DocumentType.SALE_DEED,
            title="DEED OF SALE",
            authority="Office of the Sub-Registrar, Katpadi, Vellore District",
            reference="DOC-2021-45821",
            issued_on=date(2021, 6, 15),
            pages=2,
            fields=[
                Field("Document Number", "DOC-2021-45821", 1),
                Field("Date of Registration", _d(15, 6, 2021), 1),
                Field("Vendor / Transferor", "Mohan Reddy", 1),
                Field("Purchaser / Transferee", owner, 2),
                Field("Survey Number", survey, 2),
                Field("Extent / Area", area, 2),
                Field("District", "Vellore", 1),
                Field("Village", "Sathuvachari", 1),
                Field("Sale Consideration", "Rs. 42,00,000", 2),
                Field("Classification", "Residential Plot", 2),
            ],
            paragraphs=recitals_for(DocumentType.SALE_DEED, 1, seed=21),
            seal_text="Sub-Registrar, Katpadi",
        ),
        expected_claims={
            ClaimType.DOCUMENT_NUMBER.value: "DOC-2021-45821",
            ClaimType.REGISTRATION_DATE.value: _d(15, 6, 2021),
            ClaimType.SELLER_NAME.value: "Mohan Reddy",
            ClaimType.OWNER_NAME.value: owner,
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: area,
            ClaimType.PROPERTY_TYPE.value: "Residential Plot",
        },
    )

    mortgage = DocPlan(
        DocSpec(
            filename="Mortgage_Deed_2023.pdf",
            doc_type=DocumentType.MORTGAGE_DOCUMENT,
            title="DEED OF SIMPLE MORTGAGE",
            authority="Office of the Sub-Registrar, Katpadi, Vellore District",
            reference="MTG-2023-7741",
            issued_on=date(2023, 2, 20),
            pages=2,
            fields=[
                Field("Document Number", "MTG-2023-7741", 1),
                Field("Date of Registration", _d(20, 2, 2023), 1),
                Field("Mortgagor", owner, 1),
                Field("Mortgagee", "Chola Cooperative Urban Bank", 1),
                Field("Survey Number", survey, 1),
                Field("Mortgage Amount", "Rs. 9,00,000", 1),
                Field("Charge Status", "Active", 1),
                Field("Loan Account", "CCUB/HL/2023/7741", 2),
            ],
            paragraphs=recitals_for(DocumentType.MORTGAGE_DOCUMENT, 2, seed=23),
            seal_text="Sub-Registrar, Katpadi",
        ),
        expected_claims={
            ClaimType.MORTGAGE_LENDER.value: "Chola Cooperative Urban Bank",
            ClaimType.MORTGAGE_AMOUNT.value: "Rs. 9,00,000",
            ClaimType.MORTGAGE_STATUS.value: "Active",
        },
        anomalies=["historical_encumbrance_since_released"],
    )

    noc = DocPlan(
        DocSpec(
            filename="Bank_NOC_2025.pdf",
            doc_type=DocumentType.BANK_NOC,
            title="NO OBJECTION CERTIFICATE",
            authority="Chola Cooperative Urban Bank, Vellore Branch",
            reference="NOC/CCUB/2025/0442",
            issued_on=date(2025, 4, 30),
            pages=1,
            fields=[
                Field("Certificate Number", "NOC/CCUB/2025/0442", 1),
                Field("Borrower Name", owner, 1),
                Field("Loan Account", "CCUB/HL/2023/7741", 1),
                Field("Survey Number", survey, 1),
                Field("Charge Status", "Released", 1),
                Field("Lender", "Chola Cooperative Urban Bank", 1),
            ],
            paragraphs=recitals_for(DocumentType.BANK_NOC, 1, seed=25),
            seal_text="Branch Manager",
        ),
        expected_claims={
            ClaimType.MORTGAGE_STATUS.value: "Released",
            ClaimType.MORTGAGE_LENDER.value: "Chola Cooperative Urban Bank",
        },
    )

    ec = DocPlan(
        DocSpec(
            filename="Encumbrance_Certificate_2026.pdf",
            doc_type=DocumentType.ENCUMBRANCE_CERTIFICATE,
            title="ENCUMBRANCE CERTIFICATE",
            authority="Office of the Sub-Registrar, Katpadi, Vellore District",
            reference="EC/VLR/2026/1187",
            issued_on=date(2026, 8, 12),
            pages=2,
            fields=[
                Field("Certificate Number", "EC/VLR/2026/1187", 1),
                Field("Claimant", owner, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", area, 1),
                Field("District", "Vellore", 1),
                Field("Village", "Sathuvachari", 1),
                Field("Search Period", "01-01-2015 to 31-07-2026", 1),
                Field("Encumbrance Status", "NIL", 2),
            ],
            paragraphs=[
                Para("No encumbrances were found subsisting on the schedule property as on the "
                     "date of this certificate. The mortgage registered as MTG-2023-7741 stands "
                     "released vide the release recorded on 30-04-2025.", 2),
            ] + recitals_for(DocumentType.ENCUMBRANCE_CERTIFICATE, 2, seed=26),
            seal_text="Registering Officer",
        ),
        expected_claims={
            ClaimType.DOCUMENT_NUMBER.value: "EC/VLR/2026/1187",
            ClaimType.OWNER_NAME.value: owner,
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: area,
            ClaimType.ENCUMBRANCE_PERIOD.value: "01-01-2015 to 31-07-2026",
            ClaimType.MORTGAGE_STATUS.value: "NIL",
        },
    )

    survey_rec = DocPlan(
        DocSpec(
            filename="Survey_Record_FMB_2024.pdf",
            doc_type=DocumentType.SURVEY_RECORD,
            title="SURVEY RECORD — FIELD MEASUREMENT BOOK EXTRACT",
            authority="Taluk Survey Office, Katpadi, Vellore District",
            reference="FMB/KTP/2024/0318",
            issued_on=date(2024, 1, 20),
            pages=2,
            fields=[
                Field("Certificate Number", "FMB/KTP/2024/0318", 1),
                Field("Survey Number", survey, 1),
                Field("Measured Area", area, 1),
                Field("Pattadar Name", owner, 1),
                Field("Classification", "Residential Plot", 1),
                Field("District", "Vellore", 1),
                Field("Village", "Sathuvachari", 1),
                Field("Boundaries", "North: Survey 142/2; South: Road; East: 142/3B; West: Canal", 2),
            ],
            paragraphs=recitals_for(DocumentType.SURVEY_RECORD, 2, seed=24),
            seal_text="Taluk Surveyor",
        ),
        expected_claims={
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: area,
            ClaimType.OWNER_NAME.value: owner,
            ClaimType.PROPERTY_TYPE.value: "Residential Plot",
        },
    )

    tax = DocPlan(
        DocSpec(
            filename="Property_Tax_Receipt_2026.pdf",
            doc_type=DocumentType.TAX_RECEIPT,
            title="PROPERTY TAX RECEIPT",
            authority="Vellore Municipal Corporation — Zone III",
            reference="VMC/2026/HY1/884213",
            issued_on=date(2026, 4, 5),
            pages=1,
            fields=[
                Field("Receipt Number", "VMC/2026/HY1/884213", 1),
                Field("Assessee", owner, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", area, 1),
                Field("Half-Year", "2026 — First Half", 1),
                Field("Payment Status", "Paid", 1),
                Field("Amount", "Rs. 4,120", 1),
            ],
            paragraphs=recitals_for(DocumentType.TAX_RECEIPT, 1, seed=261),
            seal_text="Revenue Officer",
        ),
        expected_claims={
            ClaimType.TAXPAYER_NAME.value: owner,
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: area,
            ClaimType.TAX_STATUS.value: "Paid",
        },
    )

    declaration = DocPlan(
        DocSpec(
            filename="Owner_Declaration.pdf",
            doc_type=DocumentType.OWNER_DECLARATION,
            title="OWNER SELF-DECLARATION",
            authority="Submitted by the owner through LandTrust Connect",
            reference="DECL-0001",
            issued_on=date(2026, 8, 25),
            pages=1,
            fields=[
                Field("Owner Name", owner, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", area, 1),
                Field("Mobile", "9840112233", 1),
                Field("Address", "14, Second Cross Street, Sathuvachari, Vellore 632009", 1),
                Field("Aadhaar Number", "XXXX XXXX 4821", 1),
            ],
            paragraphs=recitals_for(DocumentType.OWNER_DECLARATION, 1, seed=1),
            seal_text="Self-declared",
        ),
        expected_claims={
            ClaimType.OWNER_NAME.value: owner,
            ClaimType.SURVEY_NUMBER.value: survey,
        },
        anomalies=["self_declared_contact_details"],
    )

    return ScenarioPlan(
        key="clean_title",
        label="Clean Title",
        reference="LTC-PR-0001",
        survey_number=survey,
        district="Vellore",
        village="Sathuvachari",
        property_type="Residential Plot",
        claimed_area_sqft=2400,
        guideline_value_inr=48_00_000,
        asking_price_inr=52_00_000,
        listed_owner_name=owner,
        owner_name=owner,
        owner_email="ravi.kumar@example.in",
        owner_phone="9840112233",
        owner_identity="XXXX XXXX 4821",
        summary=(
            "A fully corroborated file with a complete chain of title: two registered deeds, a "
            "mortgage that was created in 2023 and released in 2025, a current encumbrance "
            "certificate, a certified survey record and a paid tax receipt."
        ),
        documents=[deed_2017, deed_2021, mortgage, noc, ec, survey_rec, tax, declaration],
        expected_state=TransactionState.PROCEED,
        expected_risk_band="LOW",
        expected_statuses={
            ClaimType.OWNER_NAME.value: VerificationStatus.VERIFIED,
            ClaimType.SURVEY_NUMBER.value: VerificationStatus.VERIFIED,
            ClaimType.PROPERTY_AREA.value: VerificationStatus.VERIFIED,
            ClaimType.MORTGAGE_STATUS.value: VerificationStatus.VERIFIED,
            ClaimType.TAX_STATUS.value: VerificationStatus.VERIFIED,
            ClaimType.REGISTRATION_DATE.value: VerificationStatus.VERIFIED,
        },
        expected_contradiction_types=[],
        injected_anomalies=["historical_ownership_chain", "released_mortgage_in_history"],
        demo_note=(
            "Demonstrates that a historical owner and a discharged mortgage are recognised as "
            "history rather than contradictions — the temporal scoping layer at work."
        ),
    )


# ===========================================================================
# CASE B — area conflict plus an active encumbrance  (the acceptance test)
# ===========================================================================
def case_b() -> ScenarioPlan:
    owner = "Priya Sharma"
    survey = "82/4B"

    deed = DocPlan(
        DocSpec(
            filename="Sale_Deed_2022.pdf",
            doc_type=DocumentType.SALE_DEED,
            title="DEED OF SALE",
            authority="Office of the Sub-Registrar, Thiruporur, Chengalpattu District",
            reference="DOC-2022-11934",
            issued_on=date(2022, 3, 22),
            pages=2,
            fields=[
                Field("Document Number", "DOC-2022-11934", 1),
                Field("Date of Registration", _d(22, 3, 2022), 1),
                Field("Vendor / Transferor", "Anand Krishnan", 1),
                Field("Purchaser / Transferee", owner, 1),
                Field("Survey Number", survey, 1),
                Field("District", "Chengalpattu", 1),
                Field("Village", "Thiruporur", 1),
                Field("Extent / Area", "1800 sq.ft", 2),
                Field("Sale Consideration", "Rs. 56,00,000", 2),
                Field("Classification", "Residential Plot", 2),
            ],
            paragraphs=recitals_for(DocumentType.SALE_DEED, 2, seed=22),
            seal_text="Sub-Registrar, Thiruporur",
        ),
        expected_claims={
            ClaimType.DOCUMENT_NUMBER.value: "DOC-2022-11934",
            ClaimType.REGISTRATION_DATE.value: _d(22, 3, 2022),
            ClaimType.SELLER_NAME.value: "Anand Krishnan",
            ClaimType.OWNER_NAME.value: owner,
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: "1800 sq.ft",
        },
    )

    ec = DocPlan(
        DocSpec(
            filename="Encumbrance_Certificate_2024.pdf",
            doc_type=DocumentType.ENCUMBRANCE_CERTIFICATE,
            title="ENCUMBRANCE CERTIFICATE",
            authority="Office of the Sub-Registrar, Thiruporur, Chengalpattu District",
            reference="EC/CGL/2024/3390",
            issued_on=date(2024, 11, 18),
            pages=2,
            fields=[
                Field("Certificate Number", "EC/CGL/2024/3390", 1),
                Field("Claimant", "Priya S. Sharma", 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", "1650 sq.ft", 1),
                Field("Search Period", "01-01-2019 to 31-10-2024", 1),
                Field("Encumbrance Status", "Active", 2),
                Field("Mortgage Amount", "Rs. 18,00,000", 2),
                Field("Mortgagee", "Sundaram Housing Finance Ltd", 2),
            ],
            paragraphs=[
                Para("A subsisting mortgage in favour of the institution named above is recorded "
                     "against the schedule property for the period of search.", 2),
            ] + recitals_for(DocumentType.ENCUMBRANCE_CERTIFICATE, 2, seed=224),
            seal_text="Registering Officer",
        ),
        expected_claims={
            ClaimType.DOCUMENT_NUMBER.value: "EC/CGL/2024/3390",
            ClaimType.OWNER_NAME.value: "Priya S. Sharma",
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: "1650 sq.ft",
            ClaimType.MORTGAGE_STATUS.value: "Active",
            ClaimType.MORTGAGE_AMOUNT.value: "Rs. 18,00,000",
            ClaimType.MORTGAGE_LENDER.value: "Sundaram Housing Finance Ltd",
        },
        anomalies=["area_mismatch_150_sqft", "owner_name_initial_variant",
                   "active_mortgage", "stale_certificate"],
    )

    tax = DocPlan(
        DocSpec(
            filename="Property_Tax_Receipt_2026.pdf",
            doc_type=DocumentType.TAX_RECEIPT,
            title="PROPERTY TAX RECEIPT",
            authority="Thiruporur Town Panchayat",
            reference="TTP/2026/HY1/22187",
            issued_on=date(2026, 4, 10),
            pages=1,
            fields=[
                Field("Receipt Number", "TTP/2026/HY1/22187", 1),
                Field("Assessee", owner, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", "1800 sq.ft", 1),
                Field("Payment Status", "Paid", 1),
                Field("Amount", "Rs. 3,480", 1),
            ],
            paragraphs=recitals_for(DocumentType.TAX_RECEIPT, 1, seed=226),
            seal_text="Executive Officer",
        ),
        expected_claims={
            ClaimType.TAXPAYER_NAME.value: owner,
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: "1800 sq.ft",
            ClaimType.TAX_STATUS.value: "Paid",
        },
    )

    mortgage = DocPlan(
        DocSpec(
            filename="Mortgage_Deed_2023.pdf",
            doc_type=DocumentType.MORTGAGE_DOCUMENT,
            title="DEED OF SIMPLE MORTGAGE",
            authority="Office of the Sub-Registrar, Thiruporur, Chengalpattu District",
            reference="MTG-2023-5512",
            issued_on=date(2023, 5, 5),
            pages=2,
            fields=[
                Field("Document Number", "MTG-2023-5512", 1),
                Field("Date of Registration", _d(5, 5, 2023), 1),
                Field("Mortgagor", owner, 1),
                Field("Mortgagee", "Sundaram Housing Finance Ltd", 1),
                Field("Survey Number", survey, 1),
                Field("Mortgage Amount", "Rs. 18,00,000", 1),
                Field("Charge Status", "Active", 1),
                Field("Loan Account", "SHF/HL/2023/5512", 2),
            ],
            paragraphs=recitals_for(DocumentType.MORTGAGE_DOCUMENT, 2, seed=235),
            seal_text="Sub-Registrar, Thiruporur",
        ),
        expected_claims={
            ClaimType.MORTGAGE_LENDER.value: "Sundaram Housing Finance Ltd",
            ClaimType.MORTGAGE_AMOUNT.value: "Rs. 18,00,000",
            ClaimType.MORTGAGE_STATUS.value: "Active",
        },
        anomalies=["active_mortgage"],
    )

    declaration = DocPlan(
        DocSpec(
            filename="Owner_Declaration.pdf",
            doc_type=DocumentType.OWNER_DECLARATION,
            title="OWNER SELF-DECLARATION",
            authority="Submitted by the owner through LandTrust Connect",
            reference="DECL-0002",
            issued_on=date(2026, 8, 20),
            pages=1,
            fields=[
                Field("Owner Name", owner, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", "1800 sq.ft", 1),
                Field("Mobile", "9789004411", 1),
                Field("Address", "7B, Lake View Enclave, Thiruporur, Chengalpattu 603110", 1),
            ],
            paragraphs=recitals_for(DocumentType.OWNER_DECLARATION, 1, seed=2),
            seal_text="Self-declared",
        ),
        expected_claims={
            ClaimType.OWNER_NAME.value: owner,
            ClaimType.PROPERTY_AREA.value: "1800 sq.ft",
        },
    )

    return ScenarioPlan(
        key="area_conflict_active_mortgage",
        label="Area Conflict + Active Mortgage",
        reference="LTC-PR-0002",
        survey_number=survey,
        district="Chengalpattu",
        village="Thiruporur",
        property_type="Residential Plot",
        claimed_area_sqft=1800,
        guideline_value_inr=62_00_000,
        asking_price_inr=68_00_000,
        listed_owner_name=owner,
        owner_name=owner,
        owner_email="priya.sharma@example.in",
        owner_phone="9789004411",
        owner_identity="XXXX XXXX 7734",
        summary=(
            "The Review-2 acceptance case. The sale deed records 1800 sq.ft while the "
            "encumbrance certificate records 1650 sq.ft, the certificate is nearly two years "
            "old, an ₹18,00,000 charge is subsisting, the owner's name appears with and without "
            "a middle initial, and no certified survey record has been supplied."
        ),
        documents=[deed, ec, tax, mortgage, declaration],
        expected_state=TransactionState.HOLD,
        expected_risk_band="HIGH",
        expected_statuses={
            ClaimType.OWNER_NAME.value: VerificationStatus.PARTIALLY_VERIFIED,
            ClaimType.SURVEY_NUMBER.value: VerificationStatus.VERIFIED,
            ClaimType.PROPERTY_AREA.value: VerificationStatus.CONFLICTING,
            ClaimType.MORTGAGE_STATUS.value: VerificationStatus.VERIFIED,
            ClaimType.TAX_STATUS.value: VerificationStatus.VERIFIED,
        },
        expected_contradiction_types=[
            ContradictionType.AREA_DISCREPANCY.value,
            ContradictionType.MISSING_EVIDENCE.value,
        ],
        injected_anomalies=[
            "area_mismatch_150_sqft", "owner_name_initial_variant", "active_mortgage",
            "stale_encumbrance_certificate", "missing_survey_record",
        ],
        demo_note=(
            "Run this one for the acceptance demonstration: detect → HOLD → resolution plan → "
            "apply evidence → risk falls → PROCEED."
        ),
    )


# ===========================================================================
# CASE C — ownership contradiction with an expired authorisation
# ===========================================================================
def case_c() -> ScenarioPlan:
    evidenced_owner = "Mohan Reddy"
    listing_party = "Arjun Reddy"
    survey = "27/1C"
    area = "3200 sq.ft"

    deed = DocPlan(
        DocSpec(
            filename="Sale_Deed_2019.pdf",
            doc_type=DocumentType.SALE_DEED,
            title="DEED OF SALE",
            authority="Office of the Sub-Registrar, Uthagamandalam, Nilgiris District",
            reference="DOC-2019-77120",
            issued_on=date(2019, 9, 9),
            pages=2,
            fields=[
                Field("Document Number", "DOC-2019-77120", 1),
                Field("Date of Registration", _d(9, 9, 2019), 1),
                Field("Vendor / Transferor", "Sundar Rajan", 1),
                Field("Purchaser / Transferee", evidenced_owner, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", area, 1),
                Field("District", "Nilgiris", 1),
                Field("Village", "Kotagiri", 1),
                Field("Sale Consideration", "Rs. 88,00,000", 2),
            ],
            paragraphs=recitals_for(DocumentType.SALE_DEED, 2, seed=19),
            seal_text="Sub-Registrar, Uthagamandalam",
        ),
        expected_claims={
            ClaimType.DOCUMENT_NUMBER.value: "DOC-2019-77120",
            ClaimType.REGISTRATION_DATE.value: _d(9, 9, 2019),
            ClaimType.OWNER_NAME.value: evidenced_owner,
            ClaimType.SELLER_NAME.value: "Sundar Rajan",
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: area,
        },
    )

    survey_rec = DocPlan(
        DocSpec(
            filename="Survey_Record_2022.pdf",
            doc_type=DocumentType.SURVEY_RECORD,
            title="SURVEY RECORD — FIELD MEASUREMENT BOOK EXTRACT",
            authority="Taluk Survey Office, Kotagiri, Nilgiris District",
            reference="FMB/KTG/2022/0091",
            issued_on=date(2022, 6, 2),
            pages=2,
            fields=[
                Field("Certificate Number", "FMB/KTG/2022/0091", 1),
                Field("Survey Number", survey, 1),
                Field("Measured Area", area, 1),
                Field("Pattadar Name", evidenced_owner, 1),
                Field("Classification", "Agricultural — converted", 1),
                Field("District", "Nilgiris", 1),
                Field("Village", "Kotagiri", 1),
            ],
            paragraphs=recitals_for(DocumentType.SURVEY_RECORD, 2, seed=192),
            seal_text="Taluk Surveyor",
        ),
        expected_claims={
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: area,
            ClaimType.OWNER_NAME.value: evidenced_owner,
        },
    )

    poa = DocPlan(
        DocSpec(
            filename="Power_of_Attorney_2023.pdf",
            doc_type=DocumentType.POWER_OF_ATTORNEY,
            title="SPECIAL POWER OF ATTORNEY",
            authority="Office of the Sub-Registrar, Kotagiri, Nilgiris District",
            reference="GPA-2023-0417",
            issued_on=date(2023, 1, 1),
            valid_until=date(2024, 12, 31),
            pages=2,
            fields=[
                Field("Document Number", "GPA-2023-0417", 1),
                Field("Date of Registration", _d(1, 1, 2023), 1),
                Field("Principal", evidenced_owner, 1),
                Field("Attorney Holder", listing_party, 1),
                Field("Survey Number", survey, 1),
                Field("Valid Until", _d(31, 12, 2024), 1),
            ],
            paragraphs=recitals_for(DocumentType.POWER_OF_ATTORNEY, 2, seed=193),
            seal_text="Sub-Registrar, Kotagiri",
        ),
        expected_claims={
            ClaimType.POA_GRANTOR.value: evidenced_owner,
            ClaimType.POA_HOLDER.value: listing_party,
            ClaimType.AUTHORIZATION_EXPIRY.value: _d(31, 12, 2024),
        },
        anomalies=["expired_power_of_attorney"],
    )

    ec = DocPlan(
        DocSpec(
            filename="Encumbrance_Certificate_2025.pdf",
            doc_type=DocumentType.ENCUMBRANCE_CERTIFICATE,
            title="ENCUMBRANCE CERTIFICATE",
            authority="Office of the Sub-Registrar, Kotagiri, Nilgiris District",
            reference="EC/NLG/2025/0774",
            issued_on=date(2025, 6, 14),
            pages=2,
            fields=[
                Field("Certificate Number", "EC/NLG/2025/0774", 1),
                Field("Claimant", evidenced_owner, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", area, 1),
                Field("Search Period", "01-01-2015 to 31-05-2025", 1),
                Field("Encumbrance Status", "Active", 2),
                Field("Mortgage Amount", "Rs. 25,00,000", 2),
                Field("Mortgagee", "Kaveri Grameena Bank", 2),
            ],
            paragraphs=recitals_for(DocumentType.ENCUMBRANCE_CERTIFICATE, 2, seed=195),
            seal_text="Registering Officer",
        ),
        expected_claims={
            ClaimType.OWNER_NAME.value: evidenced_owner,
            ClaimType.MORTGAGE_STATUS.value: "Active",
            ClaimType.MORTGAGE_AMOUNT.value: "Rs. 25,00,000",
            ClaimType.MORTGAGE_LENDER.value: "Kaveri Grameena Bank",
        },
        anomalies=["active_mortgage", "stale_certificate"],
    )

    declaration = DocPlan(
        DocSpec(
            filename="Owner_Declaration.pdf",
            doc_type=DocumentType.OWNER_DECLARATION,
            title="OWNER SELF-DECLARATION",
            authority="Submitted through LandTrust Connect",
            reference="DECL-0003",
            issued_on=date(2026, 8, 28),
            pages=1,
            fields=[
                Field("Owner Name", listing_party, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", area, 1),
                Field("Mobile", "9445567788", 1),
            ],
            paragraphs=recitals_for(DocumentType.OWNER_DECLARATION, 1, seed=3),
            seal_text="Self-declared",
        ),
        expected_claims={
            ClaimType.OWNER_NAME.value: listing_party,
            ClaimType.SURVEY_NUMBER.value: survey,
        },
        anomalies=["listing_party_differs_from_evidenced_owner"],
    )

    return ScenarioPlan(
        key="possible_impersonation",
        label="Possible Impersonation / Expired Authorisation",
        reference="LTC-PR-0003",
        survey_number=survey,
        district="Nilgiris",
        village="Kotagiri",
        property_type="Converted Agricultural",
        claimed_area_sqft=3200,
        guideline_value_inr=1_05_00_000,
        asking_price_inr=1_12_00_000,
        listed_owner_name=listing_party,
        owner_name=listing_party,
        owner_email="arjun.reddy@example.in",
        owner_phone="9445567788",
        owner_identity="XXXX XXXX 9012",
        summary=(
            "The property is listed by Arjun Reddy, but every registered document names Mohan "
            "Reddy. The only link between them is a power of attorney that expired on "
            "31-12-2024, and an ₹25,00,000 charge is subsisting."
        ),
        documents=[deed, survey_rec, poa, ec, declaration],
        expected_state=TransactionState.ESCALATE,
        expected_risk_band="CRITICAL",
        expected_statuses={
            ClaimType.OWNER_NAME.value: VerificationStatus.CONFLICTING,
            ClaimType.SURVEY_NUMBER.value: VerificationStatus.VERIFIED,
            ClaimType.PROPERTY_AREA.value: VerificationStatus.VERIFIED,
            ClaimType.MORTGAGE_STATUS.value: VerificationStatus.VERIFIED,
        },
        expected_contradiction_types=[
            ContradictionType.OWNER_IDENTITY.value,
            ContradictionType.AUTHORIZATION_EXPIRY.value,
            ContradictionType.MISSING_EVIDENCE.value,
        ],
        injected_anomalies=[
            "listing_party_differs_from_evidenced_owner", "expired_power_of_attorney",
            "active_mortgage", "missing_tax_receipt",
        ],
        demo_note=(
            "Shows the system refusing to establish ownership and escalating rather than "
            "guessing. Note the wording: unverified authority, not an accusation."
        ),
        expected_resolvable=False,
    )


# ===========================================================================
# CASE D — joint ownership with thin evidence
# ===========================================================================
def case_d() -> ScenarioPlan:
    owners = "Lakshmi Narayanan and Meera Narayanan"
    survey = "55/2"
    area = "4800 sq.ft"

    deed = DocPlan(
        DocSpec(
            filename="Sale_Deed_2020.pdf",
            doc_type=DocumentType.SALE_DEED,
            title="DEED OF SALE",
            authority="Office of the Sub-Registrar, Saravanampatti, Coimbatore District",
            reference="DOC-2020-30188",
            issued_on=date(2020, 2, 12),
            pages=2,
            fields=[
                Field("Document Number", "DOC-2020-30188", 1),
                Field("Date of Registration", _d(12, 2, 2020), 1),
                Field("Vendor / Transferor", "Balasubramanian T", 1),
                Field("Purchaser / Transferee", owners, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", area, 1),
                Field("District", "Coimbatore", 1),
                Field("Village", "Saravanampatti", 1),
                Field("Sale Consideration", "Rs. 74,00,000", 2),
            ],
            paragraphs=[
                Para("The schedule property is conveyed to the Purchasers jointly, to be held by "
                     "them as tenants in common in equal shares.", 2),
            ] + recitals_for(DocumentType.SALE_DEED, 2, seed=20),
            seal_text="Sub-Registrar, Saravanampatti",
        ),
        expected_claims={
            ClaimType.DOCUMENT_NUMBER.value: "DOC-2020-30188",
            ClaimType.OWNER_NAME.value: owners,
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: area,
            ClaimType.REGISTRATION_DATE.value: _d(12, 2, 2020),
        },
        anomalies=["joint_ownership"],
    )

    survey_rec = DocPlan(
        DocSpec(
            filename="Survey_Record_2021.pdf",
            doc_type=DocumentType.SURVEY_RECORD,
            title="SURVEY RECORD — PATTA EXTRACT",
            authority="Taluk Survey Office, Coimbatore North",
            reference="FMB/CBE/2021/1442",
            issued_on=date(2021, 7, 19),
            pages=1,
            fields=[
                Field("Certificate Number", "FMB/CBE/2021/1442", 1),
                Field("Survey Number", survey, 1),
                Field("Measured Area", area, 1),
                Field("Pattadar Name", "Lakshmi Narayanan & Meera Narayanan", 1),
                Field("Classification", "Residential Plot", 1),
                Field("District", "Coimbatore", 1),
            ],
            paragraphs=recitals_for(DocumentType.SURVEY_RECORD, 1, seed=201),
            seal_text="Taluk Surveyor",
        ),
        expected_claims={
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: area,
            ClaimType.OWNER_NAME.value: "Lakshmi Narayanan & Meera Narayanan",
        },
        anomalies=["joint_owner_name_formatting_variant"],
    )

    tax = DocPlan(
        DocSpec(
            filename="Property_Tax_Receipt_2026.pdf",
            doc_type=DocumentType.TAX_RECEIPT,
            title="PROPERTY TAX RECEIPT",
            authority="Coimbatore City Municipal Corporation — Zone II",
            reference="CCMC/2026/HY1/551903",
            issued_on=date(2026, 4, 18),
            pages=1,
            fields=[
                Field("Receipt Number", "CCMC/2026/HY1/551903", 1),
                Field("Assessee", "Lakshmi Narayanan", 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", area, 1),
                Field("Payment Status", "Paid", 1),
                Field("Amount", "Rs. 6,900", 1),
            ],
            paragraphs=recitals_for(DocumentType.TAX_RECEIPT, 1, seed=202),
            seal_text="Revenue Officer",
        ),
        expected_claims={
            ClaimType.TAXPAYER_NAME.value: "Lakshmi Narayanan",
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: area,
            ClaimType.TAX_STATUS.value: "Paid",
        },
    )

    declaration = DocPlan(
        DocSpec(
            filename="Owner_Declaration.pdf",
            doc_type=DocumentType.OWNER_DECLARATION,
            title="OWNER SELF-DECLARATION",
            authority="Submitted through LandTrust Connect",
            reference="DECL-0004",
            issued_on=date(2026, 8, 30),
            pages=1,
            fields=[
                Field("Owner Name", owners, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", area, 1),
                Field("Encumbrance Status", "None to my knowledge", 1),
                Field("Mobile", "9600233445", 1),
            ],
            paragraphs=recitals_for(DocumentType.OWNER_DECLARATION, 1, seed=4),
            seal_text="Self-declared",
        ),
        expected_claims={
            ClaimType.OWNER_NAME.value: owners,
            ClaimType.MORTGAGE_STATUS.value: "None to my knowledge",
        },
        anomalies=["self_declared_encumbrance_status_without_certificate"],
    )

    return ScenarioPlan(
        key="joint_ownership_missing_ec",
        label="Joint Ownership / Missing Encumbrance Certificate",
        reference="LTC-PR-0004",
        survey_number=survey,
        district="Coimbatore",
        village="Saravanampatti",
        property_type="Residential Plot",
        claimed_area_sqft=4800,
        guideline_value_inr=96_00_000,
        asking_price_inr=92_00_000,
        listed_owner_name=owners,
        owner_name="Lakshmi Narayanan",
        owner_email="lakshmi.n@example.in",
        owner_phone="9600233445",
        owner_identity="XXXX XXXX 3355",
        summary=(
            "Two joint owners, consistent extent across the deed, the survey record and the tax "
            "receipt — but no encumbrance certificate at all, and the owner's own declaration "
            "that there is 'none to my knowledge' carries no evidential weight."
        ),
        documents=[deed, survey_rec, tax, declaration],
        expected_state=TransactionState.WARN,
        expected_risk_band="MODERATE",
        expected_statuses={
            ClaimType.OWNER_NAME.value: VerificationStatus.PARTIALLY_VERIFIED,
            ClaimType.SURVEY_NUMBER.value: VerificationStatus.VERIFIED,
            ClaimType.PROPERTY_AREA.value: VerificationStatus.VERIFIED,
            ClaimType.TAX_STATUS.value: VerificationStatus.VERIFIED,
        },
        expected_contradiction_types=[ContradictionType.MISSING_EVIDENCE.value],
        injected_anomalies=[
            "missing_encumbrance_certificate", "joint_owner_name_formatting_variant",
            "owner_declared_encumbrance_status",
        ],
        demo_note=(
            "Shows an owner-declared 'no mortgage' being presented as OWNER PROVIDED rather than "
            "verified — the evidence gate working on an honest owner as well as a dishonest one."
        ),
    )


# ===========================================================================
# CASE E — document modification indicators
# ===========================================================================
def case_e() -> ScenarioPlan:
    evidenced_owner = "Suresh Babu"
    listing_party = "Vikram Devarajan"
    survey = "9/6D"

    deed = DocPlan(
        DocSpec(
            filename="Sale_Deed_2018_modified.pdf",
            doc_type=DocumentType.SALE_DEED,
            title="DEED OF SALE",
            authority="Office of the Sub-Registrar, Tambaram, Chengalpattu District",
            reference="DOC-2018-60233",
            issued_on=date(2018, 10, 4),
            pages=2,
            fields=[
                Field("Document Number", "DOC-2018-60233", 1),
                Field("Date of Registration", _d(4, 10, 2018), 1),
                Field("Vendor / Transferor", "Kalyani Ramesh", 1),
                Field("Purchaser / Transferee", evidenced_owner, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", "2000 sq.ft", 1),
                Field("District", "Chengalpattu", 1),
                Field("Village", "Tambaram", 1),
                Field("Sale Consideration", "Rs. 46,00,000", 2),
            ],
            paragraphs=recitals_for(DocumentType.SALE_DEED, 2, seed=18),
            tamper=Tamper(page=1, find="2000 sq.ft", replace="5000 sq.ft",
                          note="Extent overtyped after issue"),
            seal_text="Sub-Registrar, Tambaram",
        ),
        expected_claims={
            ClaimType.DOCUMENT_NUMBER.value: "DOC-2018-60233",
            ClaimType.OWNER_NAME.value: evidenced_owner,
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: "5000 sq.ft",   # what the altered file now says
            ClaimType.REGISTRATION_DATE.value: _d(4, 10, 2018),
        },
        anomalies=["post_issue_modification", "incremental_save", "font_discontinuity",
                   "area_inflated_from_2000_to_5000"],
    )

    survey_rec = DocPlan(
        DocSpec(
            filename="Survey_Record_2023.pdf",
            doc_type=DocumentType.SURVEY_RECORD,
            title="SURVEY RECORD — FIELD MEASUREMENT BOOK EXTRACT",
            authority="Taluk Survey Office, Tambaram",
            reference="FMB/TMB/2023/2210",
            issued_on=date(2023, 3, 27),
            pages=1,
            fields=[
                Field("Certificate Number", "FMB/TMB/2023/2210", 1),
                Field("Survey Number", survey, 1),
                Field("Measured Area", "2000 sq.ft", 1),
                Field("Pattadar Name", evidenced_owner, 1),
                Field("District", "Chengalpattu", 1),
            ],
            paragraphs=recitals_for(DocumentType.SURVEY_RECORD, 1, seed=183),
            seal_text="Taluk Surveyor",
        ),
        expected_claims={
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: "2000 sq.ft",
            ClaimType.OWNER_NAME.value: evidenced_owner,
        },
    )

    ec = DocPlan(
        DocSpec(
            filename="Encumbrance_Certificate_2026_partial.pdf",
            doc_type=DocumentType.ENCUMBRANCE_CERTIFICATE,
            title="ENCUMBRANCE CERTIFICATE",
            authority="Office of the Sub-Registrar, Tambaram, Chengalpattu District",
            reference="EC/CGL/2026/5521",
            issued_on=date(2026, 7, 2),
            pages=2,
            declared_pages=3,
            fields=[
                Field("Certificate Number", "EC/CGL/2026/5521", 1),
                Field("Claimant", evidenced_owner, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", "2000 sq.ft", 1),
                Field("Search Period", "01-01-2016 to 30-06-2026", 1),
                Field("Encumbrance Status", "NIL", 2),
            ],
            paragraphs=recitals_for(DocumentType.ENCUMBRANCE_CERTIFICATE, 2, seed=186),
            seal_text="Registering Officer",
        ),
        expected_claims={
            ClaimType.OWNER_NAME.value: evidenced_owner,
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: "2000 sq.ft",
            ClaimType.MORTGAGE_STATUS.value: "NIL",
        },
        anomalies=["missing_page_declared_3_supplied_2"],
    )

    declaration = DocPlan(
        DocSpec(
            filename="Owner_Declaration.pdf",
            doc_type=DocumentType.OWNER_DECLARATION,
            title="OWNER SELF-DECLARATION",
            authority="Submitted through LandTrust Connect",
            reference="DECL-0005",
            issued_on=date(2026, 9, 1),
            pages=1,
            fields=[
                Field("Owner Name", listing_party, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", "5000 sq.ft", 1),
                Field("Mobile", "9840998877", 1),
            ],
            paragraphs=recitals_for(DocumentType.OWNER_DECLARATION, 1, seed=5),
            seal_text="Self-declared",
        ),
        expected_claims={
            ClaimType.OWNER_NAME.value: listing_party,
            ClaimType.PROPERTY_AREA.value: "5000 sq.ft",
        },
        anomalies=["listing_party_differs_from_evidenced_owner"],
    )

    return ScenarioPlan(
        key="document_modification",
        label="Possible Document Modification",
        reference="LTC-PR-0005",
        survey_number=survey,
        district="Chengalpattu",
        village="Tambaram",
        property_type="Residential Plot",
        claimed_area_sqft=5000,
        guideline_value_inr=70_00_000,
        asking_price_inr=1_38_00_000,
        listed_owner_name=listing_party,
        owner_name=listing_party,
        owner_email="vikram.d@example.in",
        owner_phone="9840998877",
        owner_identity="XXXX XXXX 6611",
        summary=(
            "The uploaded deed shows post-issue modification indicators — an incremental save and "
            "an isolated font on the page where the extent appears — and the extent it now states "
            "(5000 sq.ft) contradicts both the survey record and the encumbrance certificate "
            "(2000 sq.ft). The listing party does not appear in any document."
        ),
        documents=[deed, survey_rec, ec, declaration],
        expected_state=TransactionState.REJECT,
        expected_risk_band="CRITICAL",
        expected_statuses={
            ClaimType.OWNER_NAME.value: VerificationStatus.CONFLICTING,
            ClaimType.PROPERTY_AREA.value: VerificationStatus.CONFLICTING,
            ClaimType.SURVEY_NUMBER.value: VerificationStatus.VERIFIED,
        },
        expected_contradiction_types=[
            ContradictionType.OWNER_IDENTITY.value,
            ContradictionType.AREA_DISCREPANCY.value,
            ContradictionType.DOCUMENT_INTEGRITY.value,
            ContradictionType.MISSING_EVIDENCE.value,
        ],
        injected_anomalies=[
            "post_issue_modification", "incremental_save", "font_discontinuity",
            "area_inflated_from_2000_to_5000", "missing_page_declared_3_supplied_2",
            "listing_party_differs_from_evidenced_owner", "price_far_above_guideline",
        ],
        demo_note=(
            "The only scenario that reaches REJECT. The indicators are computed from the PDF byte "
            "stream and font metrics, not stored as a flag on the record."
        ),
        expected_resolvable=False,
    )


# ===========================================================================
# CASE F — second clean file, different district
# ===========================================================================
def case_f() -> ScenarioPlan:
    owner = "Fatima Begum"
    survey = "210/7"
    area = "1500 sq.ft"

    deed = DocPlan(
        DocSpec(
            filename="Sale_Deed_2023.pdf",
            doc_type=DocumentType.SALE_DEED,
            title="DEED OF SALE",
            authority="Office of the Sub-Registrar, Anna Nagar, Madurai District",
            reference="DOC-2023-90455",
            issued_on=date(2023, 11, 27),
            pages=2,
            fields=[
                Field("Document Number", "DOC-2023-90455", 1),
                Field("Date of Registration", _d(27, 11, 2023), 1),
                Field("Vendor / Transferor", "Ilango Sethupathi", 1),
                Field("Purchaser / Transferee", owner, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", area, 1),
                Field("District", "Madurai", 1),
                Field("Village", "Anna Nagar", 1),
                Field("Sale Consideration", "Rs. 33,00,000", 2),
                Field("Classification", "Residential Plot", 2),
            ],
            paragraphs=recitals_for(DocumentType.SALE_DEED, 2, seed=231),
            seal_text="Sub-Registrar, Anna Nagar",
        ),
        expected_claims={
            ClaimType.DOCUMENT_NUMBER.value: "DOC-2023-90455",
            ClaimType.OWNER_NAME.value: owner,
            ClaimType.SELLER_NAME.value: "Ilango Sethupathi",
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: area,
            ClaimType.REGISTRATION_DATE.value: _d(27, 11, 2023),
        },
    )

    ec = DocPlan(
        DocSpec(
            filename="Encumbrance_Certificate_2026.pdf",
            doc_type=DocumentType.ENCUMBRANCE_CERTIFICATE,
            title="ENCUMBRANCE CERTIFICATE",
            authority="Office of the Sub-Registrar, Anna Nagar, Madurai District",
            reference="EC/MDU/2026/2201",
            issued_on=date(2026, 8, 22),
            pages=2,
            fields=[
                Field("Certificate Number", "EC/MDU/2026/2201", 1),
                Field("Claimant", owner, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", area, 1),
                Field("Search Period", "01-01-2018 to 15-08-2026", 1),
                Field("Encumbrance Status", "NIL", 2),
            ],
            paragraphs=[Para("No encumbrances were found subsisting on the schedule property for "
                             "the period of search.", 2)]
            + recitals_for(DocumentType.ENCUMBRANCE_CERTIFICATE, 2, seed=232),
            seal_text="Registering Officer",
        ),
        expected_claims={
            ClaimType.OWNER_NAME.value: owner,
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: area,
            ClaimType.MORTGAGE_STATUS.value: "NIL",
        },
    )

    survey_rec = DocPlan(
        DocSpec(
            filename="Survey_Record_2025.pdf",
            doc_type=DocumentType.SURVEY_RECORD,
            title="SURVEY RECORD — PATTA EXTRACT",
            authority="Taluk Survey Office, Madurai North",
            reference="FMB/MDU/2025/0640",
            issued_on=date(2025, 5, 9),
            pages=1,
            fields=[
                Field("Certificate Number", "FMB/MDU/2025/0640", 1),
                Field("Survey Number", survey, 1),
                Field("Measured Area", area, 1),
                Field("Pattadar Name", owner, 1),
                Field("Classification", "Residential Plot", 1),
                Field("District", "Madurai", 1),
            ],
            paragraphs=recitals_for(DocumentType.SURVEY_RECORD, 1, seed=233),
            seal_text="Taluk Surveyor",
        ),
        expected_claims={
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: area,
            ClaimType.OWNER_NAME.value: owner,
        },
    )

    tax = DocPlan(
        DocSpec(
            filename="Property_Tax_Receipt_2026.pdf",
            doc_type=DocumentType.TAX_RECEIPT,
            title="PROPERTY TAX RECEIPT",
            authority="Madurai Municipal Corporation — Zone I",
            reference="MMC/2026/HY1/110774",
            issued_on=date(2026, 4, 12),
            pages=1,
            fields=[
                Field("Receipt Number", "MMC/2026/HY1/110774", 1),
                Field("Assessee", owner, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", area, 1),
                Field("Payment Status", "Paid", 1),
                Field("Amount", "Rs. 2,240", 1),
            ],
            paragraphs=recitals_for(DocumentType.TAX_RECEIPT, 1, seed=234),
            seal_text="Revenue Officer",
        ),
        expected_claims={
            ClaimType.TAXPAYER_NAME.value: owner,
            ClaimType.SURVEY_NUMBER.value: survey,
            ClaimType.PROPERTY_AREA.value: area,
            ClaimType.TAX_STATUS.value: "Paid",
        },
    )

    declaration = DocPlan(
        DocSpec(
            filename="Owner_Declaration.pdf",
            doc_type=DocumentType.OWNER_DECLARATION,
            title="OWNER SELF-DECLARATION",
            authority="Submitted through LandTrust Connect",
            reference="DECL-0006",
            issued_on=date(2026, 8, 26),
            pages=1,
            fields=[
                Field("Owner Name", owner, 1),
                Field("Survey Number", survey, 1),
                Field("Extent / Area", area, 1),
                Field("Mobile", "9345667788", 1),
            ],
            paragraphs=recitals_for(DocumentType.OWNER_DECLARATION, 1, seed=6),
            seal_text="Self-declared",
        ),
        expected_claims={ClaimType.OWNER_NAME.value: owner},
    )

    return ScenarioPlan(
        key="clean_title_madurai",
        label="Clean Title — Madurai",
        reference="LTC-PR-0006",
        survey_number=survey,
        district="Madurai",
        village="Anna Nagar",
        property_type="Residential Plot",
        claimed_area_sqft=1500,
        guideline_value_inr=36_00_000,
        asking_price_inr=39_50_000,
        listed_owner_name=owner,
        owner_name=owner,
        owner_email="fatima.begum@example.in",
        owner_phone="9345667788",
        owner_identity="XXXX XXXX 2048",
        summary=(
            "A straightforward file: deed, current encumbrance certificate, certified survey "
            "record and paid tax receipt, all consistent."
        ),
        documents=[deed, ec, survey_rec, tax, declaration],
        expected_state=TransactionState.PROCEED,
        expected_risk_band="LOW",
        expected_statuses={
            ClaimType.OWNER_NAME.value: VerificationStatus.VERIFIED,
            ClaimType.SURVEY_NUMBER.value: VerificationStatus.VERIFIED,
            ClaimType.PROPERTY_AREA.value: VerificationStatus.VERIFIED,
            ClaimType.MORTGAGE_STATUS.value: VerificationStatus.VERIFIED,
            ClaimType.TAX_STATUS.value: VerificationStatus.VERIFIED,
        },
        expected_contradiction_types=[],
        injected_anomalies=[],
        demo_note="Baseline comparison case for the low-risk end of the spectrum.",
    )


# ===========================================================================
def all_scenarios() -> list[ScenarioPlan]:
    return [case_a(), case_b(), case_c(), case_d(), case_e(), case_f()]


# Evidence that a buyer/owner can "obtain" during the resolution demonstration.
# These are generated but held back (is_pending_evidence=True) until applied.
def resolution_evidence(scenario_key: str) -> list[DocPlan]:
    if scenario_key != "area_conflict_active_mortgage":
        return []
    survey = "82/4B"
    owner = "Priya Sharma"
    return [
        DocPlan(
            DocSpec(
                filename="Encumbrance_Certificate_2026_current.pdf",
                doc_type=DocumentType.ENCUMBRANCE_CERTIFICATE,
                title="ENCUMBRANCE CERTIFICATE",
                authority="Office of the Sub-Registrar, Thiruporur, Chengalpattu District",
                reference="EC/CGL/2026/8814",
                issued_on=date(2026, 9, 2),
                pages=2,
                fields=[
                    Field("Certificate Number", "EC/CGL/2026/8814", 1),
                    Field("Claimant", owner, 1),
                    Field("Survey Number", survey, 1),
                    Field("Extent / Area", "1650 sq.ft", 1),
                    Field("Search Period", "01-01-2019 to 31-08-2026", 1),
                    Field("Encumbrance Status", "Released", 2),
                    Field("Mortgagee", "Sundaram Housing Finance Ltd", 2),
                ],
                paragraphs=[Para("The mortgage registered as MTG-2023-5512 stands released vide "
                                 "the discharge recorded on 21-08-2026.", 2)],
                seal_text="Registering Officer",
            ),
            expected_claims={
                ClaimType.MORTGAGE_STATUS.value: "Released",
                ClaimType.OWNER_NAME.value: owner,
            },
        ),
        DocPlan(
            DocSpec(
                filename="Bank_NOC_2026.pdf",
                doc_type=DocumentType.BANK_NOC,
                title="NO OBJECTION CERTIFICATE",
                authority="Sundaram Housing Finance Ltd, Chengalpattu Branch",
                reference="NOC/SHF/2026/1188",
                issued_on=date(2026, 8, 21),
                pages=1,
                fields=[
                    Field("Certificate Number", "NOC/SHF/2026/1188", 1),
                    Field("Borrower Name", owner, 1),
                    Field("Loan Account", "SHF/HL/2023/5512", 1),
                    Field("Survey Number", survey, 1),
                    Field("Charge Status", "Released", 1),
                    Field("Lender", "Sundaram Housing Finance Ltd", 1),
                ],
                paragraphs=recitals_for(DocumentType.BANK_NOC, 1, seed=88),
                seal_text="Branch Manager",
            ),
            expected_claims={ClaimType.MORTGAGE_STATUS.value: "Released"},
        ),
        DocPlan(
            DocSpec(
                filename="Survey_Record_2026_certified.pdf",
                doc_type=DocumentType.SURVEY_RECORD,
                title="SURVEY RECORD — FIELD MEASUREMENT BOOK EXTRACT",
                authority="Taluk Survey Office, Thiruporur",
                reference="FMB/TPR/2026/0455",
                issued_on=date(2026, 9, 1),
                pages=1,
                fields=[
                    Field("Certificate Number", "FMB/TPR/2026/0455", 1),
                    Field("Survey Number", survey, 1),
                    Field("Measured Area", "1800 sq.ft", 1),
                    Field("Pattadar Name", owner, 1),
                    Field("District", "Chengalpattu", 1),
                ],
                paragraphs=[Para("On re-measurement the extent of the schedule property is "
                                 "confirmed as 1800 sq.ft. The extent of 1650 sq.ft quoted in "
                                 "the certificate dated 18-11-2024 was recorded before the "
                                 "sub-division boundary was re-fixed.", 1)],
                seal_text="Taluk Surveyor",
            ),
            expected_claims={
                ClaimType.PROPERTY_AREA.value: "1800 sq.ft",
                ClaimType.SURVEY_NUMBER.value: survey,
                ClaimType.OWNER_NAME.value: owner,
            },
        ),
        DocPlan(
            DocSpec(
                filename="Name_Discrepancy_Affidavit_2026.pdf",
                doc_type=DocumentType.OWNER_DECLARATION,
                title="AFFIDAVIT OF NAME DISCREPANCY",
                authority="Sworn before a Notary Public, Chengalpattu",
                reference="AFF/2026/0912",
                issued_on=date(2026, 9, 3),
                pages=1,
                fields=[
                    Field("Owner Name", owner, 1),
                    Field("Survey Number", survey, 1),
                ],
                paragraphs=[Para("I solemnly affirm that 'Priya Sharma' and 'Priya S. Sharma' "
                                 "refer to one and the same person, namely the deponent, and that "
                                 "the middle initial denotes the deponent's father's name.", 1)],
                seal_text="Notary Public",
            ),
            expected_claims={ClaimType.OWNER_NAME.value: owner},
        ),
    ]
