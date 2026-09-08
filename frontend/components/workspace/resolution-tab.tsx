"use client";

/**
 * The autonomous resolution planner.
 *
 * Two things happen here, and the difference matters:
 *   • **Simulate** asks the scorer what would happen if a step were completed. It
 *     writes nothing.
 *   • **Apply** performs the step for real — the evidence is ingested through the
 *     ordinary pipeline and the whole assessment is recomputed. The new score is
 *     computed, never asserted, which is why it matches the simulation.
 *
 * This is the Review-2 acceptance sequence: HOLD → apply evidence → risk falls →
 * PROCEED.
 */

import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  ClipboardList,
  FlaskConical,
  Landmark,
  Play,
  Scale,
  Sparkles,
  UserCog,
} from "lucide-react";
import React from "react";

import { useApi, useCapabilities } from "@/components/hooks";
import {
  Button,
  Card,
  CardHeader,
  Chip,
  EmptyState,
  ErrorState,
  LoadingCard,
  StateBadge,
  Tooltip,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import { STATE_META, type TransactionState } from "@/lib/domain";
import { cn, dateTime, titleise } from "@/lib/format";

const PARTY_ICON: Record<string, any> = {
  OWNER: UserCog,
  BUYER: Building2,
  LENDER: Landmark,
  SURVEYOR: ClipboardList,
  REGISTRAR: Scale,
  LEGAL_REVIEWER: Scale,
};

const EFFORT_META: Record<string, { label: string; tone: "emerald" | "amber" | "red" }> = {
  LOW: { label: "Low effort", tone: "emerald" },
  MEDIUM: { label: "Medium effort", tone: "amber" },
  HIGH: { label: "High effort", tone: "red" },
};

export function ResolutionTab({
  propertyId,
  version,
  onApplied,
}: {
  propertyId: string;
  version: number;
  onApplied: () => void;
}) {
  const { data, error, loading, refetch } = useApi<any>(
    () => endpoints.resolution(propertyId),
    [propertyId, version],
  );
  const [applying, setApplying] = React.useState<string | null>(null);
  const caps = useCapabilities();
  const mayApply = caps.can("APPLY_RESOLUTION");
  const [result, setResult] = React.useState<any>(null);
  const [simulated, setSimulated] = React.useState<Record<string, any>>({});
  const [selection, setSelection] = React.useState<string[]>([]);
  const [combined, setCombined] = React.useState<any>(null);
  const [failure, setFailure] = React.useState<string | null>(null);

  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (loading || !data) return <LoadingCard rows={8} title="Resolution plan" />;

  const steps: any[] = data.steps ?? [];

  const simulate = async (key: string) => {
    try {
      const out = await endpoints.simulate(propertyId, [key]);
      setSimulated((prev) => ({ ...prev, [key]: out }));
    } catch (e: any) {
      setFailure(e?.detail || e?.message || "Simulation failed.");
    }
  };

  const simulateSelection = async () => {
    if (!selection.length) return;
    try {
      setCombined(await endpoints.simulate(propertyId, selection));
    } catch (e: any) {
      setFailure(e?.detail || e?.message || "Simulation failed.");
    }
  };

  const apply = async (key: string) => {
    setApplying(key);
    setFailure(null);
    try {
      const out = await endpoints.applyAction(propertyId, key);
      setResult(out);
      setCombined(null);
      setSelection([]);
      onApplied();
      refetch();
    } catch (e: any) {
      setFailure(e?.detail || e?.message || "Could not apply this step.");
    } finally {
      setApplying(null);
    }
  };

  const toggle = (key: string) =>
    setSelection((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));

  return (
    <div className="space-y-4">
      {/* --------------------------------------------------- plan summary */}
      <Card className={cn(data.reaches_proceed ? "border-emerald-200" : "border-status-partial/30")}>
        <CardHeader
          title="Minimum evidence path"
          subtitle="Computed by a greedy search over counterfactual re-scorings: at each step, the action with the best risk reduction per unit of effort. Because the risk model is monotone in every rule weight, each predicted score is exact rather than estimated."
          icon={<Sparkles className="h-4 w-4" />}
        />
        <div className="p-5">
          {steps.length === 0 ? (
            <EmptyState
              title="No corrective evidence outstanding"
              description={data.note}
              icon={<CheckCircle2 className="h-5 w-5 text-status-verified" />}
            />
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-3">
                <ScorePill label="Current" value={data.baseline_risk} state={data.baseline_state} />
                <ArrowRight className="h-4 w-4 shrink-0 text-ink-subtle" />
                <ScorePill
                  label={`After ${steps.length} step${steps.length === 1 ? "" : "s"}`}
                  value={data.final_risk}
                  state={data.final_state}
                  highlight
                />
                <div className="ml-auto">
                  <Chip tone={data.reaches_proceed ? "emerald" : "amber"}>
                    {data.reaches_proceed ? "Reaches PROCEED" : `Ends at ${data.final_state}`}
                  </Chip>
                </div>
              </div>
              <p className="mt-3 text-[13px] leading-relaxed text-ink-muted">{data.note}</p>

              {/* the descending staircase makes the plan's shape readable at a glance */}
              <div className="mt-5">
                <Staircase baseline={data.baseline_risk} steps={steps} />
              </div>
            </>
          )}
        </div>
      </Card>

      {failure ? <ErrorState error={failure} /> : null}

      {/* ------------------------------------------------------ applied */}
      <AnimatePresence>
        {result ? (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <Card className="border-emerald-300 bg-emerald-50/50">
              <CardHeader
                title={`Applied — ${result.action.title}`}
                subtitle={
                  result.document
                    ? `${result.document.filename} was ingested through the full pipeline and the whole assessment was recomputed.`
                    : "The corresponding risk factor was closed against the evidence supplied, and the assessment was recomputed."
                }
                icon={<CheckCircle2 className="h-4 w-4 text-status-verified" />}
              />
              <div className="flex flex-wrap items-center gap-3 p-5">
                <ScorePill label="Before" value={result.before.overall_score} state={result.before.state} />
                <ArrowRight className="h-4 w-4 text-ink-subtle" />
                <ScorePill
                  label="After"
                  value={result.after.overall_score}
                  state={result.after.state}
                  highlight
                />
                <Chip tone="emerald">−{result.delta.toFixed(1)} points</Chip>
                {result.after.state !== result.before.state ? (
                  <Chip tone="navy">
                    {result.before.state} → {result.after.state}
                  </Chip>
                ) : null}
              </div>
            </Card>
          </motion.div>
        ) : null}
      </AnimatePresence>

      {/* -------------------------------------------------------- steps */}
      {steps.length > 0 ? (
        <Card>
          <CardHeader
            title="Recommended actions"
            subtitle="Priority, required evidence, responsible party, authority and expected impact"
            action={
              selection.length ? (
                <div className="flex items-center gap-2">
                  <span className="text-2xs text-ink-muted">{selection.length} selected</span>
                  <Button variant="secondary" size="sm" onClick={simulateSelection}>
                    <FlaskConical className="h-3.5 w-3.5" />
                    Simulate together
                  </Button>
                </div>
              ) : null
            }
          />

          {combined ? (
            <div className="border-b border-canvas-border bg-navy-50/60 px-5 py-3">
              <div className="flex flex-wrap items-center gap-3">
                <span className="section-label">Combined simulation</span>
                <ScorePill label="Now" value={combined.before.overall_score} state={combined.before.state} />
                <ArrowRight className="h-3.5 w-3.5 text-ink-subtle" />
                <ScorePill
                  label="If all completed"
                  value={combined.after.overall_score}
                  state={combined.after.state}
                  highlight
                />
                <Chip tone="emerald">−{combined.delta.toFixed(1)}</Chip>
                <span className="text-2xs text-ink-subtle">
                  clears {combined.resolved_rules.length} rule
                  {combined.resolved_rules.length === 1 ? "" : "s"} · nothing written
                </span>
              </div>
            </div>
          ) : null}

          <ol className="divide-y divide-canvas-border">
            {steps.map((s) => {
              const Icon = PARTY_ICON[s.responsible_party] ?? UserCog;
              const effort = EFFORT_META[s.effort] ?? EFFORT_META.MEDIUM;
              const sim = simulated[s.action_key];
              const done = s.status === "COMPLETED";
              return (
                <li key={s.id} className="px-5 py-4">
                  <div className="flex items-start gap-4">
                    <div className="flex shrink-0 flex-col items-center gap-2">
                      <span
                        className={cn(
                          "tnum grid h-8 w-8 place-items-center rounded-xl text-sm font-bold",
                          done ? "bg-status-verified text-white" : "bg-navy-900 text-white",
                        )}
                      >
                        {done ? <CheckCircle2 className="h-4 w-4" /> : s.priority}
                      </span>
                      <input
                        type="checkbox"
                        checked={selection.includes(s.action_key)}
                        onChange={() => toggle(s.action_key)}
                        disabled={done}
                        aria-label={`Include ${s.title} in the combined simulation`}
                        className="h-3.5 w-3.5 rounded border-canvas-borderStrong"
                      />
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="text-[15px] font-semibold text-ink">{s.title}</h4>
                        {done ? <Chip tone="emerald">completed</Chip> : null}
                        <Chip tone={effort.tone}>{effort.label}</Chip>
                      </div>
                      <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted">
                        {s.description}
                      </p>

                      <dl className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
                        <div>
                          <dt className="section-label">Required evidence</dt>
                          <dd className="mt-0.5 text-2xs text-ink">{s.required_evidence}</dd>
                        </div>
                        <div>
                          <dt className="section-label">Responsible party</dt>
                          <dd className="mt-0.5 flex items-center gap-1.5 text-2xs text-ink">
                            <Icon className="h-3.5 w-3.5 text-ink-subtle" />
                            {titleise(s.responsible_party)}
                          </dd>
                        </div>
                        <div>
                          <dt className="section-label">Authority required</dt>
                          <dd className="mt-0.5 text-2xs text-ink">
                            {s.authority_required || "—"}
                          </dd>
                        </div>
                      </dl>

                      {s.resolves_rules?.length ? (
                        <div className="mt-3 flex flex-wrap items-center gap-1.5">
                          <span className="text-2xs text-ink-subtle">Clears:</span>
                          {s.resolves_rules.map((r: string) => (
                            <span
                              key={r}
                              className="rounded bg-canvas-sunken px-1.5 py-0.5 font-mono text-[10px] text-ink-muted"
                            >
                              {r}
                            </span>
                          ))}
                        </div>
                      ) : null}

                      <div className="mt-4 flex flex-wrap items-center gap-3">
                        <div className="flex items-center gap-2 rounded-lg bg-canvas-sunken px-3 py-1.5">
                          <span className="tnum text-sm font-semibold text-ink">
                            {Math.round(s.risk_before)}
                          </span>
                          <ArrowRight className="h-3 w-3 text-ink-subtle" />
                          <span className="tnum text-sm font-semibold text-status-verified">
                            {Math.round(s.risk_after)}
                          </span>
                          <span className="text-2xs text-ink-subtle">expected</span>
                          <StateBadge state={s.state_after as TransactionState} size="sm" />
                        </div>

                        {!done ? (
                          <>
                            <Button variant="secondary" size="sm" onClick={() => simulate(s.action_key)}>
                              <FlaskConical className="h-3.5 w-3.5" />
                              Simulate
                            </Button>
                            <Tooltip
                              content={
                                mayApply
                                  ? "Ingests the corresponding evidence through the real pipeline and recomputes the whole assessment. The new score is computed, not written."
                                  : caps.why("APPLY_RESOLUTION")
                              }
                            >
                              <Button
                                size="sm"
                                onClick={() => apply(s.action_key)}
                                disabled={applying !== null || !mayApply}
                              >
                                <Play className="h-3.5 w-3.5" />
                                {applying === s.action_key ? "Applying…" : "Apply this step"}
                              </Button>
                            </Tooltip>
                          </>
                        ) : (
                          <span className="text-2xs text-ink-subtle">
                            Applied {dateTime(s.applied_at)}
                          </span>
                        )}
                      </div>

                      {sim ? (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          className="mt-3 overflow-hidden rounded-lg bg-navy-50 px-3 py-2.5"
                        >
                          <div className="flex flex-wrap items-center gap-2 text-2xs">
                            <span className="font-semibold text-navy-800">Simulated:</span>
                            <span className="tnum text-ink">
                              {sim.before.overall_score} → {sim.after.overall_score}
                            </span>
                            <StateBadge state={sim.after.state as TransactionState} size="sm" />
                            <span className="text-ink-subtle">
                              clears {sim.resolved_rules.join(", ") || "no rules"} · nothing written
                            </span>
                          </div>
                        </motion.div>
                      ) : null}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        </Card>
      ) : null}

      {/* ------------------------------------------------ closed rules */}
      {data.closed_rules?.length ? (
        <Card>
          <CardHeader
            title="Risk factors closed against evidence"
            subtitle="Some evidence — a notarised affidavit, a registrar's written confirmation — cannot be verified automatically. Closing a factor against such a document is recorded with the document that closed it, so a closure is never anonymous."
          />
          <ul className="divide-y divide-canvas-border">
            {data.closed_rules.map((r: any, i: number) => (
              <li key={i} className="px-5 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-canvas-sunken px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">
                    {r.rule_id}
                  </span>
                  <span className="text-[13px] font-medium text-ink">{r.document_name}</span>
                  <span className="text-2xs text-ink-subtle">{dateTime(r.closed_at)}</span>
                </div>
                <p className="mt-1 text-2xs leading-relaxed text-ink-muted">{r.note}</p>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
  );
}

function ScorePill({
  label,
  value,
  state,
  highlight,
}: {
  label: string;
  value: number;
  state: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl px-3.5 py-2",
        highlight ? "bg-status-verifiedBg" : "bg-canvas-sunken",
      )}
    >
      <div className="section-label">{label}</div>
      <div className="mt-0.5 flex items-center gap-2">
        <span
          className={cn(
            "tnum text-xl font-semibold",
            highlight ? "text-status-verified" : "text-ink",
          )}
        >
          {Math.round(value)}
        </span>
        <StateBadge state={state as TransactionState} size="sm" />
      </div>
    </div>
  );
}

/** The plan as a descending staircase — the shape of the argument, in one glance. */
function Staircase({ baseline, steps }: { baseline: number; steps: any[] }) {
  const points = [{ label: "Now", value: baseline, state: steps[0]?.state_before ?? "HOLD" }].concat(
    steps.map((s) => ({ label: `Step ${s.priority}`, value: s.risk_after, state: s.state_after })),
  );
  const max = Math.max(...points.map((p) => p.value), 100);

  return (
    <div className="flex items-end gap-2">
      {points.map((p, i) => {
        const heightPct = (p.value / max) * 100;
        const tone =
          p.state === "PROCEED"
            ? "bg-risk-low"
            : p.state === "WARN"
              ? "bg-risk-moderate"
              : p.state === "HOLD"
                ? "bg-risk-high"
                : "bg-risk-critical";
        return (
          <div key={i} className="flex min-w-0 flex-1 flex-col items-center gap-1.5">
            <span className="tnum text-2xs font-semibold text-ink">{Math.round(p.value)}</span>
            <div className="flex h-28 w-full items-end">
              <motion.div
                initial={{ height: 0 }}
                animate={{ height: `${Math.max(heightPct, 4)}%` }}
                transition={{ duration: 0.6, delay: i * 0.09, ease: [0.22, 1, 0.36, 1] }}
                className={cn("w-full rounded-t-lg", tone)}
              />
            </div>
            <span className="truncate text-2xs text-ink-muted">{p.label}</span>
            <span
              className={cn(
                "text-[9px] font-semibold uppercase tracking-wide",
                STATE_META[p.state as TransactionState]?.fg,
              )}
            >
              {p.state}
            </span>
          </div>
        );
      })}
    </div>
  );
}
