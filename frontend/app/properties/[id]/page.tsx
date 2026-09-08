"use client";

import {
  FileStack,
  GitBranch,
  History,
  LayoutGrid,
  ListChecks,
  ShieldAlert,
  Sparkles,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import React from "react";

import { useApi, useQueryParam } from "@/components/hooks";
import {
  BandBadge,
  Button,
  Card,
  Disclaimer,
  ErrorState,
  KeyValue,
  LoadingCard,
  PrototypeBadge,
  Skeleton,
  StateBadge,
  Tabs,
} from "@/components/ui";
import { AuditTab } from "@/components/workspace/audit-tab";
import { ClaimsTab } from "@/components/workspace/claims-tab";
import { DocumentsTab } from "@/components/workspace/documents-tab";
import { GraphTab } from "@/components/workspace/graph-tab";
import { OverviewTab } from "@/components/workspace/overview-tab";
import { ResolutionTab } from "@/components/workspace/resolution-tab";
import { RiskTab } from "@/components/workspace/risk-tab";
import { endpoints } from "@/lib/api";
import { STATE_META, type TransactionState } from "@/lib/domain";
import { cn, dateTime, inr, pct, sqft } from "@/lib/format";

const TABS = [
  { key: "overview", label: "Overview", icon: <LayoutGrid className="h-4 w-4" /> },
  { key: "documents", label: "Evidence", icon: <FileStack className="h-4 w-4" /> },
  { key: "claims", label: "Claims", icon: <ListChecks className="h-4 w-4" /> },
  { key: "graph", label: "Ownership Graph", icon: <GitBranch className="h-4 w-4" /> },
  { key: "risk", label: "Risk Analysis", icon: <ShieldAlert className="h-4 w-4" /> },
  { key: "resolution", label: "Resolution Plan", icon: <Wrench className="h-4 w-4" /> },
  { key: "audit", label: "Audit Trail", icon: <History className="h-4 w-4" /> },
];

export default function PropertyWorkspace({ params }: { params: { id: string } }) {
  const id = params.id;
  const [tab, setTab] = useQueryParam("tab", "overview");
  const [version, setVersion] = React.useState(0);

  const { data: property, error, loading, refetch } = useApi<any>(
    () => endpoints.property(id),
    [id, version],
  );
  const { data: claims } = useApi<any>(() => endpoints.claims(id), [id, version]);
  const { data: documents } = useApi<any>(() => endpoints.documents(id), [id, version]);
  const { data: contradictions } = useApi<any>(() => endpoints.contradictions(id), [id, version]);

  // Anything that changes the evidence set (an applied resolution step, an upload)
  // must invalidate every tab at once — a stale risk figure beside a fresh claim table
  // would undermine the whole argument this screen is making.
  const invalidate = React.useCallback(() => setVersion((v) => v + 1), []);

  if (error) return <ErrorState error={error} onRetry={refetch} />;

  if (loading || !property) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-32" />
        <Skeleton className="h-10 w-full max-w-2xl" />
        <LoadingCard rows={8} />
      </div>
    );
  }

  const counts = {
    documents: documents?.count ?? property.document_count,
    claims: claims?.matrix?.length ?? property.claim_count,
    contradictions: contradictions?.count ?? property.contradiction_count,
  };

  const tabsWithCounts = TABS.map((t) => ({
    ...t,
    count:
      t.key === "documents"
        ? counts.documents
        : t.key === "claims"
          ? counts.claims
          : t.key === "risk"
            ? counts.contradictions || undefined
            : undefined,
  }));

  return (
    <div className="space-y-5">
      <WorkspaceHeader property={property} onReassess={invalidate} />

      <Tabs tabs={tabsWithCounts} active={tab} onChange={setTab} />

      <div className="animate-fade-in">
        {tab === "overview" ? (
          <OverviewTab
            property={property}
            claims={claims}
            documents={documents}
            contradictions={contradictions}
            onNavigate={setTab}
          />
        ) : null}
        {tab === "documents" ? <DocumentsTab propertyId={id} documents={documents} /> : null}
        {tab === "claims" ? <ClaimsTab propertyId={id} claims={claims} /> : null}
        {tab === "graph" ? <GraphTab propertyId={id} /> : null}
        {tab === "risk" ? (
          <RiskTab propertyId={id} contradictions={contradictions} version={version} />
        ) : null}
        {tab === "resolution" ? (
          <ResolutionTab propertyId={id} version={version} onApplied={invalidate} />
        ) : null}
        {tab === "audit" ? <AuditTab propertyId={id} version={version} /> : null}
      </div>

      <Disclaimer />
    </div>
  );
}

/* ----------------------------------------------------------------- header */

function WorkspaceHeader({
  property: p,
  onReassess,
}: {
  property: any;
  onReassess: () => void;
}) {
  const [busy, setBusy] = React.useState(false);
  const state = p.transaction_state as TransactionState;

  const reassess = async () => {
    setBusy(true);
    try {
      await endpoints.reassess(p.reference);
      onReassess();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="overflow-hidden">
      <div
        className={cn(
          "h-1 w-full",
          {
            PROCEED: "bg-risk-low",
            WARN: "bg-risk-moderate",
            HOLD: "bg-risk-high",
            ESCALATE: "bg-risk-critical",
            REJECT: "bg-risk-critical",
          }[state] ?? "bg-canvas-borderStrong",
        )}
      />
      <div className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-2xs text-ink-subtle">{p.reference}</span>
              <PrototypeBadge />
            </div>
            <h1 className="mt-1.5 text-2xl font-semibold tracking-tight text-ink">
              Survey {p.survey_number}
              <span className="ml-2 text-base font-normal text-ink-muted">
                {p.village}, {p.district}
              </span>
            </h1>
            <p className="mt-1 text-[13px] text-ink-muted">{p.scenario_label}</p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {state ? <StateBadge state={state} size="lg" /> : null}
            {p.risk_band ? <BandBadge band={p.risk_band} /> : null}
            <Button variant="secondary" size="sm" onClick={reassess} disabled={busy}>
              <Sparkles className={cn("h-3.5 w-3.5", busy && "animate-pulse")} />
              {busy ? "Re-running…" : "Re-run assessment"}
            </Button>
            <Link href={`/buyer/${p.reference}`}>
              <Button variant="secondary" size="sm">
                See the buyer&apos;s view
              </Button>
            </Link>
          </div>
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-canvas-border pt-5 sm:grid-cols-3 lg:grid-cols-6">
          <KeyValue label="Survey number" value={p.survey_number} mono />
          <KeyValue label="Property type" value={p.property_type} />
          <KeyValue label="Recorded area" value={sqft(p.claimed_area_sqft)} />
          <KeyValue
            label="Claimed owner"
            value={
              <span>
                {p.listed_owner_name}
                <span className="ml-1.5 text-2xs text-ink-subtle">(as listed)</span>
              </span>
            }
          />
          <KeyValue
            label="Verification level"
            value={
              <span className="flex items-center gap-2">
                <span className="tnum">{pct(p.verification_level)}</span>
                <span className="h-1.5 w-12 overflow-hidden rounded-full bg-canvas-sunken">
                  <span
                    className="block h-full rounded-full bg-status-verified"
                    style={{ width: `${(p.verification_level || 0) * 100}%` }}
                  />
                </span>
              </span>
            }
          />
          <KeyValue
            label="Risk score"
            value={
              <span className="tnum">
                {p.risk_score !== null ? `${Math.round(p.risk_score)} / 100` : "—"}
              </span>
            }
          />
          <KeyValue label="Asking price" value={inr(p.asking_price_inr, { compact: true })} />
          <KeyValue
            label="Guideline value"
            value={inr(p.guideline_value_inr, { compact: true })}
          />
          <KeyValue label="Transaction" value={p.transaction?.reference ?? "—"} mono />
          <KeyValue label="Last updated" value={dateTime(p.updated_at)} />
        </dl>

        {state && state !== "PROCEED" ? (
          <div
            className={cn(
              "mt-5 rounded-xl px-4 py-3",
              STATE_META[state].bg,
            )}
          >
            <div className={cn("text-[13px] font-semibold", STATE_META[state].fg)}>
              {STATE_META[state].blurb}
            </div>
            {p.transaction?.state_reason ? (
              <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted">
                {p.transaction.state_reason}
              </p>
            ) : null}
            {p.transaction?.blocked_actions?.length ? (
              <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                <span className="text-2xs font-medium text-ink-subtle">Blocked:</span>
                {p.transaction.blocked_actions.map((a: string) => (
                  <span
                    key={a}
                    className="rounded bg-white/70 px-1.5 py-0.5 font-mono text-2xs text-ink-muted"
                  >
                    {a}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </Card>
  );
}
