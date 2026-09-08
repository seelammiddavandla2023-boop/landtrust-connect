"use client";

/**
 * Presentation Mode.
 *
 * A live demonstration in front of a faculty panel goes wrong in predictable ways:
 * the presenter forgets which property shows which anomaly, opens the wrong tab, or
 * loses their place after a refresh. This screen removes all three. Fourteen ordered
 * steps, each with the route it opens and the property it needs, presenter notes in
 * readable type, arrow-key navigation, and the current position persisted in
 * localStorage so a mid-demo reload lands exactly where it left off.
 */

import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  ExternalLink,
  Keyboard,
  ListOrdered,
  Maximize2,
  Minimize2,
  Play,
  Presentation as PresentationIcon,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";
import React from "react";

import { useApi, useMounted, useRole } from "@/components/hooks";
import {
  BandBadge,
  Button,
  Card,
  CardHeader,
  Chip,
  DemoDataBadge,
  Disclaimer,
  ErrorState,
  LoadingCard,
  PrototypeBadge,
  SectionHeading,
  Skeleton,
  StateBadge,
  Tooltip,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import type { RiskBand, TransactionState } from "@/lib/domain";
import { cn, titleise } from "@/lib/format";

/* -------------------------------------------------------------------- types */

type StepProperty = { property_id: string; reference: string; label: string };

type Step = {
  n: number;
  title: string;
  route: string;
  property: StepProperty | null;
  say: string;
};

type Presentation = { steps: Step[]; disclaimer: string };

type Scenario = {
  key: string;
  label: string;
  property_id: string;
  reference: string;
  summary: string;
  demo_note: string;
  injected_anomalies: string[];
  expected_state: TransactionState;
  actual_state: TransactionState;
  expected_band: RiskBand;
  actual_band: RiskBand;
  matches_expectation: boolean;
  risk_score: number;
  document_count: number;
};

type Scenarios = { count: number; items: Scenario[] };

const STEP_KEY = "ltc.presentation.step";

/** `/properties/{id}?tab=claims` + property → a real href. */
function resolveRoute(step: Step): string {
  if (!step.property) return step.route;
  return step.route.replace("{id}", step.property.property_id);
}

/* -------------------------------------------------------------------- page */

export default function PresentationPage() {
  const presentation = useApi<Presentation>(() => endpoints.presentation(), []);
  const scenarios = useApi<Scenarios>(() => endpoints.scenarios(), []);
  const mounted = useMounted();

  const steps = presentation.data?.steps ?? [];
  const [index, setIndex] = React.useState(0);
  const [presenter, setPresenter] = React.useState(false);
  const [restored, setRestored] = React.useState(false);

  /* -- restore position once the steps are known -------------------------- */
  React.useEffect(() => {
    if (restored || steps.length === 0) return;
    try {
      const stored = window.localStorage.getItem(STEP_KEY);
      const parsed = stored === null ? 0 : Number.parseInt(stored, 10);
      if (Number.isFinite(parsed)) {
        setIndex(Math.min(Math.max(parsed, 0), steps.length - 1));
      }
    } catch {
      /* storage unavailable — start at the beginning */
    }
    setRestored(true);
  }, [restored, steps.length]);

  /* -- persist position --------------------------------------------------- */
  React.useEffect(() => {
    if (!restored) return;
    try {
      window.localStorage.setItem(STEP_KEY, String(index));
    } catch {
      /* storage unavailable — navigation still works, it just will not survive a reload */
    }
  }, [index, restored]);

  const goto = React.useCallback(
    (next: number) => {
      if (steps.length === 0) return;
      setIndex(Math.min(Math.max(next, 0), steps.length - 1));
    },
    [steps.length],
  );

  /* -- keyboard navigation ------------------------------------------------ */
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (target?.isContentEditable) return;
      if (e.key === "ArrowRight" || e.key === "PageDown") {
        e.preventDefault();
        setIndex((i) => Math.min(i + 1, Math.max(steps.length - 1, 0)));
      } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        setIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Escape") {
        setPresenter(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [steps.length]);

  if (presentation.loading) {
    return (
      <div className="space-y-5">
        <div className="max-w-3xl">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="mt-4 h-8 w-72" />
        </div>
        <LoadingCard rows={7} title="Loading the demonstration script" />
        <LoadingCard rows={5} />
      </div>
    );
  }

  if (presentation.error) {
    return <ErrorState error={presentation.error} onRetry={presentation.refetch} />;
  }
  if (!presentation.data || steps.length === 0) return null;

  const step = steps[Math.min(index, steps.length - 1)];
  const href = resolveRoute(step);

  return (
    <>
      <div className="space-y-8 pb-4">
        {/* ------------------------------------------------------- header */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <div className="mb-2.5 flex flex-wrap items-center gap-2">
              <PrototypeBadge />
              <DemoDataBadge />
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-ink">Presentation mode</h1>
            <p className="mt-2 text-sm leading-relaxed text-ink-muted">
              A {steps.length}-step guided walkthrough with the route and property for each step,
              so a live demonstration does not depend on remembering which file shows which anomaly.
              Use <KeyCap>←</KeyCap> and <KeyCap>→</KeyCap> to move, and your place is remembered
              across a page reload.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" size="sm" onClick={() => setPresenter(true)}>
              <Maximize2 className="h-3.5 w-3.5" />
              Presenter view
            </Button>
            <Button
              variant="subtle"
              size="sm"
              onClick={() => goto(0)}
              disabled={index === 0}
              title="Return to step 1"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Restart
            </Button>
          </div>
        </div>

        {/* ------------------------------------------------------ progress */}
        <ProgressRail steps={steps} index={index} onSelect={goto} />

        {/* ----------------------------------------------- current + rail */}
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,340px)]">
          <CurrentStep
            step={step}
            href={href}
            index={index}
            total={steps.length}
            onPrev={() => goto(index - 1)}
            onNext={() => goto(index + 1)}
          />
          <StepRail steps={steps} index={index} onSelect={goto} />
        </div>

        {/* ------------------------------------------------------ scenarios */}
        <section>
          <SectionHeading
            eyebrow="Load demo scenario"
            title="The six synthetic cases"
            description="Each property was generated with a known set of injected anomalies and a state the platform is expected to reach. The match indicator compares that expectation with the state the running system actually computed."
          />
          {scenarios.loading ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <LoadingCard rows={5} />
              <LoadingCard rows={5} />
            </div>
          ) : scenarios.error ? (
            <ErrorState error={scenarios.error} onRetry={scenarios.refetch} />
          ) : (
            <ScenarioGrid items={scenarios.data?.items ?? []} />
          )}
        </section>

        {/* ---------------------------------------------------- reset demo */}
        <section>
          <SectionHeading
            eyebrow="Demo control"
            title="Reset the demonstration"
            description="Rebuilds the database from the synthetic corpus and re-runs the entire pipeline. Useful between demonstrations; destructive to anything done during one."
          />
          <ResetDemoPanel
            onDone={() => {
              scenarios.refetch();
            }}
          />
        </section>

        <Disclaimer text={presentation.data.disclaimer} />
      </div>

      {/* ------------------------------------------------- presenter overlay */}
      <AnimatePresence>
        {mounted && presenter ? (
          <PresenterOverlay
            step={step}
            href={href}
            index={index}
            total={steps.length}
            onPrev={() => goto(index - 1)}
            onNext={() => goto(index + 1)}
            onClose={() => setPresenter(false)}
          />
        ) : null}
      </AnimatePresence>
    </>
  );
}

/* ------------------------------------------------------------------ pieces */

function KeyCap({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="mx-0.5 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded border border-canvas-borderStrong bg-canvas-raised px-1 font-mono text-[11px] font-medium text-ink-muted">
      {children}
    </kbd>
  );
}

function ProgressRail({
  steps,
  index,
  onSelect,
}: {
  steps: Step[];
  index: number;
  onSelect: (i: number) => void;
}) {
  return (
    <Card className="px-5 py-4">
      <div className="flex items-center justify-between gap-3">
        <span className="section-label">
          Step {index + 1} of {steps.length}
        </span>
        <span className="tnum text-2xs text-ink-subtle">
          {Math.round(((index + 1) / steps.length) * 100)}% through the script
        </span>
      </div>
      <div className="mt-3 flex gap-1">
        {steps.map((s, i) => (
          <button
            key={s.n}
            onClick={() => onSelect(i)}
            title={`${s.n}. ${s.title}`}
            aria-label={`Go to step ${s.n}: ${s.title}`}
            className={cn(
              "h-1.5 flex-1 rounded-full transition",
              i < index
                ? "bg-navy-400"
                : i === index
                  ? "bg-navy-900"
                  : "bg-canvas-sunken hover:bg-canvas-borderStrong",
            )}
            style={{ minWidth: 14 }}
          />
        ))}
      </div>
    </Card>
  );
}

function CurrentStep({
  step,
  href,
  index,
  total,
  onPrev,
  onNext,
}: {
  step: Step;
  href: string;
  index: number;
  total: number;
  onPrev: () => void;
  onNext: () => void;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-canvas-border bg-canvas-sunken/50 px-6 py-5">
        <div className="flex items-start gap-4">
          <div className="tnum grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-navy-fade text-2xl font-semibold text-white shadow-card">
            {step.n}
          </div>
          <div className="min-w-0 flex-1">
            <div className="section-label">Current step</div>
            <h2 className="mt-1 text-xl font-semibold leading-tight tracking-tight text-ink">
              {step.title}
            </h2>
            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <Chip tone="neutral">
                <ExternalLink className="h-3 w-3" />
                <code className="font-mono">{href}</code>
              </Chip>
              {step.property ? (
                <Chip tone="navy">
                  <Building2 className="h-3 w-3" />
                  {step.property.reference} · {step.property.label}
                </Chip>
              ) : (
                <span className="text-2xs italic text-ink-subtle">
                  no property — this step is a platform-wide screen
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={step.n}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          className="px-6 py-6"
        >
          <div className="section-label mb-2.5">Presenter notes</div>
          <p className="max-w-3xl text-[17px] leading-[1.8] text-ink">{step.say}</p>
        </motion.div>
      </AnimatePresence>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-canvas-border px-6 py-4">
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="md" onClick={onPrev} disabled={index === 0}>
            <ChevronLeft className="h-4 w-4" />
            Previous
          </Button>
          <Button variant="secondary" size="md" onClick={onNext} disabled={index === total - 1}>
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
          <span className="ml-1 hidden items-center gap-1 text-2xs text-ink-subtle sm:inline-flex">
            <Keyboard className="h-3 w-3" />
            <KeyCap>←</KeyCap>
            <KeyCap>→</KeyCap>
          </span>
        </div>
        <Link href={href}>
          <Button variant="primary" size="lg">
            <Play className="h-4 w-4" />
            Open this screen
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </div>
    </Card>
  );
}

function StepRail({
  steps,
  index,
  onSelect,
}: {
  steps: Step[];
  index: number;
  onSelect: (i: number) => void;
}) {
  return (
    <Card className="flex max-h-[640px] flex-col overflow-hidden">
      <CardHeader
        title="The full script"
        subtitle={`${steps.length} steps — jump to any of them`}
        icon={<ListOrdered className="h-4 w-4" />}
      />
      <ol className="min-h-0 flex-1 overflow-y-auto p-2">
        {steps.map((s, i) => {
          const active = i === index;
          const done = i < index;
          return (
            <li key={s.n}>
              <button
                onClick={() => onSelect(i)}
                className={cn(
                  "flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left transition",
                  active ? "bg-navy-50" : "hover:bg-canvas-sunken",
                )}
              >
                <span
                  className={cn(
                    "tnum mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md text-[10px] font-bold",
                    active
                      ? "bg-navy-900 text-white"
                      : done
                        ? "bg-status-verifiedBg text-status-verified"
                        : "bg-canvas-sunken text-ink-subtle",
                  )}
                >
                  {done ? <Check className="h-3 w-3" /> : s.n}
                </span>
                <span className="min-w-0">
                  <span
                    className={cn(
                      "block text-[13px] font-medium leading-snug",
                      active ? "text-navy-900" : "text-ink",
                    )}
                  >
                    {s.title}
                  </span>
                  <span className="mt-0.5 block truncate font-mono text-2xs text-ink-subtle">
                    {s.property ? s.property.reference : "—"} · {s.route}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

/* --------------------------------------------------------------- scenarios */

function ScenarioGrid({ items }: { items: Scenario[] }) {
  if (items.length === 0) {
    return (
      <Card className="p-6">
        <p className="text-sm text-ink-muted">No scenarios are loaded in the database.</p>
      </Card>
    );
  }
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {items.map((s, i) => (
        <motion.div
          key={s.key}
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ delay: Math.min(i * 0.05, 0.25), duration: 0.35 }}
        >
          <ScenarioCard scenario={s} />
        </motion.div>
      ))}
    </div>
  );
}

function ScenarioCard({ scenario: s }: { scenario: Scenario }) {
  return (
    <Card className="flex h-full flex-col overflow-hidden">
      <div className="flex items-start justify-between gap-3 border-b border-canvas-border px-5 py-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="tnum text-2xs font-semibold text-ink-subtle">{s.reference}</span>
            <span className="text-2xs text-ink-subtle">·</span>
            <span className="text-2xs text-ink-subtle">{s.document_count} documents</span>
          </div>
          <h3 className="mt-1 text-[15px] font-semibold leading-tight text-ink">{s.label}</h3>
        </div>
        <div className="shrink-0">
          <Tooltip
            content={
              s.matches_expectation
                ? "The running system reached the state and band this scenario was designed to produce."
                : "The running system reached a different state or band from the one this scenario was designed to produce."
            }
          >
            <span
              className={cn(
                "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-2xs font-semibold uppercase tracking-[0.06em] ring-1",
                s.matches_expectation
                  ? "bg-status-verifiedBg text-status-verified ring-status-verified/20"
                  : "bg-status-conflictingBg text-status-conflicting ring-status-conflicting/20",
              )}
            >
              {s.matches_expectation ? (
                <CircleCheck className="h-3 w-3" />
              ) : (
                <AlertTriangle className="h-3 w-3" />
              )}
              {s.matches_expectation ? "matches" : "diverges"}
            </span>
          </Tooltip>
        </div>
      </div>

      <div className="flex-1 space-y-4 px-5 py-4">
        <p className="text-[13px] leading-relaxed text-ink-muted">{s.summary}</p>

        <div className="rounded-xl bg-status-infoBg/60 px-3.5 py-3">
          <div className="flex items-center gap-1.5 text-2xs font-semibold uppercase tracking-[0.08em] text-status-info">
            <Sparkles className="h-3 w-3" />
            Demo note
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-ink">{s.demo_note}</p>
        </div>

        <div>
          <div className="section-label mb-1.5">
            Injected anomalies ({s.injected_anomalies.length})
          </div>
          {s.injected_anomalies.length === 0 ? (
            <span className="text-2xs italic text-ink-subtle">
              none — this file is deliberately clean
            </span>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {s.injected_anomalies.map((a) => (
                <Chip key={a} tone="amber">
                  {titleise(a)}
                </Chip>
              ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl bg-canvas-sunken px-3.5 py-3">
            <div className="section-label">Expected</div>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <StateBadge state={s.expected_state} size="sm" />
              <BandBadge band={s.expected_band} />
            </div>
          </div>
          <div className="rounded-xl bg-canvas-sunken px-3.5 py-3">
            <div className="section-label">Computed now</div>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <StateBadge state={s.actual_state} size="sm" />
              <BandBadge band={s.actual_band} />
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-canvas-border px-5 py-3.5">
        <div className="flex items-baseline gap-1.5">
          <span className="tnum text-lg font-semibold text-ink">{s.risk_score.toFixed(1)}</span>
          <span className="text-2xs text-ink-subtle">/ 100 composite risk</span>
        </div>
        <Link href={`/properties/${s.property_id}`}>
          <Button variant="secondary" size="sm">
            Open scenario
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </Link>
      </div>
    </Card>
  );
}

/* -------------------------------------------------------------- reset demo */

function ResetDemoPanel({ onDone }: { onDone: () => void }) {
  const [role, setRole] = useRole();
  const [confirming, setConfirming] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [result, setResult] = React.useState<string | null>(null);
  const [error, setError] = React.useState<any>(null);

  const isAdmin = role === "ADMIN";

  const run = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      await endpoints.resetDemo();
      setResult(
        "The database was rebuilt from the synthetic corpus and the pipeline re-ran over every document. All six scenarios are back at their generated state.",
      );
      setConfirming(false);
      onDone();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-4 px-5 py-5">
        <div className="flex min-w-0 max-w-3xl items-start gap-3.5">
          <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-status-partialBg text-status-partial">
            <RefreshCw className="h-4 w-4" />
          </span>
          <div>
            <h3 className="text-[15px] font-semibold text-ink">Reset demonstration data</h3>
            <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted">
              This drops and rebuilds the database from the synthetic corpus, then re-runs the whole
              pipeline: classification, text acquisition, layout analysis, claim extraction,
              cross-document validation, risk scoring and state assignment for all 31 documents.
              Anything done during a demonstration — applied resolution steps, consent decisions,
              relay messages, uploaded files — is discarded. Nothing real is lost, because none of
              this data is real; but a half-finished demonstration will be reset to the beginning.
            </p>
            <p className="mt-2 text-2xs leading-relaxed text-ink-subtle">
              Expect it to take a few seconds. The request is issued with the{" "}
              <code className="font-mono">ADMIN</code> role.
            </p>
          </div>
        </div>

        <div className="shrink-0">
          {!isAdmin ? (
            <div className="text-right">
              <Button variant="secondary" size="sm" onClick={() => setRole("ADMIN")}>
                <ShieldAlert className="h-3.5 w-3.5" />
                Switch to Administrator
              </Button>
              <p className="mt-1.5 max-w-[220px] text-2xs leading-snug text-ink-subtle">
                Reset is an administrator action. Your current role is {titleise(role)}.
              </p>
            </div>
          ) : !confirming ? (
            <Button variant="secondary" size="md" onClick={() => setConfirming(true)}>
              <RefreshCw className="h-4 w-4" />
              Reset demo data
            </Button>
          ) : (
            <div className="flex flex-col items-end gap-2">
              <span className="text-2xs font-semibold uppercase tracking-[0.08em] text-status-conflicting">
                Rebuild the database?
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setConfirming(false)}
                  disabled={busy}
                >
                  <X className="h-3.5 w-3.5" />
                  Cancel
                </Button>
                <Button variant="danger" size="sm" onClick={run} disabled={busy}>
                  <RefreshCw className={cn("h-3.5 w-3.5", busy && "animate-spin")} />
                  {busy ? "Rebuilding…" : "Yes, rebuild"}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      {result ? (
        <div className="flex items-start gap-2.5 border-t border-canvas-border bg-status-verifiedBg px-5 py-3.5">
          <CircleCheck className="mt-0.5 h-4 w-4 shrink-0 text-status-verified" />
          <p className="text-[13px] leading-relaxed text-ink">{result}</p>
        </div>
      ) : null}
      {error ? (
        <div className="flex items-start gap-2.5 border-t border-canvas-border bg-status-conflictingBg px-5 py-3.5">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-status-conflicting" />
          <p className="text-[13px] leading-relaxed text-ink">
            {error?.detail || error?.message || "The reset request failed."}
          </p>
        </div>
      ) : null}
    </Card>
  );
}

/* ------------------------------------------------------- presenter overlay */

function PresenterOverlay({
  step,
  href,
  index,
  total,
  onPrev,
  onNext,
  onClose,
}: {
  step: Step;
  href: string;
  index: number;
  total: number;
  onPrev: () => void;
  onNext: () => void;
  onClose: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="fixed inset-0 z-[60] flex flex-col bg-navy-fade"
    >
      <div className="absolute inset-0 bg-hero-grid [background-size:32px_32px]" aria-hidden />

      <div className="relative flex items-center justify-between px-8 py-5">
        <div className="flex items-center gap-2.5 text-white/70">
          <PresentationIcon className="h-4 w-4" />
          <span className="text-2xs font-semibold uppercase tracking-[0.14em]">
            LandTrust Connect · presenter view
          </span>
        </div>
        <button
          onClick={onClose}
          className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-2xs font-medium text-white/70 transition hover:bg-white/10 hover:text-white"
        >
          <Minimize2 className="h-3.5 w-3.5" />
          Exit (Esc)
        </button>
      </div>

      <div className="relative flex flex-1 items-center justify-center px-8 pb-8">
        <AnimatePresence mode="wait">
          <motion.div
            key={step.n}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -14 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="w-full max-w-4xl"
          >
            <div className="tnum text-[13px] font-semibold uppercase tracking-[0.16em] text-white/45">
              Step {step.n} of {total}
            </div>
            <h2 className="mt-3 text-4xl font-semibold leading-tight tracking-tight text-white">
              {step.title}
            </h2>
            <p className="mt-6 max-w-3xl text-[21px] leading-[1.7] text-white/85">{step.say}</p>

            <div className="mt-8 flex flex-wrap items-center gap-2.5">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1.5 font-mono text-[13px] text-white/80 ring-1 ring-white/15">
                <ExternalLink className="h-3.5 w-3.5" />
                {href}
              </span>
              {step.property ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1.5 text-[13px] text-white/80 ring-1 ring-white/15">
                  <Building2 className="h-3.5 w-3.5" />
                  {step.property.reference} · {step.property.label}
                </span>
              ) : null}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      <div className="relative flex flex-wrap items-center justify-between gap-4 border-t border-white/10 px-8 py-5">
        <div className="flex items-center gap-2">
          <button
            onClick={onPrev}
            disabled={index === 0}
            className="inline-flex items-center gap-1.5 rounded-lg bg-white/10 px-3 py-2 text-[13px] font-medium text-white transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-35"
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </button>
          <button
            onClick={onNext}
            disabled={index === total - 1}
            className="inline-flex items-center gap-1.5 rounded-lg bg-white/10 px-3 py-2 text-[13px] font-medium text-white transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-35"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>

        <div className="flex flex-1 items-center gap-1 px-2">
          {Array.from({ length: total }).map((_, i) => (
            <span
              key={i}
              className={cn(
                "h-1 flex-1 rounded-full",
                i < index ? "bg-white/45" : i === index ? "bg-emerald-300" : "bg-white/15",
              )}
            />
          ))}
        </div>

        <Link href={href} onClick={onClose}>
          <span className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-navy-900 transition hover:bg-white/90">
            <Play className="h-4 w-4" />
            Open this screen
          </span>
        </Link>
      </div>
    </motion.div>
  );
}
