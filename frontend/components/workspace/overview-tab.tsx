"use client";

import {
  AlertTriangle,
  ArrowRight,
  CircleAlert,
  FileStack,
  Layers,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import React from "react";

import { useApi } from "@/components/hooks";
import {
  BandBadge,
  Button,
  Card,
  CardHeader,
  Chip,
  EmptyState,
  LoadingCard,
  RiskGauge,
  SeverityBadge,
  StateBadge,
  StatusBadge,
  StatTile,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import {
  CATEGORY_ORDER,
  STATE_META,
  VERIFICATION_META,
  type Severity,
  type TransactionState,
  type VerificationStatus,
} from "@/lib/domain";
import { cn, pct, titleise, truncate } from "@/lib/format";

export function OverviewTab({
  property,
  claims,
  documents,
  contradictions,
  onNavigate,
}: {
  property: any;
  claims: any;
  documents: any;
  contradictions: any;
  onNavigate: (tab: string) => void;
}) {
  const { data: risk } = useApi<any>(() => endpoints.risk(property.reference), [property.id]);
  const { data: plan } = useApi<any>(() => endpoints.resolution(property.reference), [property.id]);

  const coreRows: any[] = (claims?.matrix ?? []).filter((r: any) => r.is_core);
  const openContradictions: any[] = contradictions?.items ?? [];
  const topFactors = (risk?.factors ?? [])
    .filter((f: any) => !f.is_mitigation && f.weight > 0)
    .slice(0, 4);
  const mitigations = (risk?.factors ?? []).filter((f: any) => f.is_mitigation);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        {/* --------------------------------------------------- left column */}
        <div className="space-y-4">
          <Card>
            <CardHeader
              title="Core claims"
              subtitle="The six details a complete land file must establish. A status here is a statement about evidence, not about legality."
              icon={<Layers className="h-4 w-4" />}
              action={
                <Button variant="ghost" size="sm" onClick={() => onNavigate("claims")}>
                  Full matrix <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              }
            />
            {coreRows.length === 0 ? (
              <div className="p-5">
                <LoadingCard rows={4} />
              </div>
            ) : (
              <ul className="divide-y divide-canvas-border">
                {coreRows.map((row) => (
                  <li key={row.claim_type} className="px-5 py-3.5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-2xs font-medium uppercase tracking-wide text-ink-subtle">
                          {row.label}
                        </div>
                        <div
                          className={cn(
                            "mt-0.5 text-sm",
                            row.id ? "font-medium text-ink" : "italic text-ink-subtle",
                          )}
                        >
                          {row.value}
                        </div>
                      </div>
                      <StatusBadge status={row.verification_status} size="sm" />
                    </div>
                    <p className="mt-1.5 text-2xs leading-relaxed text-ink-muted">
                      {truncate(row.explanation, 210)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <CardHeader
              title={`Open contradictions${openContradictions.length ? ` · ${openContradictions.length}` : ""}`}
              subtitle="Disagreements between documents that have not been resolved"
              icon={<CircleAlert className="h-4 w-4" />}
              action={
                openContradictions.length ? (
                  <Button variant="ghost" size="sm" onClick={() => onNavigate("risk")}>
                    Risk analysis <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                ) : null
              }
            />
            {openContradictions.length === 0 ? (
              <div className="p-5">
                <EmptyState
                  title="No unresolved contradictions"
                  description="Every claim on this file agrees with its corroborating documents, and no required document is missing."
                  icon={<ShieldCheck className="h-5 w-5 text-status-verified" />}
                />
              </div>
            ) : (
              <ul className="divide-y divide-canvas-border">
                {openContradictions.slice(0, 5).map((c: any) => (
                  <li key={c.id} className="px-5 py-3.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <SeverityBadge severity={c.severity as Severity} />
                      <span className="text-[13px] font-medium text-ink">
                        {titleise(c.contradiction_type)}
                      </span>
                      <span className="text-2xs text-ink-subtle">· {c.claim_label}</span>
                      {c.difference ? (
                        <span className="tnum rounded bg-status-conflictingBg px-1.5 py-0.5 text-2xs font-medium text-status-conflicting">
                          {c.difference}
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1.5 text-2xs leading-relaxed text-ink-muted">
                      {truncate(c.explanation, 260)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        {/* -------------------------------------------------- right column */}
        <div className="space-y-4">
          <Card className="p-5">
            <div className="section-label mb-3">Transaction risk</div>
            {risk ? (
              <>
                <div className="flex justify-center">
                  <RiskGauge score={risk.overall_score} band={risk.band} size={190} />
                </div>
                <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
                  <StateBadge state={risk.state as TransactionState} />
                  <BandBadge band={risk.band} />
                </div>
                <p className="mt-3 text-2xs leading-relaxed text-ink-muted">
                  {risk.state_reason}
                </p>
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-3 w-full"
                  onClick={() => onNavigate("risk")}
                >
                  Every point, explained
                </Button>
              </>
            ) : (
              <LoadingCard rows={4} />
            )}
          </Card>

          {risk ? (
            <Card>
              <CardHeader title="Category breakdown" />
              <ul className="space-y-2.5 p-5">
                {CATEGORY_ORDER.map((key) => {
                  const value = risk.category_scores?.[key] ?? 0;
                  return (
                    <li key={key}>
                      <div className="flex items-center justify-between text-2xs">
                        <span className="text-ink-muted">
                          {risk.category_labels?.[key] ?? titleise(key)}
                        </span>
                        <span className="tnum font-medium text-ink">{Math.round(value)}</span>
                      </div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-canvas-sunken">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all",
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
                    </li>
                  );
                })}
              </ul>
            </Card>
          ) : null}

          <div className="grid grid-cols-2 gap-3">
            <StatTile
              label="Documents"
              value={documents?.count ?? property.document_count}
              icon={<FileStack className="h-4 w-4" />}
              onClick={() => onNavigate("documents")}
            />
            <StatTile
              label="Live claims"
              value={claims?.count ?? property.claim_count}
              icon={<Layers className="h-4 w-4" />}
              onClick={() => onNavigate("claims")}
            />
          </div>
        </div>
      </div>

      {/* ----------------------------------------------------- risk drivers */}
      {topFactors.length ? (
        <Card>
          <CardHeader
            title="What is driving the score"
            subtitle="Each rule contributes a stated weight to one category, and cites the evidence it fired on."
            icon={<AlertTriangle className="h-4 w-4" />}
            action={
              <Button variant="ghost" size="sm" onClick={() => onNavigate("risk")}>
                All factors <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            }
          />
          <ul className="divide-y divide-canvas-border">
            {topFactors.map((f: any) => (
              <li key={f.id} className="flex items-start gap-3 px-5 py-3.5">
                <span className="tnum mt-0.5 shrink-0 rounded-lg bg-status-conflictingBg px-2 py-1 text-2xs font-bold text-status-conflicting">
                  +{Math.round(f.weight)}
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[13px] font-medium text-ink">{f.title}</span>
                    <Chip tone="neutral">{f.category_label}</Chip>
                    <span className="font-mono text-[10px] text-ink-subtle">{f.rule_id}</span>
                  </div>
                  <p className="mt-1 text-2xs leading-relaxed text-ink-muted">
                    {truncate(f.explanation, 300)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
          {mitigations.length ? (
            <div className="border-t border-canvas-border px-5 py-3">
              <div className="section-label mb-2">Mitigating factors</div>
              <div className="flex flex-wrap gap-1.5">
                {mitigations.map((m: any) => (
                  <Chip key={m.id} tone="emerald">
                    {m.title} · {Math.round(m.weight)}
                  </Chip>
                ))}
              </div>
            </div>
          ) : null}
        </Card>
      ) : null}

      {/* -------------------------------------------------- next best action */}
      {plan?.steps?.length ? (
        <Card className="border-emerald-200 bg-emerald-50/40">
          <CardHeader
            title="Minimum evidence path"
            subtitle={
              plan.reaches_proceed
                ? `${plan.count} step${plan.count === 1 ? "" : "s"} would move this file from ${plan.baseline_state} to PROCEED.`
                : `${plan.count} step${plan.count === 1 ? "" : "s"} available, ending at ${plan.final_state}. Some exposure cannot be cleared by uploading more evidence.`
            }
            icon={<Sparkles className="h-4 w-4" />}
            action={
              <Button size="sm" onClick={() => onNavigate("resolution")}>
                Open resolution plan
              </Button>
            }
          />
          <ol className="flex flex-wrap gap-2 p-5">
            {plan.steps.map((s: any) => (
              <li
                key={s.id}
                className="flex items-center gap-2 rounded-lg bg-canvas-raised px-3 py-2 text-2xs ring-1 ring-emerald-200"
              >
                <span className="tnum grid h-5 w-5 place-items-center rounded-md bg-emerald-600 text-[10px] font-bold text-white">
                  {s.priority}
                </span>
                <span className="font-medium text-ink">{s.title}</span>
                <span className="tnum text-ink-muted">
                  {Math.round(s.risk_before)} → {Math.round(s.risk_after)}
                </span>
              </li>
            ))}
          </ol>
        </Card>
      ) : null}
    </div>
  );
}
