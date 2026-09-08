"use client";

/**
 * Evidence-gated buyer profile for one property.
 *
 * The five sections are the research contribution made visible. A conventional
 * listing renders every owner-entered field with identical authority; here the
 * *status* is decided by the evidence first and the *visibility* by consent second,
 * so a buyer always learns whether a fact is supported even when they may not see
 * its value. Nothing on this page is re-ordered, re-worded or upgraded client-side:
 * the section a field appears in is the section the server put it in.
 */

import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  Ban,
  CalendarClock,
  ChevronDown,
  CircleAlert,
  Clock,
  FileCheck2,
  FileWarning,
  Handshake,
  Lock,
  MapPin,
  Ruler,
  ShieldCheck,
  ShieldQuestion,
  Timer,
  Unlock,
  User,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import React from "react";

import { Relay } from "@/components/relay";
import { useApi, useRole } from "@/components/hooks";
import {
  BandBadge,
  Button,
  Card,
  CardHeader,
  Chip,
  Disclaimer,
  Drawer,
  EmptyState,
  ErrorState,
  KeyValue,
  LoadingCard,
  MaskedValue,
  RiskGauge,
  SectionHeading,
  Skeleton,
  StateBadge,
  StatusBadge,
  Tooltip,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import {
  STATE_META,
  type RiskBand,
  type TransactionState,
  type VerificationStatus,
} from "@/lib/domain";
import { cn, dateTime, inr, pct, sqft, titleise } from "@/lib/format";

/* ------------------------------------------------------------------- types */

type ProfileField = {
  claim_type: string;
  label: string;
  value: string;
  raw_available: boolean;
  masked: boolean;
  mask_reason: string;
  verification_status: VerificationStatus;
  explanation: string;
  sensitivity: string;
  section: string;
  supporting_documents: number;
  conflicting_documents: number;
  unlockable_by: string | null;
};

type RestrictedItem = {
  item: string;
  label: string;
  policy: string;
  requestable: boolean;
};

type PropertySummary = {
  id: string;
  reference: string;
  survey_number: string;
  district: string;
  village: string;
  state: string;
  property_type: string;
  claimed_area_sqft: number | null;
  asking_price_inr: number | null;
  guideline_value_inr: number | null;
  scenario_label: string;
  document_count: number;
  contradiction_count: number;
  verification_level: number;
  risk_score: number;
  risk_band: RiskBand;
  transaction_state: TransactionState;
  transaction: {
    reference: string;
    state: TransactionState;
    state_reason: string;
    stage: string;
    consideration_inr: number | null;
    blocked_actions: string[];
  } | null;
};

type ProfileResponse = {
  property: PropertySummary;
  role: string;
  verification_level: number;
  granted_items: string[];
  restricted_items: RestrictedItem[];
  disclaimer: string;
  sections: Record<string, ProfileField[]>;
};

type ConsentItem = { item: string; label: string };

type ConsentRequest = {
  id: string;
  property_id: string;
  requester: { name: string; role: string } | null;
  items: ConsentItem[];
  granted_items: ConsentItem[];
  denied_items: ConsentItem[];
  purpose: string;
  status: string;
  decision_note: string;
  created_at: string;
  decided_at: string | null;
  expires_at: string | null;
};

type CatalogueItem = { item: string; label: string; requestable: boolean; policy: string };

type AttemptResult = {
  allowed: boolean;
  state: TransactionState;
  action: string;
  reason: string;
  banner?: string | null;
  note?: string | null;
};

/* ---------------------------------------------------------------- sections */

const SECTIONS: {
  key: string;
  title: string;
  meaning: string;
  accent: string;
  tint: string;
  fg: string;
  icon: React.ReactNode;
}[] = [
  {
    key: "verified",
    title: "Verified information",
    meaning:
      "Corroborated by two or more independent documents, or asserted by the authority of record for that attribute. Evidence-supported — not a certification of legal title.",
    accent: "border-l-status-verified",
    tint: "bg-status-verifiedBg/40",
    fg: "text-status-verified",
    icon: <ShieldCheck className="h-4 w-4" />,
  },
  {
    key: "partially_verified",
    title: "Partially verified",
    meaning:
      "Supported, but not enough to present as verified — a single non-authoritative source, agreement that is close rather than exact, or a document past its stated validity.",
    accent: "border-l-status-partial",
    tint: "bg-status-partialBg/50",
    fg: "text-status-partial",
    icon: <ShieldQuestion className="h-4 w-4" />,
  },
  {
    key: "conflicting",
    title: "Conflicting",
    meaning:
      "Documents on file materially disagree about this value. Both figures are kept visible; the platform does not choose a winner on the buyer’s behalf.",
    accent: "border-l-status-conflicting",
    tint: "bg-status-conflictingBg/50",
    fg: "text-status-conflicting",
    icon: <CircleAlert className="h-4 w-4" />,
  },
  {
    key: "owner_provided",
    title: "Owner provided / unverified",
    meaning:
      "Stated by the owner with no supporting document on file. Useful context, never presented as fact — this is the section a conventional listing does not have.",
    accent: "border-l-status-owner",
    tint: "bg-status-ownerBg/50",
    fg: "text-status-owner",
    icon: <User className="h-4 w-4" />,
  },
  {
    key: "pending",
    title: "Not evidenced (pending)",
    meaning:
      "Expected for a property of this kind, but no document on file speaks to it at all. An absence is itself information for a buyer.",
    accent: "border-l-status-pending",
    tint: "bg-status-pendingBg/60",
    fg: "text-status-pending",
    icon: <Clock className="h-4 w-4" />,
  },
];

const BLOCKING_STATES: TransactionState[] = ["HOLD", "ESCALATE", "REJECT"];

/* -------------------------------------------------------------- countdown */

function remainingLabel(expiresAt: string | null): { text: string; expired: boolean } {
  if (!expiresAt) return { text: "—", expired: false };
  // The API emits naive UTC timestamps; without the marker a browser outside UTC would
  // read the expiry as local time and count down to the wrong instant.
  const iso = /(?:Z|[+-]\d{2}:?\d{2})$/.test(expiresAt) ? expiresAt : `${expiresAt}Z`;
  const ms = new Date(iso).getTime() - Date.now();
  if (Number.isNaN(ms)) return { text: expiresAt, expired: false };
  if (ms <= 0) return { text: "expired", expired: true };
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  const s = Math.floor((ms % 60_000) / 1000);
  return { text: `${h}h ${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`, expired: false };
}

function Countdown({ expiresAt }: { expiresAt: string | null }) {
  const [, tick] = React.useState(0);
  React.useEffect(() => {
    const t = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);
  const { text, expired } = remainingLabel(expiresAt);
  return (
    <span
      className={cn(
        "tnum inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-2xs font-semibold ring-1",
        expired
          ? "bg-status-pendingBg text-status-pending ring-status-pending/20"
          : "bg-status-partialBg text-status-partial ring-status-partial/25",
      )}
    >
      <Timer className="h-3 w-3" />
      {expired ? "Grant expired" : `${text} left`}
    </span>
  );
}

/* --------------------------------------------------------------- the page */

export default function BuyerPropertyPage({ params }: { params: { id: string } }) {
  const id = params.id;
  const [role] = useRole();

  const profileQ = useApi<ProfileResponse>(() => endpoints.profile(id), [id, role]);
  const propertyQ = useApi<PropertySummary>(() => endpoints.property(id), [id, role]);
  const riskQ = useApi<{ overall_score: number; band: RiskBand; state: TransactionState; state_reason: string }>(
    () => endpoints.risk(id),
    [id, role],
  );
  const consentQ = useApi<{ count: number; items: ConsentRequest[] }>(
    () => endpoints.consentList(id),
    [id, role],
  );
  const catalogueQ = useApi<{ items: CatalogueItem[]; time_limited_hours: number }>(
    () => endpoints.consentItems(),
    [],
  );

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [attempt, setAttempt] = React.useState<AttemptResult | null>(null);
  const [attemptError, setAttemptError] = React.useState<string | null>(null);
  const [attempting, setAttempting] = React.useState<string | null>(null);

  const profile = profileQ.data;
  const property = profile?.property ?? propertyQ.data ?? null;
  const state = property?.transaction_state ?? "WARN";
  const blocked = BLOCKING_STATES.includes(state);

  async function tryAction(action: string) {
    setAttempting(action);
    setAttemptError(null);
    try {
      const res = await endpoints.attempt(id, action);
      setAttempt(res as AttemptResult);
    } catch (err: any) {
      setAttemptError(err?.detail || err?.message || "The action could not be evaluated.");
    } finally {
      setAttempting(null);
    }
  }

  if (profileQ.loading && !profile) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-8 w-64" />
        <LoadingCard rows={6} title="Property" />
        <div className="grid gap-4 lg:grid-cols-2">
          <LoadingCard rows={5} title="Verified information" />
          <LoadingCard rows={5} title="Restricted information" />
        </div>
      </div>
    );
  }

  if (profileQ.error || !profile || !property) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorState
          error={profileQ.error ?? "This property profile could not be loaded."}
          onRetry={profileQ.refetch}
        />
      </div>
    );
  }

  const meta = STATE_META[state] ?? STATE_META.WARN;
  const requests = consentQ.data?.items ?? [];
  const openRequest = requests.find((r) => r.status === "REQUESTED");

  return (
    <div className="space-y-6">
      <BackLink />

      {/* ------------------------------------------------------------ header */}
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-6 p-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="font-mono text-[13px] font-semibold text-navy-700">
                {property.reference}
              </span>
              <StateBadge state={state} />
              <Chip tone="neutral">{property.scenario_label}</Chip>
            </div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink">
              {property.property_type} · Survey {property.survey_number}
            </h1>
            <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-muted">
              <MapPin className="h-4 w-4 text-ink-subtle" />
              {property.village}, {property.district}, {property.state}
            </p>

            <dl className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <KeyValue
                label="Claimed area"
                value={
                  <span className="tnum">
                    <Ruler className="mr-1 inline h-3.5 w-3.5 text-ink-subtle" />
                    {sqft(property.claimed_area_sqft)}
                  </span>
                }
              />
              <KeyValue
                label="Asking price"
                value={
                  <span className="tnum font-semibold">
                    <Wallet className="mr-1 inline h-3.5 w-3.5 text-ink-subtle" />
                    {inr(property.asking_price_inr)}
                  </span>
                }
              />
              <KeyValue
                label="Guideline value"
                value={<span className="tnum">{inr(property.guideline_value_inr)}</span>}
              />
              <KeyValue
                label="Verification level"
                value={<span className="tnum">{pct(profile.verification_level)}</span>}
              />
            </dl>
          </div>

          <div className="shrink-0 lg:pl-6">
            {riskQ.loading ? (
              <Skeleton className="h-[120px] w-[180px]" />
            ) : riskQ.error || !riskQ.data ? (
              <div className="w-[180px] text-center">
                <div className="tnum text-3xl font-semibold text-ink">
                  {Math.round(property.risk_score)}
                </div>
                <div className="mt-1">
                  <BandBadge band={property.risk_band} />
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <RiskGauge score={riskQ.data.overall_score} band={riskQ.data.band} size={180} />
                <BandBadge band={riskQ.data.band} />
              </div>
            )}
          </div>
        </div>

        {/* Blocking banner: the state is enforced server-side, this only reports it. */}
        {blocked ? (
          <div
            className={cn(
              "flex items-start gap-3 border-t border-canvas-border px-5 py-4",
              meta.bg,
            )}
          >
            <Ban className={cn("mt-0.5 h-5 w-5 shrink-0", meta.fg)} />
            <div className="min-w-0">
              <p className={cn("text-sm font-semibold", meta.fg)}>
                {meta.label} — progression is blocked
              </p>
              <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">{meta.blurb}</p>
              {property.transaction?.state_reason ? (
                <p className="mt-1.5 text-[13px] leading-relaxed text-ink">
                  {property.transaction.state_reason}
                </p>
              ) : null}
              {property.transaction?.blocked_actions?.length ? (
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {property.transaction.blocked_actions.map((a) => (
                    <span
                      key={a}
                      className="inline-flex items-center gap-1.5 rounded-full bg-canvas-raised px-2 py-0.5 text-2xs font-semibold text-ink-muted ring-1 ring-canvas-border"
                    >
                      <Lock className="h-3 w-3" />
                      {titleise(a)}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        ) : null}

        {/* ---------------------------------------------------------- actions */}
        <div className="flex flex-wrap items-center gap-3 border-t border-canvas-border px-5 py-4">
          <ActionButton
            action="PROCEED_TO_AGREEMENT"
            label="Proceed to agreement"
            icon={<Handshake className="h-4 w-4" />}
            blocked={blocked}
            busy={attempting === "PROCEED_TO_AGREEMENT"}
            reason={property.transaction?.state_reason || meta.blurb}
            onClick={() => tryAction("PROCEED_TO_AGREEMENT")}
          />
          <ActionButton
            action="INITIATE_PAYMENT"
            label="Initiate payment"
            icon={<Wallet className="h-4 w-4" />}
            blocked={blocked}
            busy={attempting === "INITIATE_PAYMENT"}
            reason={property.transaction?.state_reason || meta.blurb}
            onClick={() => tryAction("INITIATE_PAYMENT")}
          />
          <Button variant="secondary" onClick={() => setDrawerOpen(true)}>
            <Unlock className="h-4 w-4" />
            Request owner access
          </Button>
          <p className="text-2xs leading-relaxed text-ink-subtle">
            Blocked actions still call the server — the refusal, with its reason, is the
            demonstration.
          </p>
        </div>

        <AnimatePresence>
          {attempt ? (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden border-t border-canvas-border"
            >
              <div
                className={cn(
                  "flex items-start gap-3 px-5 py-4",
                  attempt.allowed ? "bg-status-verifiedBg/60" : "bg-status-conflictingBg/60",
                )}
              >
                {attempt.allowed ? (
                  <FileCheck2 className="mt-0.5 h-4 w-4 shrink-0 text-status-verified" />
                ) : (
                  <Ban className="mt-0.5 h-4 w-4 shrink-0 text-status-conflicting" />
                )}
                <div className="min-w-0 flex-1">
                  <p
                    className={cn(
                      "text-[13px] font-semibold",
                      attempt.allowed ? "text-status-verified" : "text-status-conflicting",
                    )}
                  >
                    {titleise(attempt.action)} —{" "}
                    {attempt.allowed ? "permitted in this state" : "refused in this state"}
                  </p>
                  {attempt.banner ? (
                    <p className="mt-1 text-[13px] font-medium text-ink">{attempt.banner}</p>
                  ) : null}
                  <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
                    {attempt.reason}
                  </p>
                  {attempt.note ? (
                    <p className="mt-1 text-2xs leading-relaxed text-ink-subtle">{attempt.note}</p>
                  ) : null}
                </div>
                <button
                  onClick={() => setAttempt(null)}
                  className="text-2xs font-semibold uppercase tracking-[0.1em] text-ink-subtle hover:text-ink"
                >
                  Dismiss
                </button>
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>

        {attemptError ? (
          <p className="border-t border-canvas-border bg-status-conflictingBg/50 px-5 py-3 text-[13px] text-status-conflicting">
            {attemptError}
          </p>
        ) : null}
      </Card>

      {/* ----------------------------------------------------------- profile */}
      <div>
        <SectionHeading
          eyebrow="Evidence-gated profile"
          title="What the documents actually support"
          description="Five sections, in descending order of evidential strength. A field's section is decided by the verification engine on the server; nothing here is promoted for presentation."
        />
        <div className="space-y-4">
          {SECTIONS.map((section) => (
            <ProfileSection
              key={section.key}
              section={section}
              fields={profile.sections?.[section.key] ?? []}
            />
          ))}
        </div>
      </div>

      {/* -------------------------------------------- restricted information */}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <RestrictedPanel
          items={profile.restricted_items ?? []}
          granted={profile.granted_items ?? []}
          onRequest={() => setDrawerOpen(true)}
        />
        <ConsentRequestsPanel
          loading={consentQ.loading}
          error={consentQ.error}
          onRetry={consentQ.refetch}
          requests={requests}
          hours={catalogueQ.data?.time_limited_hours ?? 24}
        />
      </div>

      <Relay propertyId={id} />

      <Disclaimer text={profile.disclaimer} />

      <RequestAccessDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        propertyId={id}
        propertyReference={property.reference}
        catalogue={catalogueQ.data?.items ?? []}
        catalogueLoading={catalogueQ.loading}
        catalogueError={catalogueQ.error}
        granted={profile.granted_items ?? []}
        pending={openRequest ?? null}
        onSubmitted={() => {
          consentQ.refetch();
          profileQ.refetch();
        }}
      />
    </div>
  );
}

/* -------------------------------------------------------------- fragments */

function BackLink() {
  return (
    <Link
      href="/buyer"
      className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ink-muted transition hover:text-ink"
    >
      <ArrowLeft className="h-3.5 w-3.5" />
      All listings
    </Link>
  );
}

/**
 * A blocked action is rendered as disabled *and* still calls the server when clicked:
 * the refusal it returns, with its rule and reason, is the point of the screen.
 */
function ActionButton({
  action,
  label,
  icon,
  blocked,
  busy,
  reason,
  onClick,
}: {
  action: string;
  label: string;
  icon: React.ReactNode;
  blocked: boolean;
  busy: boolean;
  reason: string;
  onClick: () => void;
}) {
  const button = (
    <button
      onClick={onClick}
      aria-disabled={blocked}
      data-action={action}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition",
        blocked
          ? "cursor-not-allowed bg-canvas-sunken text-ink-subtle ring-1 ring-canvas-borderStrong"
          : "bg-navy-900 text-white hover:bg-navy-800",
        busy && "opacity-70",
      )}
    >
      {blocked ? <Lock className="h-4 w-4" /> : icon}
      {label}
    </button>
  );
  return (
    <Tooltip
      content={
        blocked
          ? `Disabled in the current transaction state. ${reason} Selecting it anyway will show the server’s refusal.`
          : "Permitted in the current state. This prototype never processes a payment."
      }
    >
      {button}
    </Tooltip>
  );
}

function ProfileSection({
  section,
  fields,
}: {
  section: (typeof SECTIONS)[number];
  fields: ProfileField[];
}) {
  return (
    <Card className={cn("overflow-hidden border-l-4", section.accent)}>
      <div className={cn("flex flex-wrap items-start justify-between gap-3 px-5 py-4", section.tint)}>
        <div className="min-w-0">
          <h3 className={cn("flex items-center gap-2 text-[15px] font-semibold", section.fg)}>
            {section.icon}
            {section.title}
          </h3>
          <p className="mt-1 max-w-3xl text-[13px] leading-relaxed text-ink-muted">
            {section.meaning}
          </p>
        </div>
        <span className="tnum shrink-0 rounded-full bg-canvas-raised px-2.5 py-1 text-2xs font-semibold text-ink-muted ring-1 ring-canvas-border">
          {fields.length} {fields.length === 1 ? "attribute" : "attributes"}
        </span>
      </div>

      {fields.length === 0 ? (
        <p className="px-5 py-4 text-[13px] text-ink-subtle">
          No attribute falls into this section for this property.
        </p>
      ) : (
        <ul className="divide-y divide-canvas-border">
          {fields.map((f) => (
            <ProfileFieldRow key={f.claim_type} field={f} />
          ))}
        </ul>
      )}
    </Card>
  );
}

function ProfileFieldRow({ field }: { field: ProfileField }) {
  const [open, setOpen] = React.useState(false);
  return (
    <li>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5 text-left transition hover:bg-canvas-sunken/50"
      >
        <div className="min-w-[168px] flex-1">
          <div className="section-label">{field.label}</div>
          <div className="mt-1 text-sm text-ink">
            {field.masked ? (
              <MaskedValue value={field.value} reason={field.mask_reason} />
            ) : (
              <span className="font-medium">{field.value}</span>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={field.verification_status} size="sm" />
          {field.supporting_documents > 0 ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-status-verifiedBg px-2 py-0.5 text-2xs font-semibold text-status-verified ring-1 ring-status-verified/20">
              <FileCheck2 className="h-3 w-3" />
              <span className="tnum">{field.supporting_documents}</span> supporting
            </span>
          ) : null}
          {field.conflicting_documents > 0 ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-status-conflictingBg px-2 py-0.5 text-2xs font-semibold text-status-conflicting ring-1 ring-status-conflicting/20">
              <FileWarning className="h-3 w-3" />
              <span className="tnum">{field.conflicting_documents}</span> conflicting
            </span>
          ) : null}
          {field.masked && field.unlockable_by ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-canvas-sunken px-2 py-0.5 text-2xs font-medium text-ink-muted ring-1 ring-canvas-border">
              <Lock className="h-3 w-3" />
              Unlocks with {titleise(field.unlockable_by)}
            </span>
          ) : null}
          <ChevronDown
            className={cn("h-4 w-4 text-ink-subtle transition", open && "rotate-180")}
          />
        </div>
      </button>

      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <div className="space-y-2 bg-canvas-sunken/50 px-5 py-3.5">
              <div>
                <div className="section-label">Why this status</div>
                <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
                  {field.explanation || "No explanation was returned for this attribute."}
                </p>
              </div>
              {field.masked ? (
                <div>
                  <div className="section-label">Why this value is masked</div>
                  <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
                    {field.mask_reason}
                  </p>
                </div>
              ) : null}
              <div className="flex flex-wrap gap-2 pt-0.5">
                <Chip tone="neutral">Sensitivity: {titleise(field.sensitivity)}</Chip>
                <Chip tone="neutral">Attribute: {field.claim_type}</Chip>
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </li>
  );
}

function RestrictedPanel({
  items,
  granted,
  onRequest,
}: {
  items: RestrictedItem[];
  granted: string[];
  onRequest: () => void;
}) {
  const requestable = items.filter((i) => i.requestable);
  const never = items.filter((i) => !i.requestable);

  return (
    <Card>
      <CardHeader
        icon={<Lock className="h-4 w-4" />}
        title="Restricted information"
        subtitle="What is withheld from this profile, and on what terms it can be released."
        action={
          <Button size="sm" variant="secondary" onClick={onRequest}>
            Request access
          </Button>
        }
      />
      <div className="space-y-4 px-5 py-4">
        <div>
          <div className="section-label mb-2">Releasable with owner consent</div>
          <ul className="space-y-2">
            {requestable.map((i) => {
              const isGranted = granted.includes(i.item);
              return (
                <li
                  key={i.item}
                  className="flex flex-wrap items-start justify-between gap-2 rounded-xl bg-canvas-sunken/60 px-3.5 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium text-ink">{i.label}</p>
                    <p className="mt-0.5 text-2xs leading-relaxed text-ink-muted">{i.policy}</p>
                  </div>
                  {isGranted ? (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-status-verifiedBg px-2 py-0.5 text-2xs font-semibold text-status-verified ring-1 ring-status-verified/20">
                      <Unlock className="h-3 w-3" />
                      Granted
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-canvas-raised px-2 py-0.5 text-2xs font-medium text-ink-muted ring-1 ring-canvas-border">
                      <Lock className="h-3 w-3" />
                      Withheld
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>

        {/* Identity is not a missing feature. The platform verifies identity on its own
            side and shares only the outcome, so there is no consent path that releases
            the document itself — that refusal is deliberate and permanent. */}
        {never.length ? (
          <div className="rounded-xl border border-status-conflicting/25 bg-status-conflictingBg/50 px-4 py-3.5">
            <div className="flex items-center gap-2 text-status-conflicting">
              <Ban className="h-4 w-4" />
              <span className="text-[13px] font-semibold">Never disclosed — by policy</span>
            </div>
            <ul className="mt-2 space-y-2">
              {never.map((i) => (
                <li key={i.item}>
                  <p className="text-[13px] font-medium text-ink">{i.label}</p>
                  <p className="mt-0.5 text-[13px] leading-relaxed text-ink-muted">{i.policy}</p>
                </li>
              ))}
            </ul>
            <p className="mt-2.5 text-2xs leading-relaxed text-ink-muted">
              This item cannot be requested, and an owner approval that includes it is stripped
              before it takes effect. Identity is checked on the platform’s side and only the
              outcome is shared — there is no path through this interface that releases the
              document.
            </p>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

function ConsentRequestsPanel({
  loading,
  error,
  onRetry,
  requests,
  hours,
}: {
  loading: boolean;
  error: any;
  onRetry: () => void;
  requests: ConsentRequest[];
  hours: number;
}) {
  return (
    <Card>
      <CardHeader
        icon={<CalendarClock className="h-4 w-4" />}
        title="Access requests on this property"
        subtitle={`Approvals may be time-limited; a ${hours}-hour grant lapses on its own without anyone acting.`}
      />
      <div className="px-5 py-4">
        {loading ? (
          <LoadingCard rows={3} />
        ) : error ? (
          <ErrorState error={error} onRetry={onRetry} />
        ) : requests.length === 0 ? (
          <EmptyState
            title="No access requests yet"
            description="Ask the owner to release a specific document or detail. Every request states its purpose and is recorded."
            icon={<Lock className="h-5 w-5" />}
          />
        ) : (
          <ul className="space-y-3">
            {requests.map((r) => (
              <li key={r.id} className="rounded-xl border border-canvas-border px-4 py-3.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <ConsentStatusBadge status={r.status} />
                  <span className="text-2xs text-ink-subtle">
                    requested {dateTime(r.created_at)}
                  </span>
                </div>
                {r.purpose ? (
                  <p className="mt-2 text-[13px] leading-relaxed text-ink">“{r.purpose}”</p>
                ) : null}
                <div className="mt-2.5 space-y-1.5">
                  <ItemLine label="Requested" items={r.items} tone="neutral" />
                  {r.granted_items.length ? (
                    <ItemLine label="Granted" items={r.granted_items} tone="emerald" />
                  ) : null}
                  {r.denied_items.length ? (
                    <ItemLine label="Withheld" items={r.denied_items} tone="red" />
                  ) : null}
                </div>
                {r.status === "APPROVED_TIME_LIMITED" ? (
                  <div className="mt-2.5 flex flex-wrap items-center gap-2">
                    <Countdown expiresAt={r.expires_at} />
                    <span className="text-2xs text-ink-subtle">
                      expires {dateTime(r.expires_at)}
                    </span>
                  </div>
                ) : null}
                {r.decision_note ? (
                  <p className="mt-2 text-2xs leading-relaxed text-ink-muted">
                    Owner note: {r.decision_note}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

function ItemLine({
  label,
  items,
  tone,
}: {
  label: string;
  items: ConsentItem[];
  tone: "neutral" | "emerald" | "red";
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="section-label">{label}</span>
      {items.map((i) => (
        <Chip key={`${label}-${i.item}`} tone={tone}>
          {i.label}
        </Chip>
      ))}
    </div>
  );
}

function ConsentStatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    REQUESTED: "bg-status-infoBg text-status-info ring-status-info/20",
    APPROVED: "bg-status-verifiedBg text-status-verified ring-status-verified/20",
    APPROVED_TIME_LIMITED: "bg-status-partialBg text-status-partial ring-status-partial/25",
    DENIED: "bg-status-conflictingBg text-status-conflicting ring-status-conflicting/20",
    EXPIRED: "bg-status-pendingBg text-status-pending ring-status-pending/20",
    REVOKED: "bg-status-pendingBg text-status-pending ring-status-pending/20",
  };
  const label: Record<string, string> = {
    REQUESTED: "Awaiting owner decision",
    APPROVED: "Approved",
    APPROVED_TIME_LIMITED: "Approved · time-limited",
    DENIED: "Denied",
    EXPIRED: "Expired automatically",
    REVOKED: "Revoked by owner",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-2xs font-semibold uppercase tracking-[0.08em] ring-1",
        map[status] ?? "bg-canvas-sunken text-ink-muted ring-canvas-border",
      )}
    >
      {label[status] ?? titleise(status)}
    </span>
  );
}

function RequestAccessDrawer({
  open,
  onClose,
  propertyId,
  propertyReference,
  catalogue,
  catalogueLoading,
  catalogueError,
  granted,
  pending,
  onSubmitted,
}: {
  open: boolean;
  onClose: () => void;
  propertyId: string;
  propertyReference: string;
  catalogue: CatalogueItem[];
  catalogueLoading: boolean;
  catalogueError: any;
  granted: string[];
  pending: ConsentRequest | null;
  onSubmitted: () => void;
}) {
  const [selected, setSelected] = React.useState<string[]>([]);
  const [purpose, setPurpose] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [result, setResult] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  function toggle(item: string) {
    setSelected((prev) =>
      prev.includes(item) ? prev.filter((i) => i !== item) : [...prev, item],
    );
  }

  async function submit() {
    if (selected.length === 0 || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await endpoints.requestConsent({
        property_id: propertyId,
        items: selected,
        purpose: purpose.trim(),
      });
      setResult(
        [
          "Request sent. The owner decides item by item, and may grant access for a limited window.",
          // The server reports anything it refused to carry into the request at all.
          res?.notice,
        ]
          .filter(Boolean)
          .join(" "),
      );
      setSelected([]);
      setPurpose("");
      onSubmitted();
    } catch (err: any) {
      setError(err?.detail || err?.message || "The request could not be sent.");
    } finally {
      setSubmitting(false);
    }
  }

  const requestable = catalogue.filter((i) => i.requestable);
  const never = catalogue.filter((i) => !i.requestable);

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="Request owner access"
      subtitle={`Property ${propertyReference} · the owner decides each item separately and can withdraw a grant at any time.`}
    >
      {catalogueLoading ? (
        <LoadingCard rows={6} />
      ) : catalogueError ? (
        <ErrorState error={catalogueError} />
      ) : (
        <div className="space-y-5">
          {pending ? (
            <div className="rounded-xl bg-status-infoBg px-4 py-3 ring-1 ring-status-info/20">
              <p className="text-[13px] font-semibold text-status-info">
                A request is already awaiting the owner’s decision
              </p>
              <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
                Requested {dateTime(pending.created_at)} for{" "}
                {pending.items.map((i) => i.label).join(", ")}.
              </p>
            </div>
          ) : null}

          {result ? (
            <div className="rounded-xl bg-status-verifiedBg px-4 py-3 ring-1 ring-status-verified/20">
              <p className="text-[13px] leading-relaxed text-status-verified">{result}</p>
            </div>
          ) : null}

          {error ? (
            <div className="rounded-xl bg-status-conflictingBg px-4 py-3 ring-1 ring-status-conflicting/20">
              <p className="text-[13px] leading-relaxed text-status-conflicting">{error}</p>
            </div>
          ) : null}

          <div>
            <div className="section-label mb-2">Items you can request</div>
            <ul className="space-y-2">
              {requestable.map((i) => {
                const alreadyGranted = granted.includes(i.item);
                return (
                  <li key={i.item}>
                    <label
                      className={cn(
                        "flex cursor-pointer items-start gap-3 rounded-xl border px-3.5 py-3 transition",
                        selected.includes(i.item)
                          ? "border-navy-400 bg-navy-50"
                          : "border-canvas-border hover:bg-canvas-sunken/60",
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={selected.includes(i.item)}
                        onChange={() => toggle(i.item)}
                        className="mt-0.5 h-4 w-4 shrink-0 accent-navy-900"
                      />
                      <span className="min-w-0">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="text-[13px] font-medium text-ink">{i.label}</span>
                          {alreadyGranted ? (
                            <span className="rounded-full bg-status-verifiedBg px-2 py-0.5 text-2xs font-semibold text-status-verified ring-1 ring-status-verified/20">
                              already granted
                            </span>
                          ) : null}
                        </span>
                        <span className="mt-0.5 block text-2xs leading-relaxed text-ink-muted">
                          {i.policy}
                        </span>
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </div>

          {never.length ? (
            <div>
              <div className="section-label mb-2">Not requestable</div>
              <ul className="space-y-2">
                {never.map((i) => (
                  <li
                    key={i.item}
                    className="flex items-start gap-3 rounded-xl border border-dashed border-status-conflicting/30 bg-status-conflictingBg/40 px-3.5 py-3"
                  >
                    <input
                      type="checkbox"
                      disabled
                      checked={false}
                      readOnly
                      className="mt-0.5 h-4 w-4 shrink-0 cursor-not-allowed"
                    />
                    <div className="min-w-0">
                      <p className="text-[13px] font-medium text-ink-muted line-through">
                        {i.label}
                      </p>
                      <p className="mt-0.5 text-2xs leading-relaxed text-ink-muted">{i.policy}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div>
            <label className="section-label mb-2 block" htmlFor="consent-purpose">
              Purpose of the request
            </label>
            <textarea
              id="consent-purpose"
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
              rows={4}
              placeholder="Explain why you need each item — the purpose is stored with the request and shown to the owner."
              className="w-full resize-y rounded-xl border border-canvas-borderStrong bg-canvas-raised px-3.5 py-2.5 text-[13.5px] leading-relaxed text-ink placeholder:text-ink-subtle focus:border-navy-400"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={submit} disabled={selected.length === 0 || submitting}>
              {submitting ? "Sending…" : `Send request (${selected.length})`}
            </Button>
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </Drawer>
  );
}
