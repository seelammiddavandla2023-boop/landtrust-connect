"use client";

import {
  AlertTriangle,
  Building2,
  FileCheck2,
  FileStack,
  GitCompareArrows,
  Inbox,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import React from "react";
import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useApi } from "@/components/hooks";
import {
  BandBadge,
  Card,
  CardHeader,
  Disclaimer,
  EmptyState,
  ErrorState,
  LoadingCard,
  SectionHeading,
  Skeleton,
  StateBadge,
  StatTile,
  StatusBadge,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import {
  BAND_META,
  STATE_META,
  VERIFICATION_META,
  type RiskBand,
  type TransactionState,
  type VerificationStatus,
} from "@/lib/domain";
import { cn, dateTime, pct, relative, titleise } from "@/lib/format";

const CHART_AXIS = { fontSize: 11, fill: "#7f8ca5" };

export default function DashboardPage() {
  const { data, error, loading, refetch } = useApi<any>(() => endpoints.dashboard(), []);

  if (error) return <ErrorState error={error} onRetry={refetch} />;

  if (loading || !data) {
    return (
      <div className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-[92px]" />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <LoadingCard rows={6} />
          <LoadingCard rows={6} />
          <LoadingCard rows={6} />
        </div>
      </div>
    );
  }

  const c = data.cards;

  return (
    <div className="space-y-7">
      <SectionHeading
        eyebrow="Workspace"
        title="Verification dashboard"
        description="Every figure below is derived from the evidence currently on file. Uploading a document or granting consent changes these numbers because it changes what the platform can establish."
        action={
          <Link
            href="/properties"
            className="inline-flex items-center gap-2 rounded-lg bg-navy-900 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-navy-800"
          >
            <Building2 className="h-4 w-4" />
            All properties
          </Link>
        }
      />

      {/* ------------------------------------------------------------ cards */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Properties under review"
          value={c.properties_under_review}
          hint={`of ${c.total_properties} total files`}
          icon={<Building2 className="h-4 w-4" />}
        />
        <StatTile
          label="Verified properties"
          value={c.verified_properties}
          tone="verified"
          hint="Clear to proceed on the evidence supplied"
          icon={<ShieldCheck className="h-4 w-4" />}
        />
        <StatTile
          label="Documents processed"
          value={c.documents_processed}
          hint="Classified, read and linked"
          icon={<FileStack className="h-4 w-4" />}
        />
        <StatTile
          label="Claims extracted"
          value={c.claims_extracted}
          hint="Each bound to a document and page"
          icon={<FileCheck2 className="h-4 w-4" />}
        />
        <StatTile
          label="Contradictions found"
          value={c.contradictions_found}
          tone={c.contradictions_found > 0 ? "warn" : "neutral"}
          hint="Unresolved disagreements across sources"
          icon={<GitCompareArrows className="h-4 w-4" />}
        />
        <StatTile
          label="High-risk transactions"
          value={c.high_risk_transactions}
          tone={c.high_risk_transactions > 0 ? "danger" : "neutral"}
          hint="HIGH or CRITICAL band"
          icon={<ShieldAlert className="h-4 w-4" />}
        />
        <StatTile
          label="Pending owner requests"
          value={c.pending_owner_requests}
          tone={c.pending_owner_requests > 0 ? "warn" : "neutral"}
          hint="Access requests awaiting a decision"
          icon={<Inbox className="h-4 w-4" />}
        />
        <StatTile
          label="Total properties"
          value={c.total_properties}
          hint="Synthetic evaluation corpus"
          icon={<Building2 className="h-4 w-4" />}
        />
      </div>

      {/* ----------------------------------------------------------- charts */}
      <div className="grid gap-4 lg:grid-cols-3">
        <RiskDistribution data={data.charts.risk_distribution} />
        <VerificationDistribution data={data.charts.verification_status} />
        <StateDistribution data={data.charts.transaction_states} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <RiskByProperty data={data.charts.risk_by_property} />
        <ContradictionMix
          types={data.charts.contradiction_types}
          severity={data.charts.contradiction_severity}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <RecentProperties items={data.recent_properties} />
        <div className="space-y-4">
          <DocumentMix data={data.charts.document_types} />
          <ProcessingPerformance data={data.charts.processing_performance} />
        </div>
      </div>

      <RecentActivity items={data.recent_activity} />

      <Disclaimer text={data.disclaimer} />
    </div>
  );
}

/* ----------------------------------------------------------------- charts */

function RiskDistribution({ data }: { data: { band: RiskBand; count: number }[] }) {
  const rows = data.filter((d) => d.count > 0);
  return (
    <Card>
      <CardHeader
        title="Risk distribution"
        subtitle="Properties by composite risk band"
        icon={<ShieldAlert className="h-4 w-4" />}
      />
      <div className="p-5">
        {rows.length === 0 ? (
          <EmptyState title="No assessments yet" />
        ) : (
          <>
            <ResponsiveContainer width="100%" height={168}>
              <PieChart>
                <Pie
                  data={rows}
                  dataKey="count"
                  nameKey="band"
                  innerRadius={44}
                  outerRadius={70}
                  paddingAngle={2}
                  stroke="none"
                >
                  {rows.map((r) => (
                    <Cell key={r.band} fill={BAND_META[r.band]?.hex ?? "#7f8ca5"} />
                  ))}
                </Pie>
                <RTooltip
                  formatter={(v: any, n: any) => [`${v} propert${v === 1 ? "y" : "ies"}`, titleise(n)]}
                  contentStyle={{ fontSize: 12, borderRadius: 10, border: "1px solid #dde5f0" }}
                />
              </PieChart>
            </ResponsiveContainer>
            <ul className="mt-3 space-y-1.5">
              {rows.map((r) => (
                <li key={r.band} className="flex items-center justify-between text-[13px]">
                  <span className="flex items-center gap-2 text-ink-muted">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: BAND_META[r.band]?.hex }}
                    />
                    {BAND_META[r.band]?.label ?? r.band}
                  </span>
                  <span className="tnum font-medium text-ink">{r.count}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </Card>
  );
}

function VerificationDistribution({
  data,
}: {
  data: { status: VerificationStatus; count: number }[];
}) {
  const rows = data.filter((d) => d.count > 0);
  const total = rows.reduce((s, r) => s + r.count, 0) || 1;
  return (
    <Card>
      <CardHeader
        title="Verification status"
        subtitle="Every live claim across all properties"
        icon={<ShieldCheck className="h-4 w-4" />}
      />
      <div className="p-5">
        {/* A single stacked bar reads faster than a pie when the point is proportion. */}
        <div className="flex h-3 overflow-hidden rounded-full">
          {rows.map((r) => (
            <div
              key={r.status}
              className={cn(VERIFICATION_META[r.status]?.bg)}
              style={{ width: `${(r.count / total) * 100}%` }}
              title={`${VERIFICATION_META[r.status]?.label}: ${r.count}`}
            >
              <div
                className="h-full w-full opacity-90"
                style={{
                  background: "currentColor",
                  color: "transparent",
                }}
              />
            </div>
          ))}
        </div>
        <ul className="mt-4 space-y-2">
          {rows.map((r) => {
            const meta = VERIFICATION_META[r.status];
            return (
              <li key={r.status} className="flex items-center justify-between gap-3">
                <StatusBadge status={r.status} size="sm" />
                <div className="flex items-center gap-3">
                  <span className="tnum text-2xs text-ink-subtle">
                    {pct(r.count / total, 0)}
                  </span>
                  <span className="tnum w-8 text-right text-[13px] font-medium text-ink">
                    {r.count}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </Card>
  );
}

function StateDistribution({
  data,
}: {
  data: { state: TransactionState; count: number }[];
}) {
  const rows = data.filter((d) => d.count > 0);
  return (
    <Card>
      <CardHeader
        title="Transaction states"
        subtitle="What the state controller currently permits"
        icon={<AlertTriangle className="h-4 w-4" />}
      />
      <div className="space-y-2.5 p-5">
        {rows.length === 0 ? (
          <EmptyState title="No transactions" />
        ) : (
          rows.map((r) => (
            <div key={r.state} className="rounded-xl border border-canvas-border p-3">
              <div className="flex items-center justify-between">
                <StateBadge state={r.state} size="sm" />
                <span className="tnum text-lg font-semibold text-ink">{r.count}</span>
              </div>
              <p className="mt-1.5 text-2xs leading-relaxed text-ink-muted">
                {STATE_META[r.state]?.blurb}
              </p>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

function RiskByProperty({ data }: { data: any[] }) {
  const rows = [...data].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  return (
    <Card>
      <CardHeader
        title="Composite risk by property"
        subtitle="Score out of 100. Thresholds: under 25 proceed · 25–49 warn · 50–74 hold · 75+ escalate."
      />
      <div className="p-5">
        <ResponsiveContainer width="100%" height={Math.max(200, rows.length * 42)}>
          <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 32, top: 4, bottom: 4 }}>
            <XAxis type="number" domain={[0, 100]} tick={CHART_AXIS} axisLine={false} tickLine={false} />
            <YAxis
              type="category"
              dataKey="reference"
              tick={CHART_AXIS}
              width={104}
              axisLine={false}
              tickLine={false}
            />
            <RTooltip
              cursor={{ fill: "#eef2f8" }}
              contentStyle={{ fontSize: 12, borderRadius: 10, border: "1px solid #dde5f0" }}
              formatter={(v: any, _n: any, p: any) => [
                `${v}/100 · ${p.payload.band} · ${p.payload.state}`,
                p.payload.label,
              ]}
            />
            <Bar dataKey="score" radius={[0, 6, 6, 0]} barSize={18}>
              {rows.map((r, i) => (
                <Cell key={i} fill={BAND_META[r.band as RiskBand]?.hex ?? "#7f8ca5"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div className="mt-3 flex flex-wrap gap-2">
          {rows.map((r) => (
            <Link
              key={r.reference}
              href={`/properties/${r.reference}`}
              className="inline-flex items-center gap-2 rounded-full bg-canvas-sunken px-2.5 py-1 text-2xs font-medium text-ink-muted transition hover:bg-canvas-border"
            >
              {r.reference}
              <StateBadge state={r.state as TransactionState} size="sm" />
            </Link>
          ))}
        </div>
      </div>
    </Card>
  );
}

function ContradictionMix({ types, severity }: { types: any[]; severity: any[] }) {
  const sev = severity.filter((s) => s.count > 0);
  const sevColour: Record<string, string> = {
    CRITICAL: "#c62828",
    HIGH: "#d2691e",
    MEDIUM: "#b7791f",
    LOW: "#5c6b85",
    INFO: "#1f6fb2",
  };
  return (
    <Card>
      <CardHeader
        title="Contradictions detected"
        subtitle="By type and severity, across every open file"
        icon={<GitCompareArrows className="h-4 w-4" />}
      />
      <div className="p-5">
        {types.length === 0 ? (
          <EmptyState
            title="No contradictions"
            description="Every claim on every file agrees with its corroborating documents."
          />
        ) : (
          <>
            <ul className="space-y-2">
              {types.map((t) => (
                <li key={t.type}>
                  <div className="flex items-center justify-between text-[13px]">
                    <span className="text-ink-muted">{titleise(t.type)}</span>
                    <span className="tnum font-medium text-ink">{t.count}</span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-canvas-sunken">
                    <div
                      className="h-full rounded-full bg-navy-500"
                      style={{
                        width: `${(t.count / Math.max(...types.map((x) => x.count))) * 100}%`,
                      }}
                    />
                  </div>
                </li>
              ))}
            </ul>
            <div className="mt-5 border-t border-canvas-border pt-4">
              <div className="section-label mb-2.5">By severity</div>
              <div className="flex flex-wrap gap-2">
                {sev.map((s) => (
                  <span
                    key={s.severity}
                    className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-2xs font-semibold"
                    style={{
                      color: sevColour[s.severity],
                      background: `${sevColour[s.severity]}14`,
                    }}
                  >
                    <span
                      className="h-1.5 w-1.5 rounded-full"
                      style={{ background: sevColour[s.severity] }}
                    />
                    {titleise(s.severity)} · {s.count}
                  </span>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}

function DocumentMix({ data }: { data: any[] }) {
  const max = Math.max(...data.map((d) => d.count), 1);
  return (
    <Card>
      <CardHeader title="Documents by type" subtitle="As classified by the pipeline" />
      <ul className="space-y-2 p-5">
        {data.map((d) => (
          <li key={d.doc_type}>
            <div className="flex items-center justify-between text-[13px]">
              <span className="text-ink-muted">{titleise(d.doc_type)}</span>
              <span className="tnum font-medium text-ink">{d.count}</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-canvas-sunken">
              <div
                className="h-full rounded-full bg-emerald-500"
                style={{ width: `${(d.count / max) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function ProcessingPerformance({ data }: { data: any[] }) {
  return (
    <Card>
      <CardHeader
        title="Processing time"
        subtitle="Milliseconds per document, measured during ingestion"
      />
      <div className="p-5">
        <ResponsiveContainer width="100%" height={150}>
          <BarChart data={data} margin={{ left: -18, right: 8, top: 4, bottom: 4 }}>
            <XAxis dataKey="filename" tick={false} axisLine={false} tickLine={false} />
            <YAxis tick={CHART_AXIS} axisLine={false} tickLine={false} />
            <RTooltip
              cursor={{ fill: "#eef2f8" }}
              contentStyle={{ fontSize: 12, borderRadius: 10, border: "1px solid #dde5f0" }}
              formatter={(v: any, _n: any, p: any) => [
                `${v} ms · ${p.payload.pages} page(s)`,
                p.payload.filename,
              ]}
            />
            <Bar dataKey="ms" fill="#48649d" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        <p className="mt-2 text-2xs leading-relaxed text-ink-subtle">
          Text-layer extraction. The OCR path is roughly two orders of magnitude slower — see the
          comparison on the research results page.
        </p>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ lists */

function RecentProperties({ items }: { items: any[] }) {
  return (
    <Card>
      <CardHeader
        title="Properties"
        subtitle="Verification level is measured over the six core claims"
        action={
          <Link href="/properties" className="text-[13px] font-medium text-navy-700 hover:underline">
            View all
          </Link>
        }
      />
      <div className="scroll-x">
        <table className="table-grid">
          <thead>
            <tr>
              <th>Property</th>
              <th>Verification</th>
              <th>Evidence</th>
              <th>Risk</th>
              <th>State</th>
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id} className="clickable">
                <td>
                  <Link href={`/properties/${p.reference}`} className="block">
                    <div className="font-medium text-ink">{p.reference}</div>
                    <div className="mt-0.5 text-2xs text-ink-muted">
                      {p.scenario_label} · Survey {p.survey_number} · {p.village}
                    </div>
                  </Link>
                </td>
                <td>
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-16 overflow-hidden rounded-full bg-canvas-sunken">
                      <div
                        className="h-full rounded-full bg-status-verified"
                        style={{ width: `${(p.verification_level || 0) * 100}%` }}
                      />
                    </div>
                    <span className="tnum text-2xs text-ink-muted">
                      {pct(p.verification_level)}
                    </span>
                  </div>
                </td>
                <td className="text-2xs text-ink-muted">
                  <div>{p.document_count} documents · {p.claim_count} claims</div>
                  {p.contradiction_count > 0 ? (
                    <div className="mt-0.5 font-medium text-status-conflicting">
                      {p.contradiction_count} contradiction
                      {p.contradiction_count === 1 ? "" : "s"}
                    </div>
                  ) : (
                    <div className="mt-0.5 text-status-verified">No contradictions</div>
                  )}
                </td>
                <td>
                  {p.risk_score !== null ? (
                    <div className="flex items-center gap-2">
                      <span className="tnum text-sm font-semibold text-ink">
                        {Math.round(p.risk_score)}
                      </span>
                      <BandBadge band={p.risk_band} />
                    </div>
                  ) : (
                    "—"
                  )}
                </td>
                <td>
                  {p.transaction_state ? <StateBadge state={p.transaction_state} size="sm" /> : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function RecentActivity({ items }: { items: any[] }) {
  return (
    <Card>
      <CardHeader
        title="Recent verification activity"
        subtitle="Every consequential action is written to an append-only ledger"
        action={
          <Link href="/properties" className="text-[13px] font-medium text-navy-700 hover:underline">
            Full audit trails
          </Link>
        }
      />
      <ul className="divide-y divide-canvas-border">
        {items.map((e) => (
          <li key={e.id} className="flex items-start gap-3 px-5 py-3">
            <span
              className={cn(
                "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                e.result === "OK"
                  ? "bg-status-verified"
                  : ["HIGH", "CRITICAL", "BLOCKED"].includes(e.result)
                    ? "bg-status-conflicting"
                    : "bg-status-partial",
              )}
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-[13px] font-medium text-ink">{titleise(e.action)}</span>
                <span className="text-2xs text-ink-subtle">
                  {e.actor_name} · {e.actor_role.toLowerCase()}
                </span>
              </div>
              <p className="mt-0.5 text-2xs leading-relaxed text-ink-muted">{e.summary}</p>
            </div>
            <time
              className="shrink-0 text-2xs text-ink-subtle"
              title={dateTime(e.created_at)}
              dateTime={e.created_at}
            >
              {relative(e.created_at)}
            </time>
          </li>
        ))}
      </ul>
    </Card>
  );
}
