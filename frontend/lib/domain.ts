/**
 * Domain vocabulary — mirrors backend/app/domain.py.
 *
 * Kept in sync by hand deliberately: the backend is the single source of truth and
 * this file only describes how each value is *presented*. If you add a status here
 * without adding it there, nothing will produce it.
 */

export type Role = "OWNER" | "BUYER" | "VERIFIER" | "LEGAL_REVIEWER" | "ADMIN";

export const ROLES: { role: Role; label: string; blurb: string }[] = [
  { role: "BUYER", label: "Buyer", blurb: "Sees the evidence-gated profile; masked values stay masked." },
  { role: "OWNER", label: "Land Owner", blurb: "Uploads evidence and decides every access request." },
  { role: "VERIFIER", label: "Verifier", blurb: "Full view of claims, contradictions and integrity indicators." },
  { role: "LEGAL_REVIEWER", label: "Legal Reviewer", blurb: "Handles escalated cases and the full audit trail." },
  { role: "ADMIN", label: "Administrator", blurb: "Platform operations, demo control and research dashboards." },
];

export type VerificationStatus =
  | "VERIFIED"
  | "PARTIALLY_VERIFIED"
  | "CONFLICTING"
  | "PENDING"
  | "EXPIRED"
  | "OWNER_PROVIDED"
  | "UNVERIFIED";

export const VERIFICATION_META: Record<
  VerificationStatus,
  { label: string; short: string; fg: string; bg: string; ring: string; meaning: string }
> = {
  VERIFIED: {
    label: "Verified",
    short: "VER",
    fg: "text-status-verified",
    bg: "bg-status-verifiedBg",
    ring: "ring-status-verified/25",
    meaning:
      "Corroborated by two or more independent documents, or asserted by the authority of record for this attribute.",
  },
  PARTIALLY_VERIFIED: {
    label: "Partially verified",
    short: "PART",
    fg: "text-status-partial",
    bg: "bg-status-partialBg",
    ring: "ring-status-partial/25",
    meaning:
      "Supported, but not enough to certify — a single non-authoritative source, or agreement that is close rather than exact.",
  },
  CONFLICTING: {
    label: "Conflicting",
    short: "CONF",
    fg: "text-status-conflicting",
    bg: "bg-status-conflictingBg",
    ring: "ring-status-conflicting/25",
    meaning: "Documents materially disagree. The value cannot be presented as verified.",
  },
  PENDING: {
    label: "Pending",
    short: "PEND",
    fg: "text-status-pending",
    bg: "bg-status-pendingBg",
    ring: "ring-status-pending/25",
    meaning: "Expected but not evidenced by any document on file.",
  },
  EXPIRED: {
    label: "Expired",
    short: "EXP",
    fg: "text-status-expired",
    bg: "bg-status-expiredBg",
    ring: "ring-status-expired/25",
    meaning: "The only supporting document is past its stated validity.",
  },
  OWNER_PROVIDED: {
    label: "Owner provided",
    short: "OWN",
    fg: "text-status-owner",
    bg: "bg-status-ownerBg",
    ring: "ring-status-owner/25",
    meaning: "Stated by the owner with no supporting document. Never shown as verified.",
  },
  UNVERIFIED: {
    label: "Unverified",
    short: "UNV",
    fg: "text-status-pending",
    bg: "bg-status-pendingBg",
    ring: "ring-status-pending/25",
    meaning: "No usable evidence supports this value.",
  },
};

export type TransactionState = "PROCEED" | "WARN" | "HOLD" | "ESCALATE" | "REJECT";

export const STATE_META: Record<
  TransactionState,
  { label: string; fg: string; bg: string; dot: string; blurb: string }
> = {
  PROCEED: {
    label: "Proceed",
    fg: "text-risk-low",
    bg: "bg-risk-lowBg",
    dot: "bg-risk-low",
    blurb: "Evidence supports progression. Continue with normal diligence.",
  },
  WARN: {
    label: "Warn",
    fg: "text-risk-moderate",
    bg: "bg-risk-moderateBg",
    dot: "bg-risk-moderate",
    blurb: "Open items exist. Review them before committing funds.",
  },
  HOLD: {
    label: "Hold",
    fg: "text-risk-high",
    bg: "bg-risk-highBg",
    dot: "bg-risk-high",
    blurb: "Progression blocked while unresolved evidence creates a high-risk condition.",
  },
  ESCALATE: {
    label: "Escalate",
    fg: "text-risk-critical",
    bg: "bg-risk-criticalBg",
    dot: "bg-risk-critical",
    blurb: "Requires review by a legal reviewer or authorised verifier.",
  },
  REJECT: {
    label: "Reject",
    fg: "text-risk-critical",
    bg: "bg-risk-criticalBg",
    dot: "bg-risk-critical",
    blurb: "Progression refused on the current evidence.",
  },
};

export type RiskBand = "LOW" | "MODERATE" | "HIGH" | "CRITICAL";

export const BAND_META: Record<RiskBand, { label: string; fg: string; bg: string; hex: string }> = {
  LOW: { label: "Low", fg: "text-risk-low", bg: "bg-risk-lowBg", hex: "#0f8a5f" },
  MODERATE: { label: "Moderate", fg: "text-risk-moderate", bg: "bg-risk-moderateBg", hex: "#b7791f" },
  HIGH: { label: "High", fg: "text-risk-high", bg: "bg-risk-highBg", hex: "#d2691e" },
  CRITICAL: { label: "Critical", fg: "text-risk-critical", bg: "bg-risk-criticalBg", hex: "#c62828" },
};

export type Severity = "INFO" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export const SEVERITY_META: Record<Severity, { label: string; fg: string; bg: string }> = {
  INFO: { label: "Info", fg: "text-status-info", bg: "bg-status-infoBg" },
  LOW: { label: "Low", fg: "text-status-pending", bg: "bg-status-pendingBg" },
  MEDIUM: { label: "Medium", fg: "text-status-partial", bg: "bg-status-partialBg" },
  HIGH: { label: "High", fg: "text-risk-high", bg: "bg-risk-highBg" },
  CRITICAL: { label: "Critical", fg: "text-risk-critical", bg: "bg-risk-criticalBg" },
};

export const DOC_TYPE_LABEL: Record<string, string> = {
  SALE_DEED: "Sale Deed",
  ENCUMBRANCE_CERTIFICATE: "Encumbrance Certificate",
  SURVEY_RECORD: "Survey Record",
  TAX_RECEIPT: "Tax Receipt",
  IDENTITY_PROOF: "Identity Proof",
  POWER_OF_ATTORNEY: "Power of Attorney",
  MORTGAGE_DOCUMENT: "Mortgage Document",
  BANK_NOC: "Bank NOC / Release",
  OWNER_DECLARATION: "Owner Declaration",
  UNKNOWN: "Unclassified",
};

export const PIPELINE_STAGES = [
  { key: "UPLOADING", label: "Uploading", detail: "Receiving and storing the file" },
  { key: "FILE_VALIDATION", label: "File validation", detail: "Type, size and checksum" },
  { key: "CLASSIFICATION", label: "Classification", detail: "Which kind of document is this" },
  { key: "OCR", label: "Text acquisition", detail: "Text layer, or OCR for scans" },
  { key: "LAYOUT_ANALYSIS", label: "Layout analysis", detail: "Blocks and word geometry" },
  { key: "CLAIM_EXTRACTION", label: "Claim extraction", detail: "Fields with page provenance" },
  { key: "EVIDENCE_LINKING", label: "Evidence linking", detail: "Anchoring claims to page regions" },
  { key: "CROSS_DOCUMENT_VALIDATION", label: "Cross-document validation", detail: "Comparing against every other document" },
  { key: "RISK_UPDATE", label: "Risk update", detail: "Recomputing score and transaction state" },
  { key: "COMPLETE", label: "Complete", detail: "" },
] as const;

export const WORKFLOW_STEPS = [
  { key: "upload", label: "Upload evidence", blurb: "Deeds, certificates, survey records, receipts" },
  { key: "extract", label: "Extract claims", blurb: "Each field bound to a document, page and region" },
  { key: "verify", label: "Verify evidence", blurb: "Status derived across documents, never from one" },
  { key: "graph", label: "Build ownership graph", blurb: "Parties, instruments and charges over time" },
  { key: "profile", label: "Create verified profile", blurb: "Disclosure gated on evidence and consent" },
  { key: "risk", label: "Assess transaction risk", blurb: "Explainable rules, every point traceable" },
  { key: "resolve", label: "Resolve issues", blurb: "The smallest set of documents that clears the hold" },
  { key: "decide", label: "Proceed or hold", blurb: "State enforced, not merely displayed" },
] as const;

export const CATEGORY_ORDER = [
  "OWNERSHIP",
  "ENCUMBRANCE",
  "SURVEY",
  "DOCUMENT",
  "VALUATION",
  "PAYMENT",
  "INTERACTION",
] as const;

export const DISCLAIMER =
  "Research prototype — decision-support only. LandTrust Connect does not replace official land records, registrar verification or legal advice.";
