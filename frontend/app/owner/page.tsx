"use client";

/**
 * Owner portal.
 *
 * The owner's side of the consent gate: every disclosure is decided item by item,
 * a grant can be limited to a window that closes on its own, and identity documents
 * are withheld even from an "approve everything" decision.
 */

import { motion } from "framer-motion";
import {
  Ban,
  Building2,
  CalendarClock,
  CheckCheck,
  Eye,
  Info,
  Lock,
  ShieldCheck,
  SlidersHorizontal,
  Timer,
  Unlock,
  UserCog,
  X,
} from "lucide-react";
import Link from "next/link";
import React from "react";

import { useApi, useRole } from "@/components/hooks";
import {
  BandBadge,
  Button,
  Card,
  CardHeader,
  Chip,
  Disclaimer,
  EmptyState,
  ErrorState,
  LoadingCard,
  SectionHeading,
  StateBadge,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import type { RiskBand, TransactionState } from "@/lib/domain";
import { cn, dateTime, pct, relative, titleise } from "@/lib/format";

/* ------------------------------------------------------------------- types */

type PropertySummary = {
  id: string;
  reference: string;
  survey_number: string;
  district: string;
  village: string;
  property_type: string;
  scenario_label: string;
  document_count: number;
  contradiction_count: number;
  verification_level: number;
  verification_counts: Record<string, number>;
  risk_score: number;
  risk_band: RiskBand;
  transaction_state: TransactionState;
};

type ConsentItem = { item: string; label: string };

type ConsentRequest = {
  id: string;
  property_id: string;
  requester: { name: string; role: string; organisation?: string } | null;
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

const NEVER_DISCLOSED = "IDENTITY_DOCUMENT";

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
  return {
    text: `${h}h ${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`,
    expired: false,
  };
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

function ConsentStatusBadge({ status }: { status: string }) {
  const tone: Record<string, string> = {
    REQUESTED: "bg-status-infoBg text-status-info ring-status-info/20",
    APPROVED: "bg-status-verifiedBg text-status-verified ring-status-verified/20",
    APPROVED_TIME_LIMITED: "bg-status-partialBg text-status-partial ring-status-partial/25",
    DENIED: "bg-status-conflictingBg text-status-conflicting ring-status-conflicting/20",
    EXPIRED: "bg-status-pendingBg text-status-pending ring-status-pending/20",
    REVOKED: "bg-status-pendingBg text-status-pending ring-status-pending/20",
  };
  const label: Record<string, string> = {
    REQUESTED: "Awaiting your decision",
    APPROVED: "Approved",
    APPROVED_TIME_LIMITED: "Approved · time-limited",
    DENIED: "Denied",
    EXPIRED: "Expired automatically",
    REVOKED: "Revoked",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-2xs font-semibold uppercase tracking-[0.08em] ring-1",
        tone[status] ?? "bg-canvas-sunken text-ink-muted ring-canvas-border",
      )}
    >
      {label[status] ?? titleise(status)}
    </span>
  );
}

/* --------------------------------------------------------------- the page */

export default function OwnerPortalPage() {
  const [role] = useRole();

  const propertiesQ = useApi<{ count: number; items: PropertySummary[] }>(
    () => endpoints.properties(),
    [role],
  );
  const consentQ = useApi<{ count: number; items: ConsentRequest[] }>(
    () => endpoints.consentList(),
    [role],
  );
  const catalogueQ = useApi<{ items: CatalogueItem[]; time_limited_hours: number }>(
    () => endpoints.consentItems(),
    [],
  );

  const properties = propertiesQ.data?.items ?? [];
  const requests = consentQ.data?.items ?? [];
  const hours = catalogueQ.data?.time_limited_hours ?? 24;

  const propertyById = React.useMemo(() => {
    const map: Record<string, PropertySummary> = {};
    for (const p of properties) map[p.id] = p;
    return map;
  }, [properties]);

  const openCountFor = React.useCallback(
    (propertyId: string) =>
      requests.filter((r) => r.property_id === propertyId && r.status === "REQUESTED").length,
    [requests],
  );

  const pending = requests.filter((r) => r.status === "REQUESTED");
  const decided = requests.filter((r) => r.status !== "REQUESTED");

  return (
    <div className="space-y-8">
      <SectionHeading
        eyebrow="Owner portal"
        title="Your properties, and everything anyone has asked to see"
        description="Disclosure on this platform is not a switch between public and private. Each item is decided on its own, an approval can be limited to a window that closes without anyone acting, and identity documents are withheld from every grant."
      />

      {role !== "OWNER" ? (
        <div className="flex items-start gap-3 rounded-xl bg-status-infoBg px-4 py-3.5 ring-1 ring-status-info/20">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-status-info" />
          <div>
            <p className="text-[13px] font-semibold text-status-info">
              You are viewing this as {titleise(role)}
            </p>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
              Consent decisions are authorised server-side and require the Land Owner role. Switch
              role using the switcher in the top bar to approve, limit or revoke access — the
              buttons below will send an owner decision, but the surrounding views still reflect
              the role you are in.
            </p>
          </div>
        </div>
      ) : null}

      {/* --------------------------------------------------- my properties */}
      <section>
        <SectionHeading
          eyebrow="1 · Portfolio"
          title="My properties"
          description="Verification status, risk and transaction state as they stand on the current evidence."
        />
        {propertiesQ.loading ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <LoadingCard key={i} rows={6} />
            ))}
          </div>
        ) : propertiesQ.error ? (
          <ErrorState error={propertiesQ.error} onRetry={propertiesQ.refetch} />
        ) : properties.length === 0 ? (
          <EmptyState title="No properties on file" icon={<Building2 className="h-5 w-5" />} />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {properties.map((p, i) => (
              <OwnerPropertyCard
                key={p.id}
                property={p}
                openRequests={openCountFor(p.id)}
                index={i}
              />
            ))}
          </div>
        )}
      </section>

      {/* -------------------------------------------------- access requests */}
      <section>
        <SectionHeading
          eyebrow="2 · Consent"
          title="Access requests"
          description={`Approve everything, approve only the items you choose, or grant access for ${hours} hours and let it lapse on its own. Nothing is released until you decide.`}
          action={
            <div className="flex items-center gap-2">
              <Chip tone={pending.length ? "amber" : "neutral"}>
                <span className="tnum">{pending.length}</span> awaiting decision
              </Chip>
              <Chip tone="neutral">
                <span className="tnum">{decided.length}</span> decided
              </Chip>
            </div>
          }
        />

        {consentQ.loading ? (
          <LoadingCard rows={6} />
        ) : consentQ.error ? (
          <ErrorState error={consentQ.error} onRetry={consentQ.refetch} />
        ) : requests.length === 0 ? (
          <EmptyState
            title="No one has requested access yet"
            description="When a buyer asks for a document or a masked detail, the request appears here with the purpose they stated."
            icon={<Lock className="h-5 w-5" />}
          />
        ) : (
          <div className="space-y-4">
            {[...pending, ...decided].map((r) => (
              <RequestCard
                key={r.id}
                request={r}
                property={propertyById[r.property_id] ?? null}
                hours={hours}
                onChanged={() => {
                  consentQ.refetch();
                  propertiesQ.refetch();
                }}
              />
            ))}
          </div>
        )}
      </section>

      {/* ------------------------------------------------- consent controls */}
      <section>
        <SectionHeading
          eyebrow="3 · Policy"
          title="Consent controls"
          description="Every disclosure item this platform knows about, and the terms on which it can ever leave your file."
        />
        <Card>
          <CardHeader
            icon={<SlidersHorizontal className="h-4 w-4" />}
            title="Disclosure catalogue"
            subtitle={`Time-limited grants last ${hours} hours from approval.`}
          />
          {catalogueQ.loading ? (
            <div className="p-5">
              <LoadingCard rows={5} />
            </div>
          ) : catalogueQ.error ? (
            <div className="p-5">
              <ErrorState error={catalogueQ.error} onRetry={catalogueQ.refetch} />
            </div>
          ) : (
            <div className="scroll-x">
              <table className="table-grid min-w-[720px]">
                <thead>
                  <tr>
                    <th className="w-[28%]">Disclosure item</th>
                    <th className="w-[18%]">Can be requested</th>
                    <th>Policy</th>
                  </tr>
                </thead>
                <tbody>
                  {(catalogueQ.data?.items ?? []).map((i) => (
                    <tr key={i.item}>
                      <td>
                        <div className="text-[13px] font-medium text-ink">{i.label}</div>
                        <div className="mt-0.5 font-mono text-2xs text-ink-subtle">{i.item}</div>
                      </td>
                      <td>
                        {i.requestable ? (
                          <span className="inline-flex items-center gap-1.5 rounded-full bg-status-verifiedBg px-2 py-0.5 text-2xs font-semibold text-status-verified ring-1 ring-status-verified/20">
                            <Unlock className="h-3 w-3" />
                            With your consent
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 rounded-full bg-status-conflictingBg px-2 py-0.5 text-2xs font-semibold text-status-conflicting ring-1 ring-status-conflicting/20">
                            <Ban className="h-3 w-3" />
                            Never
                          </span>
                        )}
                      </td>
                      <td className="text-[13px] leading-relaxed text-ink-muted">{i.policy}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </section>

      <Disclaimer />
    </div>
  );
}

/* -------------------------------------------------------------- fragments */

function OwnerPropertyCard({
  property: p,
  openRequests,
  index,
}: {
  property: PropertySummary;
  openRequests: number;
  index: number;
}) {
  const level = Math.round((p.verification_level ?? 0) * 100);
  const verified = p.verification_counts?.VERIFIED ?? 0;
  const conflicting = p.verification_counts?.CONFLICTING ?? 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.04, 0.24) }}
    >
      <Card className="flex h-full flex-col p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="font-mono text-[13px] font-semibold text-navy-700">{p.reference}</div>
            <p className="mt-1 text-[15px] font-semibold leading-tight text-ink">
              {p.property_type} · Survey {p.survey_number}
            </p>
            <p className="mt-0.5 text-2xs text-ink-subtle">
              {p.village}, {p.district} · {p.scenario_label}
            </p>
          </div>
          <StateBadge state={p.transaction_state} size="sm" />
        </div>

        <div className="mt-4">
          <div className="flex items-center justify-between text-2xs">
            <span className="section-label">Verification level</span>
            <span className="tnum text-ink-muted">{pct(p.verification_level)}</span>
          </div>
          <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-canvas-sunken">
            <div
              className={cn(
                "h-full rounded-full",
                level >= 70
                  ? "bg-status-verified"
                  : level >= 40
                    ? "bg-status-partial"
                    : "bg-status-conflicting",
              )}
              style={{ width: `${Math.max(level, 2)}%` }}
            />
          </div>
          <div className="mt-2.5 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-status-verifiedBg px-2 py-0.5 text-2xs font-semibold text-status-verified ring-1 ring-status-verified/20">
              <span className="tnum">{verified}</span> verified
            </span>
            {conflicting ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-status-conflictingBg px-2 py-0.5 text-2xs font-semibold text-status-conflicting ring-1 ring-status-conflicting/20">
                <span className="tnum">{conflicting}</span> conflicting
              </span>
            ) : null}
            <span className="inline-flex items-center gap-1.5 rounded-full bg-canvas-sunken px-2 py-0.5 text-2xs font-medium text-ink-muted ring-1 ring-canvas-border">
              <span className="tnum">{p.document_count}</span> documents
            </span>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <BandBadge band={p.risk_band} />
          <span className="tnum text-2xs text-ink-subtle">{Math.round(p.risk_score)}/100</span>
          <span
            className={cn(
              "ml-auto inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-2xs font-semibold ring-1",
              openRequests
                ? "bg-status-infoBg text-status-info ring-status-info/20"
                : "bg-canvas-sunken text-ink-subtle ring-canvas-border",
            )}
          >
            <Lock className="h-3 w-3" />
            <span className="tnum">{openRequests}</span> open request
            {openRequests === 1 ? "" : "s"}
          </span>
        </div>

        <div className="mt-4 flex flex-wrap gap-2 border-t border-canvas-border pt-4">
          <Link href={`/properties/${p.reference}`} className="flex-1">
            <Button variant="secondary" size="sm" className="w-full">
              <ShieldCheck className="h-3.5 w-3.5" />
              Open workspace
            </Button>
          </Link>
          {/* An owner needs to know what a stranger can read about their property. */}
          <Link href={`/buyer/${p.reference}`} className="flex-1">
            <Button variant="subtle" size="sm" className="w-full">
              <Eye className="h-3.5 w-3.5" />
              See what a buyer sees
            </Button>
          </Link>
        </div>
      </Card>
    </motion.div>
  );
}

function RequestCard({
  request: r,
  property,
  hours,
  onChanged,
}: {
  request: ConsentRequest;
  property: PropertySummary | null;
  hours: number;
  onChanged: () => void;
}) {
  const requestable = r.items.filter((i) => i.item !== NEVER_DISCLOSED);
  const identityAsked = r.items.some((i) => i.item === NEVER_DISCLOSED);

  const [selected, setSelected] = React.useState<string[]>(requestable.map((i) => i.item));
  const [note, setNote] = React.useState("");
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const isOpen = r.status === "REQUESTED";
  const isLive = r.status === "APPROVED" || r.status === "APPROVED_TIME_LIMITED";

  function toggle(item: string) {
    setSelected((prev) =>
      prev.includes(item) ? prev.filter((i) => i !== item) : [...prev, item],
    );
  }

  async function decide(
    kind: "all" | "selected" | "timed" | "deny",
  ): Promise<void> {
    setBusy(kind);
    setError(null);
    try {
      if (kind === "deny") {
        await endpoints.decideConsent(r.id, { approve: false, note: note.trim() });
      } else {
        await endpoints.decideConsent(r.id, {
          approve: true,
          items:
            kind === "all"
              ? requestable.map((i) => i.item)
              : selected.filter((i) => i !== NEVER_DISCLOSED),
          time_limited: kind === "timed",
          note: note.trim(),
        });
      }
      onChanged();
    } catch (err: any) {
      setError(err?.detail || err?.message || "The decision could not be recorded.");
    } finally {
      setBusy(null);
    }
  }

  async function revoke() {
    setBusy("revoke");
    setError(null);
    try {
      await endpoints.revokeConsent(r.id);
      onChanged();
    } catch (err: any) {
      setError(err?.detail || err?.message || "Access could not be revoked.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card className={cn("overflow-hidden", isOpen && "ring-1 ring-status-info/25")}>
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-canvas-border px-5 py-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <ConsentStatusBadge status={r.status} />
            {property ? (
              <Link
                href={`/buyer/${property.reference}`}
                className="font-mono text-[13px] font-semibold text-navy-700 hover:underline"
              >
                {property.reference}
              </Link>
            ) : (
              <span className="font-mono text-[13px] text-ink-subtle">{r.property_id}</span>
            )}
            {property ? (
              <span className="text-2xs text-ink-subtle">
                {property.village}, {property.district}
              </span>
            ) : null}
          </div>
          <p className="mt-2 text-[13px] text-ink">
            <UserCog className="mr-1.5 inline h-3.5 w-3.5 text-ink-subtle" />
            <span className="font-medium">{r.requester?.name ?? "Unknown requester"}</span>
            <span className="text-ink-subtle">
              {" "}
              · {titleise(r.requester?.role ?? "BUYER")} · asked {relative(r.created_at)}
            </span>
          </p>
          {r.purpose ? (
            <p className="mt-2 max-w-3xl rounded-xl bg-canvas-sunken/70 px-3.5 py-2.5 text-[13px] leading-relaxed text-ink">
              “{r.purpose}”
            </p>
          ) : null}
        </div>
        {r.status === "APPROVED_TIME_LIMITED" ? (
          <div className="flex flex-col items-end gap-1.5">
            <Countdown expiresAt={r.expires_at} />
            <span className="text-2xs text-ink-subtle">expires {dateTime(r.expires_at)}</span>
            <span className="text-2xs text-ink-subtle">No action is needed to end it.</span>
          </div>
        ) : null}
      </div>

      <div className="px-5 py-4">
        {isOpen ? (
          <>
            <div className="section-label mb-2">Items requested — decide each one</div>
            <ul className="grid gap-2 sm:grid-cols-2">
              {requestable.map((i) => (
                <li key={i.item}>
                  <label
                    className={cn(
                      "flex cursor-pointer items-center gap-3 rounded-xl border px-3.5 py-2.5 transition",
                      selected.includes(i.item)
                        ? "border-emerald-300 bg-emerald-50"
                        : "border-canvas-border hover:bg-canvas-sunken/60",
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={selected.includes(i.item)}
                      onChange={() => toggle(i.item)}
                      className="h-4 w-4 shrink-0 accent-emerald-600"
                    />
                    <span className="min-w-0">
                      <span className="block text-[13px] font-medium text-ink">{i.label}</span>
                      <span className="block font-mono text-2xs text-ink-subtle">{i.item}</span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>

            {/* Identity is stripped from an approval server-side. Showing it here keeps the
                owner from believing they granted something the platform will never release. */}
            {identityAsked ? (
              <div className="mt-3 flex items-start gap-3 rounded-xl border border-status-conflicting/25 bg-status-conflictingBg/50 px-3.5 py-3">
                <Ban className="mt-0.5 h-4 w-4 shrink-0 text-status-conflicting" />
                <div>
                  <p className="text-[13px] font-semibold text-status-conflicting">
                    Identity document — withheld automatically
                  </p>
                  <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
                    This item was part of the request but cannot be released, with or without your
                    consent. It is stripped from your approval before it takes effect; identity is
                    checked on the platform side and only the outcome is shared.
                  </p>
                </div>
              </div>
            ) : null}

            <div className="mt-4">
              <label className="section-label mb-1.5 block" htmlFor={`note-${r.id}`}>
                Note to the requester (optional)
              </label>
              <input
                id={`note-${r.id}`}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="e.g. Sharing the EC only; the survey record is being re-issued."
                className="w-full rounded-xl border border-canvas-borderStrong bg-canvas-raised px-3.5 py-2 text-[13.5px] text-ink placeholder:text-ink-subtle focus:border-navy-400"
              />
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Button onClick={() => decide("all")} disabled={busy !== null}>
                <CheckCheck className="h-4 w-4" />
                {busy === "all" ? "Approving…" : "Approve all"}
              </Button>
              <Button
                variant="secondary"
                onClick={() => decide("selected")}
                disabled={busy !== null || selected.length === 0}
              >
                <Unlock className="h-4 w-4" />
                {busy === "selected" ? "Approving…" : `Approve selected (${selected.length})`}
              </Button>
              <Button
                variant="secondary"
                onClick={() => decide("timed")}
                disabled={busy !== null || selected.length === 0}
              >
                <Timer className="h-4 w-4" />
                {busy === "timed" ? "Approving…" : `Approve for ${hours} hours`}
              </Button>
              <Button variant="danger" onClick={() => decide("deny")} disabled={busy !== null}>
                <X className="h-4 w-4" />
                {busy === "deny" ? "Denying…" : "Deny"}
              </Button>
            </div>
            <p className="mt-2 text-2xs leading-relaxed text-ink-subtle">
              A time-limited approval releases the same items and then withdraws them
              automatically after {hours} hours — you do not have to remember to close it.
            </p>
          </>
        ) : (
          <div className="space-y-2.5">
            <ItemLine label="Requested" items={r.items} tone="neutral" />
            {r.granted_items.length ? (
              <ItemLine label="Granted" items={r.granted_items} tone="emerald" />
            ) : null}
            {r.denied_items.length ? (
              <ItemLine label="Withheld" items={r.denied_items} tone="red" />
            ) : null}
            {r.decision_note ? (
              <p className="text-[13px] leading-relaxed text-ink-muted">
                Your note: {r.decision_note}
              </p>
            ) : null}
            <p className="text-2xs text-ink-subtle">
              <CalendarClock className="mr-1 inline h-3 w-3" />
              decided {dateTime(r.decided_at)}
            </p>
            {isLive ? (
              <Button
                variant="danger"
                size="sm"
                onClick={revoke}
                disabled={busy !== null}
              >
                <Lock className="h-3.5 w-3.5" />
                {busy === "revoke" ? "Revoking…" : "Revoke access"}
              </Button>
            ) : null}
          </div>
        )}

        {error ? (
          <p className="mt-3 rounded-xl bg-status-conflictingBg px-3.5 py-2.5 text-[13px] text-status-conflicting ring-1 ring-status-conflicting/20">
            {error}
          </p>
        ) : null}
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
      {items.length === 0 ? (
        <span className="text-[13px] text-ink-subtle">nothing</span>
      ) : (
        items.map((i) => (
          <Chip key={`${label}-${i.item}`} tone={tone}>
            {i.label}
          </Chip>
        ))
      )}
    </div>
  );
}
