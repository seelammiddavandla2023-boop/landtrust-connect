"use client";

import {
  Ban,
  CircleAlert,
  Info,
  ShieldAlert,
  ShieldCheck,
  TrendingDown,
} from "lucide-react";
import React from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useApi, useCapabilities } from "@/components/hooks";
import {
  BandBadge,
  Button,
  Card,
  CardHeader,
  Chip,
  Disclaimer,
  EmptyState,
  ErrorState,
  EvidenceChip,
  LoadingCard,
  RiskGauge,
  SeverityBadge,
  StateBadge,
  Tooltip,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import {
  CATEGORY_ORDER,
  STATE_META,
  type Severity,
  type TransactionState,
} from "@/lib/domain";
import { cn, dateTime, titleise } from "@/lib/format";

export function RiskTab({
  propertyId,
  contradictions,
  version,
}: {
  propertyId: string;
  contradictions: any;
  version: number;
}) {
  const { data: risk, error, loading, refetch } = useApi<any>(
    () => endpoints.risk(propertyId, true),
    [propertyId, version],
  );
  const [attempt, setAttempt] = React.useState<any>(null);
  const [busy, setBusy] = React.useState(false);
  const caps = useCapabilities();
  const mayAttempt = caps.can("ATTEMPT_TRANSACTION");

  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (loading || !risk) return <LoadingCard rows={10} title="Risk analysis" />;

  const drivers = (risk.factors ?? []).filter((f: any) => !f.is_mitigation);
  const mitigations = (risk.factors ?? []).filter((f: any) => f.is_mitigation);
  const state = risk.state as TransactionState;
  const blocked: string[] = risk.transaction?.blocked_actions ?? [];

  const radar = CATEGORY_ORDER.map((key) => ({
    category: (risk.category_labels?.[key] ?? titleise(key)).replace(" Risk", ""),
    score: risk.category_scores?.[key] ?? 0,
  }));

  const tryAction = async (action: string) => {
    setBusy(true);
    try {
      setAttempt(await endpoints.attempt(propertyId, action));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
        {/* -------------------------------------------------------- gauge */}
        <Card className="p-5">
          <div className="flex justify-center">
            <RiskGauge score={risk.overall_score} band={risk.band} size={220} />
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
            <StateBadge state={state} size="lg" />
            <BandBadge band={risk.band} />
          </div>
          <div className="mt-4 rounded-xl bg-canvas-sunken px-3.5 py-3">
            <p className="text-[13px] leading-relaxed text-ink-muted">{risk.state_reason}</p>
          </div>
          <dl className="mt-4 space-y-2 text-2xs">
            <div className="flex justify-between">
              <dt className="text-ink-subtle">Engine</dt>
              <dd className="font-mono text-ink-muted">{risk.engine_version}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-subtle">Rules triggered</dt>
              <dd className="tnum text-ink-muted">{drivers.length}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-subtle">Mitigations</dt>
              <dd className="tnum text-ink-muted">{mitigations.length}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-subtle">Assessed</dt>
              <dd className="text-ink-muted">{dateTime(risk.created_at)}</dd>
            </div>
          </dl>
        </Card>

        {/* ------------------------------------------------- categories */}
        <div className="space-y-4">
          <Card>
            <CardHeader
              title="Risk by category"
              subtitle="Categories saturate: the first serious problem moves a category a lot, the fifth moves it little. The overall score combines them as independent chances of the transaction being unsafe, so one critical category is never diluted by six benign ones."
            />
            <div className="grid gap-4 p-5 lg:grid-cols-[minmax(0,1fr)_260px]">
              <ul className="space-y-3">
                {CATEGORY_ORDER.map((key) => {
                  const value = risk.category_scores?.[key] ?? 0;
                  const inCategory = drivers.filter((f: any) => f.category === key);
                  return (
                    <li key={key}>
                      <div className="flex items-baseline justify-between">
                        <span className="text-[13px] font-medium text-ink">
                          {risk.category_labels?.[key] ?? titleise(key)}
                        </span>
                        <span className="tnum text-[13px] font-semibold text-ink">
                          {Math.round(value)}
                          <span className="ml-0.5 text-2xs font-normal text-ink-subtle">/100</span>
                        </span>
                      </div>
                      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-canvas-sunken">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all duration-700",
                            value >= 60
                              ? "bg-risk-critical"
                              : value >= 35
                                ? "bg-risk-high"
                                : value > 0
                                  ? "bg-risk-moderate"
                                  : "bg-canvas-borderStrong",
                          )}
                          style={{ width: `${Math.max(value, 1.5)}%` }}
                        />
                      </div>
                      {inCategory.length ? (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {inCategory.map((f: any) => (
                            <span
                              key={f.id}
                              className="rounded bg-canvas-sunken px-1.5 py-0.5 font-mono text-[10px] text-ink-subtle"
                            >
                              {f.rule_id} +{Math.round(f.weight)}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
              <ResponsiveContainer width="100%" height={250}>
                <RadarChart data={radar} outerRadius="76%">
                  <PolarGrid stroke="#dde5f0" />
                  <PolarAngleAxis dataKey="category" tick={{ fontSize: 10, fill: "#7f8ca5" }} />
                  <Radar dataKey="score" stroke="#0f1c38" fill="#48649d" fillOpacity={0.28} />
                  <RTooltip
                    contentStyle={{ fontSize: 12, borderRadius: 10, border: "1px solid #dde5f0" }}
                    formatter={(v: any) => [`${Math.round(v)}/100`, "Category score"]}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {risk.history?.length > 1 ? (
            <Card>
              <CardHeader
                title="Risk over time"
                subtitle="Every recomputation on this file. The score moves when the evidence moves."
                icon={<TrendingDown className="h-4 w-4" />}
              />
              <div className="p-5">
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart
                    data={risk.history.map((h: any, i: number) => ({
                      i: i + 1,
                      score: h.overall_score,
                      state: h.state,
                      at: dateTime(h.created_at),
                    }))}
                    margin={{ left: -18, right: 12, top: 8, bottom: 4 }}
                  >
                    <CartesianGrid stroke="#eef2f8" vertical={false} />
                    <XAxis dataKey="i" tick={{ fontSize: 11, fill: "#7f8ca5" }} axisLine={false} tickLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#7f8ca5" }} axisLine={false} tickLine={false} />
                    <RTooltip
                      contentStyle={{ fontSize: 12, borderRadius: 10, border: "1px solid #dde5f0" }}
                      formatter={(v: any, _n: any, p: any) => [`${v}/100 · ${p.payload.state}`, p.payload.at]}
                    />
                    <Line
                      type="monotone"
                      dataKey="score"
                      stroke="#0f1c38"
                      strokeWidth={2}
                      dot={{ r: 3, fill: "#0f1c38" }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>
          ) : null}
        </div>
      </div>

      {/* ----------------------------------------------- state controller */}
      <Card className={cn("border", state === "PROCEED" ? "" : "border-status-partial/30")}>
        <CardHeader
          title="Transaction state controller"
          subtitle="The state is enforced, not displayed. Blocked actions are refused by the API, and the refusal is recorded in the audit trail."
          icon={<Ban className="h-4 w-4" />}
        />
        <div className="p-5">
          <div className={cn("rounded-xl px-4 py-3", STATE_META[state].bg)}>
            <p className={cn("text-[13px] font-semibold", STATE_META[state].fg)}>
              {STATE_META[state].blurb}
            </p>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {["PROCEED_TO_AGREEMENT", "INITIATE_PAYMENT", "SITE_VISIT_BOOKING"].map((action) => {
              const isBlocked = blocked.includes(action);
              return (
                <Tooltip
                  key={action}
                  content={
                    !mayAttempt
                      ? caps.why("ATTEMPT_TRANSACTION")
                      : isBlocked
                        ? "Blocked in the current state. Click anyway — the refusal is the demonstration."
                        : "Permitted in the current state. No payment is processed by this prototype."
                  }
                >
                  <Button
                    variant={isBlocked ? "subtle" : "secondary"}
                    size="sm"
                    disabled={busy || !mayAttempt}
                    onClick={() => tryAction(action)}
                    className={cn(isBlocked && "line-through decoration-status-conflicting/60")}
                  >
                    {isBlocked ? <Ban className="h-3.5 w-3.5 text-status-conflicting" /> : null}
                    {titleise(action)}
                  </Button>
                </Tooltip>
              );
            })}
          </div>

          {attempt ? (
            <div
              className={cn(
                "mt-3 rounded-xl border px-4 py-3",
                attempt.allowed
                  ? "border-status-verified/25 bg-status-verifiedBg"
                  : "border-status-conflicting/25 bg-status-conflictingBg",
              )}
            >
              <div className="flex items-start gap-2">
                {attempt.allowed ? (
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-status-verified" />
                ) : (
                  <Ban className="mt-0.5 h-4 w-4 shrink-0 text-status-conflicting" />
                )}
                <div>
                  <div className="text-[13px] font-semibold text-ink">
                    {titleise(attempt.action)} — {attempt.allowed ? "permitted" : "refused"}
                  </div>
                  <p className="mt-1 text-2xs leading-relaxed text-ink-muted">{attempt.reason}</p>
                  <p className="mt-1 text-2xs text-ink-subtle">{attempt.note}</p>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </Card>

      {/* ------------------------------------------------------- factors */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            title={`Contributing factors · ${drivers.length}`}
            subtitle="Every rule that fired, with its weight and the evidence it fired on"
            icon={<ShieldAlert className="h-4 w-4" />}
          />
          {drivers.length === 0 ? (
            <div className="p-5">
              <EmptyState title="No risk factors triggered" />
            </div>
          ) : (
            <ul className="divide-y divide-canvas-border">
              {drivers.map((f: any) => (
                <li key={f.id} className="px-5 py-3.5">
                  <div className="flex items-start gap-3">
                    <span className="tnum mt-0.5 shrink-0 rounded-lg bg-status-conflictingBg px-2 py-1 text-2xs font-bold text-status-conflicting">
                      +{Math.round(f.weight)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[13px] font-medium text-ink">{f.title}</span>
                        <SeverityBadge severity={f.severity as Severity} />
                        <Chip tone="neutral">{f.category_label}</Chip>
                      </div>
                      <p className="mt-1 text-2xs leading-relaxed text-ink-muted">{f.explanation}</p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        <span className="font-mono text-[10px] text-ink-subtle">{f.rule_id}</span>
                        {(f.evidence_refs ?? []).slice(0, 3).map((r: any, i: number) => (
                          <EvidenceChip key={i} document={r.label ?? r.id} page={r.page} />
                        ))}
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader
              title={`Mitigating factors · ${mitigations.length}`}
              subtitle="Evidence that reduces the score"
              icon={<ShieldCheck className="h-4 w-4" />}
            />
            {mitigations.length === 0 ? (
              <div className="p-5">
                <EmptyState title="No mitigations" description="Nothing on file reduces the score." />
              </div>
            ) : (
              <ul className="divide-y divide-canvas-border">
                {mitigations.map((f: any) => (
                  <li key={f.id} className="flex items-start gap-3 px-5 py-3.5">
                    <span className="tnum mt-0.5 shrink-0 rounded-lg bg-status-verifiedBg px-2 py-1 text-2xs font-bold text-status-verified">
                      {Math.round(f.weight)}
                    </span>
                    <div className="min-w-0">
                      <div className="text-[13px] font-medium text-ink">{f.title}</div>
                      <p className="mt-1 text-2xs leading-relaxed text-ink-muted">{f.explanation}</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <CardHeader
              title={`Contradictions · ${contradictions?.count ?? 0}`}
              subtitle="What the cross-document comparison found"
              icon={<CircleAlert className="h-4 w-4" />}
            />
            {!contradictions?.items?.length ? (
              <div className="p-5">
                <EmptyState title="No unresolved contradictions" />
              </div>
            ) : (
              <ul className="divide-y divide-canvas-border">
                {contradictions.items.map((c: any) => (
                  <li key={c.id} className="px-5 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <SeverityBadge severity={c.severity as Severity} />
                      <span className="text-[13px] font-medium text-ink">
                        {titleise(c.contradiction_type)}
                      </span>
                      {c.difference ? (
                        <span className="tnum rounded bg-status-conflictingBg px-1.5 py-0.5 text-2xs text-status-conflicting">
                          {c.difference}
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1.5 text-2xs leading-relaxed text-ink-muted">{c.explanation}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      <Disclaimer text="Risk scores describe the strength and consistency of the evidence supplied to this platform. They are not a legal opinion on title, and a low score is not a warranty." />
    </div>
  );
}
