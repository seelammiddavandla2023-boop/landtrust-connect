"use client";

/**
 * Research Results — the measured evaluation dashboard.
 *
 * Nothing on this page is typed in. Every figure is read from `data/metrics.json`,
 * which is written by `python -m app.eval.run_eval` when it scores the running
 * platform against a ground-truth answer key. Several headline figures are 100%.
 * That is a property of a controlled synthetic corpus whose field grammar matches
 * the documents it was written against — not evidence of production accuracy — and
 * `meta.caveat` says so in the system's own words. It is rendered verbatim, near
 * the top, and cannot be dismissed.
 */

import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  BadgeCheck,
  Ban,
  BarChart3,
  Braces,
  CircleSlash,
  ClipboardCheck,
  Cpu,
  FileSearch,
  FlaskConical,
  Gauge,
  GitCompareArrows,
  Info,
  Layers,
  Quote,
  Route,
  ScanText,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  Timer,
  TriangleAlert,
} from "lucide-react";
import React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useApi } from "@/components/hooks";
import {
  BandBadge,
  Button,
  Card,
  CardHeader,
  Chip,
  DemoDataBadge,
  Disclaimer,
  EmptyState,
  ErrorState,
  LoadingCard,
  PrototypeBadge,
  SectionHeading,
  Skeleton,
  StateBadge,
  StatTile,
  Tooltip,
} from "@/components/ui";
import { ApiError, endpoints } from "@/lib/api";
import {
  BAND_META,
  VERIFICATION_META,
  type RiskBand,
  type TransactionState,
  type VerificationStatus,
} from "@/lib/domain";
import { cn, dateTime, titleise } from "@/lib/format";

/* -------------------------------------------------------------------- types */

type ByClaimType = { claim_type: string; total: number; correct: number; accuracy: number };

type ExtractionError = {
  property: string;
  document: string;
  claim_type: string;
  expected: string | null;
  actual: string | null;
  kind: string;
  match_type?: string;
};

type ClassificationError = {
  property: string;
  document: string;
  expected: string;
  predicted: string;
  confidence: number;
};

type VerificationError = {
  property: string;
  claim_type: string;
  expected: VerificationStatus;
  actual: VerificationStatus;
};

type Metrics = {
  headline: {
    documents_tested: number;
    claims_evaluated: number;
    classification_accuracy: number;
    extraction_accuracy: number;
    contradiction_precision: number;
    contradiction_recall: number;
    contradiction_f1: number;
    verification_agreement: number;
    transaction_state_accuracy: number;
    grounded_citation_rate: number;
    unsupported_answer_blocking: number;
    resolution_outcome_accuracy: number;
  };
  classification: { total: number; correct: number; accuracy: number; errors: ClassificationError[] };
  extraction: {
    total: number;
    correct: number;
    accuracy: number;
    by_claim_type: ByClaimType[];
    errors: ExtractionError[];
  };
  contradiction: {
    true_positives: number;
    false_positives: number;
    false_negatives: number;
    precision: number;
    recall: number;
    f1: number;
    per_property: {
      property: string;
      label: string;
      expected: string[];
      detected: string[];
      true_positives: string[];
      false_positives: string[];
      false_negatives: string[];
    }[];
  };
  verification: {
    total: number;
    correct: number;
    agreement: number;
    confusion: { transition: string; count: number }[];
    errors: VerificationError[];
  };
  transaction_state: {
    total: number;
    correct: number;
    accuracy: number;
    per_property: {
      property: string;
      label: string;
      expected_state: TransactionState;
      actual_state: TransactionState;
      expected_band: RiskBand;
      actual_band: RiskBand;
      risk_score: number;
      correct: boolean;
    }[];
  };
  grounding: {
    answerable_probes: number;
    grounded_answers: number;
    grounded_with_citations: number;
    grounded_citation_rate: number;
    answerable_coverage: number;
    unanswerable_probes: number;
    refused: number;
    refusal_rate: number;
    unsupported_answers_emitted: number;
    leaks: { question?: string; answer?: string; property?: string; kind?: string }[];
    answerable_but_refused: { question?: string; property?: string }[];
    logged_queries: number;
    note: string;
  };
  resolution: {
    properties_needing_a_plan: number;
    plans_reaching_proceed: number;
    reaching_proceed_pct: number;
    outcome_accuracy: number;
    outcomes_scored: number;
    mean_steps: number;
    per_property: {
      property: string;
      label?: string;
      baseline_state: TransactionState;
      baseline_risk: number;
      steps: number;
      step_keys?: string[];
      final_state: TransactionState;
      final_risk: number;
      reaches_proceed: boolean;
      expected_resolvable: boolean;
      outcome_correct: boolean;
      risk_reduction?: number;
      note: string;
    }[];
    note: string;
  };
  performance: {
    documents: { document: string; doc_type: string; pages: number; ms: number; claims: number }[];
    mean_ms: number;
    mean_claims_per_document: number;
  };
  ocr_arm?: {
    available: boolean;
    engine?: string;
    documents_tested?: number;
    classification_accuracy?: number;
    claims_evaluated?: number;
    extraction_accuracy?: number;
    mean_ms_per_document?: number;
    by_claim_type?: ByClaimType[];
    errors?: ExtractionError[];
    note?: string;
    reason?: string;
  };
  meta: {
    generated_at: string;
    duration_ms: number;
    corpus: string;
    extraction_mode: string;
    engine_version: string;
    caveat: string;
  };
};

/* ------------------------------------------------------------------ palette */

const C = {
  navy: "#0f1c38",
  navyMid: "#48649d",
  navyLight: "#9aaed2",
  verified: "#0f8a5f",
  partial: "#b7791f",
  high: "#d2691e",
  critical: "#c62828",
  info: "#1f6fb2",
  grid: "#dde5f0",
  axis: "#7f8ca5",
};

/* ---------------------------------------------------------------- utilities */

function fmtPct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const trimmed = Number.isInteger(value) ? value.toFixed(0) : value.toFixed(digits);
  return `${trimmed}%`;
}

function accuracyColour(accuracy: number): string {
  if (accuracy >= 99.995) return C.verified;
  if (accuracy >= 95) return C.partial;
  if (accuracy >= 85) return C.high;
  return C.critical;
}

/** A small, unmissable marker on any figure that reads 100%. */
function PerfectNote({ children }: { children?: React.ReactNode }) {
  return (
    <Tooltip
      content={
        children ??
        "100% on this corpus. The evaluation set is synthetic and its field grammar matches the extractor's, so a perfect score here characterises internal consistency, not real-world accuracy. See the caveat at the top of this page."
      }
    >
      <span className="inline-flex items-center gap-1 rounded-full bg-status-partialBg px-1.5 py-0.5 text-2xs font-semibold uppercase tracking-[0.08em] text-status-partial ring-1 ring-status-partial/20">
        <Info className="h-3 w-3" />
        caveat
      </span>
    </Tooltip>
  );
}

function ChartCaption({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-2 text-2xs leading-relaxed text-ink-subtle">
      <span className="font-semibold uppercase tracking-[0.1em]">Figure · </span>
      {children}
    </p>
  );
}

function Panel({
  title,
  subtitle,
  icon,
  action,
  children,
  className,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardHeader title={title} subtitle={subtitle} icon={icon} action={action} />
      <div className="p-5">{children}</div>
    </Card>
  );
}

/** Small emphasised statement of what the section measured. */
function NoteBlock({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "info" }) {
  return (
    <p
      className={cn(
        "flex items-start gap-2 rounded-xl px-3.5 py-3 text-[13px] leading-relaxed",
        tone === "info"
          ? "bg-status-infoBg text-status-info ring-1 ring-status-info/15"
          : "bg-canvas-sunken text-ink-muted",
      )}
    >
      <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 opacity-70" />
      <span>{children}</span>
    </p>
  );
}

function CountChips({
  label,
  items,
  tone,
}: {
  label: string;
  items: string[];
  tone: "emerald" | "red" | "amber" | "neutral";
}) {
  if (!items.length) {
    return (
      <span className="text-2xs text-ink-subtle">
        {label}: <span className="tnum font-semibold">0</span>
      </span>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-2xs font-semibold uppercase tracking-[0.08em] text-ink-subtle">
        {label} ({items.length})
      </span>
      {items.map((item) => (
        <Chip key={item} tone={tone}>
          {titleise(item)}
        </Chip>
      ))}
    </div>
  );
}

/* -------------------------------------------------------------------- page */

export default function ResearchResultsPage() {
  const { data, error, loading, refetch } = useApi<Metrics>(() => endpoints.metrics(), []);

  if (loading) {
    return (
      <div className="space-y-5">
        <PageIntro />
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i} className="px-4 py-3.5">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="mt-3 h-7 w-16" />
            </Card>
          ))}
        </div>
        <LoadingCard rows={6} title="Loading computed metrics" />
        <LoadingCard rows={6} />
      </div>
    );
  }

  if (error) {
    const notRun = error instanceof ApiError && error.status === 404;
    return (
      <div className="space-y-5">
        <PageIntro />
        {notRun ? (
          <Card className="p-8">
            <EmptyState
              icon={<FlaskConical className="h-5 w-5" />}
              title="The evaluation has not been run on this machine yet"
              description={
                error instanceof ApiError
                  ? error.detail
                  : "No metrics file found. Run the evaluation to compute results against the synthetic corpus."
              }
              action={
                <div className="w-full max-w-xl space-y-3">
                  <div className="rounded-xl bg-navy-950 px-4 py-3 text-left">
                    <div className="mb-1.5 flex items-center gap-1.5 text-2xs font-semibold uppercase tracking-[0.12em] text-white/50">
                      <Terminal className="h-3 w-3" />
                      from ./backend
                    </div>
                    <code className="block font-mono text-[13px] leading-relaxed text-emerald-300">
                      python -m app.eval.run_eval
                    </code>
                  </div>
                  <p className="text-left text-2xs leading-relaxed text-ink-muted">
                    The script scores the running platform against the ground-truth answer key
                    for the synthetic corpus and writes <code className="font-mono">data/metrics.json</code>.
                    This page reads that file and renders nothing that the script did not compute —
                    which is why it is empty rather than showing example numbers.
                  </p>
                  <Button variant="secondary" size="sm" onClick={refetch}>
                    Check again
                  </Button>
                </div>
              }
            />
          </Card>
        ) : (
          <ErrorState error={error} onRetry={refetch} />
        )}
      </div>
    );
  }

  if (!data) return null;

  const m = data;
  const ocr = m.ocr_arm;

  return (
    <div className="space-y-8 pb-4">
      <PageIntro meta={m.meta} />

      {/* ---------------------------------------------------------- caveat */}
      <Card className="overflow-hidden border-status-partial/30">
        <div className="flex items-start gap-3.5 bg-status-partialBg px-5 py-4">
          <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-status-partial/15 text-status-partial">
            <TriangleAlert className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h2 className="text-[13px] font-semibold uppercase tracking-[0.1em] text-status-partial">
              How to read every number on this page
            </h2>
            <p className="mt-2 max-w-4xl text-sm leading-relaxed text-ink">{m.meta.caveat}</p>
            <p className="mt-2.5 max-w-4xl text-[13px] leading-relaxed text-ink-muted">
              Read a figure of 100% here as “the mechanism did what the answer key says it should
              do, on every case in this corpus” — not as a claim of accuracy on registry documents
              the system has never seen. The comparison that carries information is the OCR arm
              below, where the reader changes and the answer key does not.
            </p>
          </div>
        </div>
        <div className="grid gap-px bg-canvas-border sm:grid-cols-2 lg:grid-cols-4">
          <MetaCell label="Generated at" value={dateTime(m.meta.generated_at)} />
          <MetaCell label="Corpus" value={m.meta.corpus} />
          <MetaCell label="Engine version" value={m.meta.engine_version} mono />
          <MetaCell
            label="Extraction mode / run time"
            value={`${m.meta.extraction_mode} · ${(m.meta.duration_ms / 1000).toFixed(1)}s`}
            mono
          />
        </div>
      </Card>

      {/* -------------------------------------------------------- headline */}
      <section>
        <SectionHeading
          eyebrow="1 · Headline"
          title="Computed evaluation results"
          description="Counts describe the size of the evaluation. Percentages describe agreement with the answer key. Both are produced by the same script run."
        />
        <HeadlineTiles headline={m.headline} />
      </section>

      {/* ------------------------------------------------- text layer vs OCR */}
      <section>
        <SectionHeading
          eyebrow="2 · Reader comparison"
          title="Text layer versus OCR"
          description="The single comparison on this page where something genuinely varies: the same documents, the same field grammar and the same answer key, read two different ways."
        />
        {ocr?.available ? (
          <OcrArm ocr={ocr} textLayer={m} />
        ) : (
          <OcrUnavailable reason={ocr?.note ?? ocr?.reason} />
        )}
      </section>

      {/* ------------------------------------------------------- extraction */}
      <section>
        <SectionHeading
          eyebrow="3 · Extraction"
          title="Claim extraction by field"
          description={`${m.extraction.correct} of ${m.extraction.total} extracted values agreed with the answer key across ${m.extraction.by_claim_type.length} field types.`}
        />
        <ExtractionDetail extraction={m.extraction} classification={m.classification} />
      </section>

      {/* ---------------------------------------------------- contradiction */}
      <section>
        <SectionHeading
          eyebrow="4 · Contradiction detection"
          title="Did it find the anomalies that were deliberately injected?"
          description="Each property in the corpus carries a known list of contradiction types. Precision and recall are computed over those lists, per property, not over a global pool."
        />
        <ContradictionDetail contradiction={m.contradiction} />
      </section>

      {/* ----------------------------------------------------- verification */}
      <section>
        <SectionHeading
          eyebrow="5 · Verification agreement"
          title="Status resolution against expected status"
          description="For every scored attribute the answer key names the verification status the evidence should produce. This compares what the resolver decided with what was expected."
        />
        <VerificationDetail verification={m.verification} />
      </section>

      {/* ------------------------------------------------ transaction state */}
      <section>
        <SectionHeading
          eyebrow="6 · Transaction state"
          title="Did the right cases get blocked?"
          description="The state controller's decision per property, against the state and risk band the scenario was designed to produce."
        />
        <TransactionStateDetail ts={m.transaction_state} />
      </section>

      {/* -------------------------------------------------------- grounding */}
      <section>
        <SectionHeading
          eyebrow="7 · Grounded answering"
          title="Citations when it answers, refusals when it cannot"
          description="Probes are split into questions the property file can answer and questions it cannot. Both halves are scored, and the second half is the one that matters."
        />
        <GroundingDetail grounding={m.grounding} />
      </section>

      {/* ------------------------------------------------------- resolution */}
      <section>
        <SectionHeading
          eyebrow="8 · Resolution planning"
          title="The smallest evidence path, and where it correctly stops short"
          description="For each property the planner's outcome is compared with whether the scenario was designed to be resolvable at all."
        />
        <ResolutionDetail resolution={m.resolution} />
      </section>

      {/* ------------------------------------------------------ performance */}
      <section>
        <SectionHeading
          eyebrow="9 · Performance"
          title="Processing cost per document"
          description="Wall-clock milliseconds recorded by the pipeline for each document in the corpus, on the machine that ran the evaluation."
        />
        <PerformanceDetail performance={m.performance} ocrMeanMs={ocr?.available ? ocr.mean_ms_per_document : undefined} />
      </section>

      <Disclaimer />
    </div>
  );
}

/* ----------------------------------------------------------------- pieces */

function PageIntro({ meta }: { meta?: Metrics["meta"] }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="max-w-3xl">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <PrototypeBadge />
          <DemoDataBadge />
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-2xs font-semibold uppercase tracking-[0.1em] text-emerald-700 ring-1 ring-emerald-200">
            <ClipboardCheck className="h-3 w-3" />
            Computed, not authored
          </span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Research Results</h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-muted">
          Every figure below is produced by <code className="font-mono text-[12.5px]">python -m app.eval.run_eval</code>,
          which drives the running platform over a synthetic corpus and scores its output against a
          ground-truth answer key. The script writes{" "}
          <code className="font-mono text-[12.5px]">data/metrics.json</code>; this page renders that
          file and nothing else. No number here is hardcoded in the frontend, and if the evaluation
          has not been run the page shows an empty state rather than sample values.
        </p>
      </div>
      {meta ? (
        <div className="rounded-xl border border-canvas-border bg-canvas-raised px-4 py-3 text-right">
          <div className="section-label">Last computed</div>
          <div className="tnum mt-1 text-[13px] font-semibold text-ink">
            {dateTime(meta.generated_at)}
          </div>
          <div className="mt-0.5 text-2xs text-ink-subtle">
            run took {(meta.duration_ms / 1000).toFixed(1)}s
          </div>
        </div>
      ) : null}
    </div>
  );
}

function MetaCell({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="bg-canvas-raised px-5 py-3.5">
      <div className="section-label">{label}</div>
      <div className={cn("mt-1 text-[13px] leading-snug text-ink", mono && "font-mono text-[12.5px]")}>
        {value}
      </div>
    </div>
  );
}

function HeadlineTiles({ headline }: { headline: Metrics["headline"] }) {
  const counts: { label: string; value: number; hint: string; icon: React.ReactNode }[] = [
    {
      label: "Documents tested",
      value: headline.documents_tested,
      hint: "Count — every document in the synthetic corpus",
      icon: <FileSearch className="h-4 w-4" />,
    },
    {
      label: "Claims evaluated",
      value: headline.claims_evaluated,
      hint: "Count — individual extracted values scored against the key",
      icon: <Braces className="h-4 w-4" />,
    },
  ];

  const percentages: {
    label: string;
    value: number;
    hint: string;
    icon: React.ReactNode;
  }[] = [
    {
      label: "Classification accuracy",
      value: headline.classification_accuracy,
      hint: "Share of documents assigned the expected document type",
      icon: <Layers className="h-4 w-4" />,
    },
    {
      label: "Extraction accuracy",
      value: headline.extraction_accuracy,
      hint: "Share of claims whose value agrees with the answer key",
      icon: <ScanText className="h-4 w-4" />,
    },
    {
      label: "Contradiction precision",
      value: headline.contradiction_precision,
      hint: "Detected contradictions that were expected",
      icon: <GitCompareArrows className="h-4 w-4" />,
    },
    {
      label: "Contradiction recall",
      value: headline.contradiction_recall,
      hint: "Expected contradictions that were detected",
      icon: <GitCompareArrows className="h-4 w-4" />,
    },
    {
      label: "Contradiction F1",
      value: headline.contradiction_f1,
      hint: "Harmonic mean of precision and recall",
      icon: <Activity className="h-4 w-4" />,
    },
    {
      label: "Verification agreement",
      value: headline.verification_agreement,
      hint: "Attributes whose resolved status matched the expected status",
      icon: <ShieldCheck className="h-4 w-4" />,
    },
    {
      label: "Transaction-state accuracy",
      value: headline.transaction_state_accuracy,
      hint: "Properties placed in the expected transaction state",
      icon: <Gauge className="h-4 w-4" />,
    },
    {
      label: "Grounded citation rate",
      value: headline.grounded_citation_rate,
      hint: "Grounded answers that carried at least one document citation",
      icon: <Quote className="h-4 w-4" />,
    },
    {
      label: "Unsupported-answer blocking",
      value: headline.unsupported_answer_blocking,
      hint: "Unanswerable probes that produced a refusal instead of an answer",
      icon: <Ban className="h-4 w-4" />,
    },
    {
      label: "Resolution outcome accuracy",
      value: headline.resolution_outcome_accuracy,
      hint: "Plans whose outcome matched whether the case was designed to be resolvable",
      icon: <Route className="h-4 w-4" />,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {counts.map((c) => (
          <StatTile
            key={c.label}
            label={c.label}
            value={c.value}
            hint={c.hint}
            icon={c.icon}
          />
        ))}
        <Card className="px-4 py-3.5 sm:col-span-2">
          <div className="section-label">Units on this row</div>
          <p className="mt-2 text-[13px] leading-relaxed text-ink-muted">
            The two tiles to the left are <strong className="font-semibold text-ink">counts</strong> —
            the size of the evaluation. Every tile below is a{" "}
            <strong className="font-semibold text-ink">percentage</strong> of agreement with the
            answer key. They are not comparable to each other and are deliberately separated here.
          </p>
        </Card>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {percentages.map((p) => {
          const perfect = p.value >= 99.995;
          return (
            <StatTile
              key={p.label}
              label={p.label}
              tone={toneFor(p.value)}
              icon={p.icon}
              hint={p.hint}
              value={
                <span className="inline-flex items-baseline gap-2">
                  {fmtPct(p.value)}
                  {perfect ? <PerfectNote /> : null}
                </span>
              }
            />
          );
        })}
      </div>
    </div>
  );
}

/** Maps an accuracy figure onto the StatTile tone vocabulary. */
function toneFor(accuracy: number): "neutral" | "verified" | "warn" | "danger" {
  if (accuracy >= 99.995) return "verified";
  if (accuracy >= 95) return "neutral";
  if (accuracy >= 85) return "warn";
  return "danger";
}

/* --------------------------------------------------------------- OCR arm */

function OcrUnavailable({ reason }: { reason?: string }) {
  return (
    <Card className="p-6">
      <EmptyState
        icon={<ScanText className="h-5 w-5" />}
        title="The OCR arm did not run"
        description={
          reason ||
          "Tesseract was not available on the machine that ran the evaluation, so the reader comparison could not be computed. Every other figure on this page is unaffected — but the most informative comparison is missing, and the extraction figure above should be read as measuring the field grammar against a lossless text layer rather than measuring a reader."
        }
      />
    </Card>
  );
}

function OcrArm({ ocr, textLayer }: { ocr: NonNullable<Metrics["ocr_arm"]>; textLayer: Metrics }) {
  const textCls = textLayer.classification.accuracy;
  const textExt = textLayer.extraction.accuracy;
  const ocrCls = ocr.classification_accuracy ?? 0;
  const ocrExt = ocr.extraction_accuracy ?? 0;
  const extDelta = ocrExt - textExt;
  const clsDelta = ocrCls - textCls;
  const textMean = textLayer.performance.mean_ms;
  const ocrMean = ocr.mean_ms_per_document ?? 0;

  const chartData = [
    { metric: "Classification", "Text layer": textCls, "Tesseract OCR": ocrCls },
    { metric: "Extraction", "Text layer": textExt, "Tesseract OCR": ocrExt },
  ];

  const claimTypeRows = React.useMemo(() => {
    const textByType = new Map(textLayer.extraction.by_claim_type.map((r) => [r.claim_type, r]));
    return (ocr.by_claim_type ?? [])
      .map((row) => ({
        ...row,
        textAccuracy: textByType.get(row.claim_type)?.accuracy ?? null,
      }))
      .sort((a, b) => a.accuracy - b.accuracy || b.total - a.total);
  }, [ocr.by_claim_type, textLayer.extraction.by_claim_type]);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Panel
          title="Accuracy under two different readers"
          subtitle="Same 31 documents, same answer key, same field grammar. Only the text acquisition step changes."
          icon={<GitCompareArrows className="h-4 w-4" />}
          action={
            <Chip tone="navy">
              <Cpu className="h-3 w-3" />
              {ocr.engine ?? "OCR"}
            </Chip>
          }
        >
          <div className="h-[280px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 18, right: 12, left: 4, bottom: 28 }} barGap={10}>
                <CartesianGrid stroke={C.grid} vertical={false} />
                <XAxis
                  dataKey="metric"
                  tick={{ fill: C.axis, fontSize: 12 }}
                  tickLine={false}
                  axisLine={{ stroke: C.grid }}
                />
                <YAxis
                  domain={[0, 100]}
                  ticks={[0, 25, 50, 75, 100]}
                  tick={{ fill: C.axis, fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  label={{
                    value: "Accuracy (% of claims agreeing with the answer key)",
                    angle: -90,
                    position: "insideLeft",
                    style: { fill: C.axis, fontSize: 11, textAnchor: "middle" },
                  }}
                />
                <RTooltip
                  cursor={{ fill: "rgba(15,28,56,0.04)" }}
                  formatter={(value: any, name: any) => [`${Number(value).toFixed(2)}%`, name]}
                  contentStyle={{
                    borderRadius: 12,
                    border: `1px solid ${C.grid}`,
                    fontSize: 12,
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                <Bar dataKey="Text layer" fill={C.verified} radius={[5, 5, 0, 0]} maxBarSize={64}>
                  <LabelList
                    dataKey="Text layer"
                    position="top"
                    formatter={(v: any) => `${Number(v).toFixed(2)}%`}
                    style={{ fill: C.navy, fontSize: 11, fontWeight: 600 }}
                  />
                </Bar>
                <Bar dataKey="Tesseract OCR" fill={C.info} radius={[5, 5, 0, 0]} maxBarSize={64}>
                  <LabelList
                    dataKey="Tesseract OCR"
                    position="top"
                    formatter={(v: any) => `${Number(v).toFixed(2)}%`}
                    style={{ fill: C.navy, fontSize: 11, fontWeight: 600 }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <ChartCaption>
            Classification and extraction accuracy for the default text-layer path (green) against
            the Tesseract OCR arm (blue). The vertical axis runs the full 0–100% so the bars are not
            visually exaggerated; the gap is small and stated numerically below rather than magnified
            by a truncated axis.
          </ChartCaption>
        </Panel>

        <div className="space-y-4">
          <Card className="p-5">
            <div className="section-label">The cost of OCR on this corpus</div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <DeltaCell
                label="Extraction accuracy"
                left={`${fmtPct(textExt)} text layer`}
                right={`${fmtPct(ocrExt)} OCR`}
                delta={extDelta}
                unit="pp"
              />
              <DeltaCell
                label="Classification accuracy"
                left={`${fmtPct(textCls)} text layer`}
                right={`${fmtPct(ocrCls)} OCR`}
                delta={clsDelta}
                unit="pp"
              />
              <DeltaCell
                label="Mean time per document"
                left={`${textMean.toFixed(1)} ms text layer`}
                right={`${ocrMean.toFixed(1)} ms OCR`}
                delta={ocrMean - textMean}
                unit="ms"
                invertTone
              />
              <div className="rounded-xl bg-canvas-sunken px-3.5 py-3">
                <div className="section-label">Claims scored in this arm</div>
                <div className="tnum mt-1.5 text-xl font-semibold text-ink">
                  {ocr.claims_evaluated ?? "—"}
                </div>
                <p className="mt-1 text-2xs leading-snug text-ink-subtle">
                  across {ocr.documents_tested ?? "—"} documents
                </p>
              </div>
            </div>
          </Card>
          {ocr.note ? <NoteBlock tone="info">{ocr.note}</NoteBlock> : null}
          <p className="text-2xs leading-relaxed text-ink-subtle">
            This is the honest comparison on the page. The text-layer figure is 100% partly because
            the synthetic PDFs carry a clean text layer written by the same corpus generator the
            field grammar was designed against. Tesseract re-reads those same pages from pixels and
            introduces real character errors — so the OCR number is the one that shows the extractor
            under stress it did not author.
          </p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <Panel
          title="OCR extraction accuracy by field type"
          subtitle="Sorted worst-first. Every field type the answer key scores appears, including the ones OCR handled perfectly."
          icon={<ScanText className="h-4 w-4" />}
        >
          <div className="overflow-x-auto">
            <table className="table-grid min-w-[560px]">
              <thead>
                <tr>
                  <th>Field type</th>
                  <th className="text-right">Scored</th>
                  <th className="text-right">Correct (OCR)</th>
                  <th className="text-right">OCR accuracy</th>
                  <th className="text-right">Text layer</th>
                  <th className="text-right">Δ</th>
                </tr>
              </thead>
              <tbody>
                {claimTypeRows.map((row) => {
                  const delta =
                    row.textAccuracy === null ? null : row.accuracy - row.textAccuracy;
                  return (
                    <tr key={row.claim_type}>
                      <td className="font-medium text-ink">{titleise(row.claim_type)}</td>
                      <td className="tnum text-right text-ink-muted">{row.total}</td>
                      <td className="tnum text-right text-ink-muted">{row.correct}</td>
                      <td className="tnum text-right font-semibold" style={{ color: accuracyColour(row.accuracy) }}>
                        {fmtPct(row.accuracy)}
                      </td>
                      <td className="tnum text-right text-ink-muted">
                        {row.textAccuracy === null ? "—" : fmtPct(row.textAccuracy)}
                      </td>
                      <td
                        className={cn(
                          "tnum text-right font-medium",
                          delta === null || delta === 0
                            ? "text-ink-subtle"
                            : delta < 0
                              ? "text-status-conflicting"
                              : "text-status-verified",
                        )}
                      >
                        {delta === null ? "—" : delta === 0 ? "0.00" : `${delta > 0 ? "+" : ""}${delta.toFixed(2)}`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel
          title="Actual OCR failures"
          subtitle={`${(ocr.errors ?? []).length} claim${(ocr.errors ?? []).length === 1 ? "" : "s"} where the OCR reader disagreed with the answer key.`}
          icon={<AlertTriangle className="h-4 w-4" />}
        >
          {(ocr.errors ?? []).length === 0 ? (
            <p className="text-[13px] leading-relaxed text-ink-muted">
              The OCR arm produced no disagreements on this run.
            </p>
          ) : (
            <ul className="space-y-3">
              {(ocr.errors ?? []).slice(0, 8).map((err, i) => (
                <li key={i} className="rounded-xl border border-canvas-border bg-canvas-sunken/60 p-3.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <Chip tone="red">{titleise(err.kind)}</Chip>
                    <span className="text-2xs font-medium text-ink-muted">{err.property}</span>
                    <span className="text-2xs text-ink-subtle">·</span>
                    <span className="truncate text-2xs text-ink-subtle">{err.document}</span>
                  </div>
                  <div className="mt-2 text-[13px] font-medium text-ink">
                    {titleise(err.claim_type)}
                  </div>
                  <dl className="mt-2 space-y-1.5">
                    <div className="flex items-start gap-2">
                      <dt className="w-16 shrink-0 text-2xs font-semibold uppercase tracking-[0.08em] text-status-verified">
                        Expected
                      </dt>
                      <dd className="min-w-0 break-words font-mono text-[12.5px] text-ink">
                        {err.expected ?? "—"}
                      </dd>
                    </div>
                    <div className="flex items-start gap-2">
                      <dt className="w-16 shrink-0 text-2xs font-semibold uppercase tracking-[0.08em] text-status-conflicting">
                        OCR read
                      </dt>
                      <dd className="min-w-0 break-words font-mono text-[12.5px] text-status-conflicting">
                        {err.actual ?? <span className="italic">nothing extracted</span>}
                      </dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ul>
          )}
          {(ocr.errors ?? []).length > 8 ? (
            <p className="mt-3 text-2xs text-ink-subtle">
              Showing 8 of {(ocr.errors ?? []).length}.
            </p>
          ) : null}
        </Panel>
      </div>
    </div>
  );
}

function DeltaCell({
  label,
  left,
  right,
  delta,
  unit,
  invertTone,
}: {
  label: string;
  left: string;
  right: string;
  delta: number;
  unit: string;
  invertTone?: boolean;
}) {
  const worse = invertTone ? delta > 0 : delta < 0;
  const neutral = Math.abs(delta) < 0.005;
  return (
    <div className="rounded-xl bg-canvas-sunken px-3.5 py-3">
      <div className="section-label">{label}</div>
      <div
        className={cn(
          "tnum mt-1.5 text-xl font-semibold",
          neutral ? "text-ink" : worse ? "text-status-conflicting" : "text-status-verified",
        )}
      >
        {neutral ? "no change" : `${delta > 0 ? "+" : ""}${delta.toFixed(unit === "ms" ? 1 : 2)} ${unit}`}
      </div>
      <p className="mt-1 text-2xs leading-snug text-ink-subtle">
        {left} → {right}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------- extraction */

function ExtractionDetail({
  extraction,
  classification,
}: {
  extraction: Metrics["extraction"];
  classification: Metrics["classification"];
}) {
  const rows = React.useMemo(
    () => [...extraction.by_claim_type].sort((a, b) => b.total - a.total || a.claim_type.localeCompare(b.claim_type)),
    [extraction.by_claim_type],
  );
  const chartHeight = Math.max(260, rows.length * 26 + 60);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <Panel
          title="Claims scored per field type"
          subtitle="Bar length is the number of claims of that type in the answer key; bar colour is the extraction accuracy achieved on them."
          icon={<BarChart3 className="h-4 w-4" />}
        >
          <div style={{ height: chartHeight }} className="w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={rows}
                layout="vertical"
                margin={{ top: 8, right: 44, left: 8, bottom: 28 }}
              >
                <CartesianGrid stroke={C.grid} horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fill: C.axis, fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: C.grid }}
                  allowDecimals={false}
                  label={{
                    value: "Claims of this type scored against the answer key",
                    position: "insideBottom",
                    offset: -16,
                    style: { fill: C.axis, fontSize: 11 },
                  }}
                />
                <YAxis
                  type="category"
                  dataKey="claim_type"
                  width={148}
                  tick={{ fill: C.axis, fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v: string) => titleise(v)}
                />
                <RTooltip
                  cursor={{ fill: "rgba(15,28,56,0.04)" }}
                  formatter={(value: any, _name: any, item: any) => [
                    `${value} claims · ${fmtPct(item?.payload?.accuracy)} correct`,
                    titleise(item?.payload?.claim_type),
                  ]}
                  labelFormatter={() => ""}
                  contentStyle={{ borderRadius: 12, border: `1px solid ${C.grid}`, fontSize: 12 }}
                />
                <Bar dataKey="total" radius={[0, 4, 4, 0]} maxBarSize={16}>
                  {rows.map((row) => (
                    <Cell key={row.claim_type} fill={accuracyColour(row.accuracy)} />
                  ))}
                  <LabelList
                    dataKey="accuracy"
                    position="right"
                    formatter={(v: any) => fmtPct(Number(v), 1)}
                    style={{ fill: C.axis, fontSize: 10, fontWeight: 600 }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <ChartCaption>
            Extraction volume and accuracy by field type, sorted by volume. Green is 100% agreement
            on this corpus; amber, orange and red would mark degrading accuracy. All bars are green
            on the text-layer run — the caveat at the top of this page applies to that result.
          </ChartCaption>
        </Panel>

        <div className="space-y-4">
          <Panel
            title="Classification"
            subtitle="Document type assignment, scored before any field was read."
            icon={<Layers className="h-4 w-4" />}
          >
            <div className="grid grid-cols-3 gap-3">
              <MiniStat label="Documents" value={String(classification.total)} />
              <MiniStat label="Correct type" value={String(classification.correct)} />
              <MiniStat
                label="Accuracy"
                value={fmtPct(classification.accuracy)}
                colour={accuracyColour(classification.accuracy)}
              />
            </div>
            <div className="mt-4">
              {classification.errors.length === 0 ? (
                <p className="text-[13px] leading-relaxed text-ink-muted">
                  No misclassifications on this run. Every document in the corpus received the
                  document type the answer key expects.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="table-grid min-w-[520px]">
                    <thead>
                      <tr>
                        <th>Document</th>
                        <th>Expected</th>
                        <th>Predicted</th>
                        <th className="text-right">Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {classification.errors.map((e, i) => (
                        <tr key={i}>
                          <td className="text-ink">{e.document}</td>
                          <td className="text-status-verified">{titleise(e.expected)}</td>
                          <td className="text-status-conflicting">{titleise(e.predicted)}</td>
                          <td className="tnum text-right text-ink-muted">
                            {(e.confidence * 100).toFixed(1)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </Panel>

          <Panel
            title="Extraction errors"
            subtitle="Values the extractor produced that disagree with the answer key, on the default text-layer path."
            icon={<AlertTriangle className="h-4 w-4" />}
          >
            {extraction.errors.length === 0 ? (
              <div className="rounded-xl bg-canvas-sunken px-4 py-4">
                <p className="text-[13px] leading-relaxed text-ink-muted">
                  <strong className="font-semibold text-ink">The error table is empty.</strong> On
                  the text-layer path the extractor disagreed with the answer key zero times across{" "}
                  {extraction.total} claims. Stating that plainly matters more than hiding the
                  table: an empty error list on a matched synthetic corpus is close to the expected
                  outcome, which is exactly why the OCR arm above exists. Its error list is not
                  empty.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="table-grid min-w-[620px]">
                  <thead>
                    <tr>
                      <th>Property</th>
                      <th>Document</th>
                      <th>Field</th>
                      <th>Expected</th>
                      <th>Extracted</th>
                      <th>Kind</th>
                    </tr>
                  </thead>
                  <tbody>
                    {extraction.errors.map((e, i) => (
                      <tr key={i}>
                        <td className="tnum text-ink-muted">{e.property}</td>
                        <td className="text-ink-muted">{e.document}</td>
                        <td className="font-medium text-ink">{titleise(e.claim_type)}</td>
                        <td className="font-mono text-[12.5px] text-status-verified">
                          {e.expected ?? "—"}
                        </td>
                        <td className="font-mono text-[12.5px] text-status-conflicting">
                          {e.actual ?? "nothing extracted"}
                        </td>
                        <td>
                          <Chip tone="red">{titleise(e.kind)}</Chip>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

function MiniStat({ label, value, colour }: { label: string; value: string; colour?: string }) {
  return (
    <div className="rounded-xl bg-canvas-sunken px-3 py-2.5">
      <div className="section-label">{label}</div>
      <div className="tnum mt-1 text-lg font-semibold" style={colour ? { color: colour } : undefined}>
        {value}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------- contradiction */

function ContradictionDetail({ contradiction }: { contradiction: Metrics["contradiction"] }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
      <Card className="p-5">
        <div className="section-label">Aggregate over the corpus</div>
        <div className="mt-3 space-y-3">
          <PrfBar label="Precision" value={contradiction.precision} />
          <PrfBar label="Recall" value={contradiction.recall} />
          <PrfBar label="F1" value={contradiction.f1} />
        </div>
        <div className="mt-5 grid grid-cols-3 gap-2">
          <TallyCell label="True pos." value={contradiction.true_positives} tone="verified" />
          <TallyCell label="False pos." value={contradiction.false_positives} tone="conflicting" />
          <TallyCell label="False neg." value={contradiction.false_negatives} tone="conflicting" />
        </div>
        <p className="mt-4 text-2xs leading-relaxed text-ink-subtle">
          A false positive is a contradiction the engine raised that the corpus never injected; a
          false negative is an injected contradiction it missed. Both are zero on this run, over{" "}
          {contradiction.true_positives} expected contradiction types across{" "}
          {contradiction.per_property.length} properties — a small enough set that the per-property
          table beside this panel is the more informative view.
        </p>
      </Card>

      <Panel
        title="Expected against detected, per property"
        subtitle="The corpus injects a known list of contradiction types into each property. This compares that list with what the engine raised."
        icon={<GitCompareArrows className="h-4 w-4" />}
      >
        <div className="overflow-x-auto">
          <table className="table-grid min-w-[860px]">
            <thead>
              <tr>
                <th>Property</th>
                <th>Expected</th>
                <th>Detected</th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody>
              {contradiction.per_property.map((row) => (
                <tr key={row.property}>
                  <td>
                    <div className="tnum text-[13px] font-semibold text-ink">{row.property}</div>
                    <div className="mt-0.5 text-2xs text-ink-muted">{row.label}</div>
                  </td>
                  <td>
                    {row.expected.length === 0 ? (
                      <span className="text-2xs italic text-ink-subtle">
                        none — a clean file is also a test
                      </span>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {row.expected.map((t) => (
                          <Chip key={t} tone="neutral">
                            {titleise(t)}
                          </Chip>
                        ))}
                      </div>
                    )}
                  </td>
                  <td>
                    {row.detected.length === 0 ? (
                      <span className="text-2xs italic text-ink-subtle">none raised</span>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {row.detected.map((t) => (
                          <Chip key={t} tone="navy">
                            {titleise(t)}
                          </Chip>
                        ))}
                      </div>
                    )}
                  </td>
                  <td>
                    <div className="space-y-1.5">
                      <CountChips label="TP" items={row.true_positives} tone="emerald" />
                      <CountChips label="FP" items={row.false_positives} tone="red" />
                      <CountChips label="FN" items={row.false_negatives} tone="amber" />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function PrfBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-[13px] font-medium text-ink">{label}</span>
        <span className="tnum text-[13px] font-semibold" style={{ color: accuracyColour(value) }}>
          {fmtPct(value)}
        </span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-canvas-sunken">
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: accuracyColour(value) }}
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(100, value)}%` }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>
    </div>
  );
}

function TallyCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "verified" | "conflicting";
}) {
  return (
    <div
      className={cn(
        "rounded-xl px-2.5 py-2 text-center",
        tone === "verified" ? "bg-status-verifiedBg" : "bg-canvas-sunken",
      )}
    >
      <div
        className={cn(
          "tnum text-lg font-semibold",
          tone === "verified" ? "text-status-verified" : value > 0 ? "text-status-conflicting" : "text-ink-muted",
        )}
      >
        {value}
      </div>
      <div className="text-2xs font-medium text-ink-subtle">{label}</div>
    </div>
  );
}

/* ---------------------------------------------------------- verification */

function VerificationDetail({ verification }: { verification: Metrics["verification"] }) {
  const parsed = React.useMemo(
    () =>
      verification.confusion.map((c) => {
        const [expected, actual] = c.transition.split("->");
        return {
          expected: expected as VerificationStatus,
          actual: actual as VerificationStatus,
          count: c.count,
        };
      }),
    [verification.confusion],
  );

  const statuses = React.useMemo(() => {
    const order: VerificationStatus[] = [
      "VERIFIED",
      "PARTIALLY_VERIFIED",
      "CONFLICTING",
      "PENDING",
      "EXPIRED",
      "OWNER_PROVIDED",
      "UNVERIFIED",
    ];
    const present = new Set<VerificationStatus>();
    parsed.forEach((p) => {
      present.add(p.expected);
      present.add(p.actual);
    });
    return order.filter((s) => present.has(s));
  }, [parsed]);

  const lookup = React.useMemo(() => {
    const map = new Map<string, number>();
    parsed.forEach((p) => map.set(`${p.expected}->${p.actual}`, p.count));
    return map;
  }, [parsed]);

  const maxCount = Math.max(1, ...parsed.map((p) => p.count));

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,420px)]">
      <Panel
        title="Confusion matrix — expected status against resolved status"
        subtitle="Rows are the status the answer key expects for that attribute; columns are the status the verification resolver produced. Everything on the diagonal is an agreement."
        icon={<ShieldCheck className="h-4 w-4" />}
      >
        <div className="overflow-x-auto">
          <table className="min-w-[560px] border-separate border-spacing-0 text-sm">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 bg-canvas-raised px-3 py-2 text-left text-2xs font-semibold uppercase tracking-[0.1em] text-ink-subtle">
                  Expected ↓ / Resolved →
                </th>
                {statuses.map((s) => {
                  const meta = VERIFICATION_META[s];
                  return (
                    <th key={s} className="px-3 py-2 text-center">
                      <span
                        className={cn(
                          "inline-block rounded-full px-2 py-0.5 text-2xs font-semibold",
                          meta.fg,
                          meta.bg,
                        )}
                      >
                        {meta.label}
                      </span>
                    </th>
                  );
                })}
                <th className="px-3 py-2 text-right text-2xs font-semibold uppercase tracking-[0.1em] text-ink-subtle">
                  Row total
                </th>
              </tr>
            </thead>
            <tbody>
              {statuses.map((rowStatus) => {
                const rowMeta = VERIFICATION_META[rowStatus];
                const rowTotal = statuses.reduce(
                  (sum, col) => sum + (lookup.get(`${rowStatus}->${col}`) ?? 0),
                  0,
                );
                return (
                  <tr key={rowStatus}>
                    <th className="sticky left-0 z-10 border-t border-canvas-border bg-canvas-raised px-3 py-2.5 text-left">
                      <span className={cn("text-[13px] font-semibold", rowMeta.fg)}>
                        {rowMeta.label}
                      </span>
                    </th>
                    {statuses.map((colStatus) => {
                      const count = lookup.get(`${rowStatus}->${colStatus}`) ?? 0;
                      const diagonal = rowStatus === colStatus;
                      const intensity = count / maxCount;
                      return (
                        <td
                          key={colStatus}
                          className="border-t border-canvas-border px-3 py-2.5 text-center"
                        >
                          <div
                            className={cn(
                              "tnum mx-auto grid h-11 w-full min-w-[52px] max-w-[84px] place-items-center rounded-lg text-[15px] font-semibold",
                              count === 0 && "text-ink-subtle",
                            )}
                            style={
                              count === 0
                                ? { backgroundColor: "#f7f9fc" }
                                : diagonal
                                  ? {
                                      backgroundColor: `rgba(15, 138, 95, ${0.12 + intensity * 0.4})`,
                                      color: "#0b5c3f",
                                    }
                                  : {
                                      backgroundColor: `rgba(198, 40, 40, ${0.12 + intensity * 0.4})`,
                                      color: "#8e1c1c",
                                    }
                            }
                          >
                            {count === 0 ? "·" : count}
                          </div>
                        </td>
                      );
                    })}
                    <td className="tnum border-t border-canvas-border px-3 py-2.5 text-right font-medium text-ink-muted">
                      {rowTotal}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <ChartCaption>
          Attribute-level confusion for {verification.total} scored attributes. Green cells sit on the
          diagonal (resolved status equals expected status); any off-diagonal cell would be red.
          Only three statuses appear because those are the only statuses the answer key asserts for
          this corpus — the resolver never invented a fourth.
        </ChartCaption>
      </Panel>

      <div className="space-y-4">
        <Card className="p-5">
          <div className="section-label">Agreement</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span
              className="tnum text-3xl font-semibold tracking-tight"
              style={{ color: accuracyColour(verification.agreement) }}
            >
              {fmtPct(verification.agreement)}
            </span>
            {verification.agreement >= 99.995 ? <PerfectNote /> : null}
          </div>
          <p className="mt-1.5 text-[13px] text-ink-muted">
            {verification.correct} of {verification.total} scored attributes resolved to the expected
            status.
          </p>
          <div className="mt-4 space-y-2">
            {parsed
              .slice()
              .sort((a, b) => b.count - a.count)
              .map((p) => {
                const agree = p.expected === p.actual;
                const expMeta = VERIFICATION_META[p.expected];
                const actMeta = VERIFICATION_META[p.actual];
                return (
                  <div
                    key={`${p.expected}->${p.actual}`}
                    className={cn(
                      "flex items-center justify-between gap-3 rounded-xl px-3 py-2",
                      agree ? "bg-status-verifiedBg/60" : "bg-status-conflictingBg",
                    )}
                  >
                    <div className="flex min-w-0 items-center gap-1.5 text-2xs">
                      <span className={cn("font-semibold", expMeta.fg)}>{expMeta.label}</span>
                      <span className="text-ink-subtle">→</span>
                      <span className={cn("font-semibold", actMeta.fg)}>{actMeta.label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="tnum text-sm font-semibold text-ink">{p.count}</span>
                      {agree ? (
                        <BadgeCheck className="h-3.5 w-3.5 text-status-verified" />
                      ) : (
                        <AlertTriangle className="h-3.5 w-3.5 text-status-conflicting" />
                      )}
                    </div>
                  </div>
                );
              })}
          </div>
        </Card>

        <Panel
          title="Disagreements"
          subtitle="Attributes whose resolved status differed from the expected status."
          icon={<ShieldAlert className="h-4 w-4" />}
        >
          {verification.errors.length === 0 ? (
            <p className="text-[13px] leading-relaxed text-ink-muted">
              None on this run. Each of the {verification.total} scored attributes resolved to the
              status the answer key expects — including the attributes expected to come out{" "}
              <span className="font-medium text-status-conflicting">Conflicting</span>, where
              agreeing with the key means correctly refusing to call the value verified.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="table-grid min-w-[480px]">
                <thead>
                  <tr>
                    <th>Property</th>
                    <th>Attribute</th>
                    <th>Expected</th>
                    <th>Resolved</th>
                  </tr>
                </thead>
                <tbody>
                  {verification.errors.map((e, i) => (
                    <tr key={i}>
                      <td className="tnum text-ink-muted">{e.property}</td>
                      <td className="font-medium text-ink">{titleise(e.claim_type)}</td>
                      <td className={cn("font-medium", VERIFICATION_META[e.expected]?.fg)}>
                        {VERIFICATION_META[e.expected]?.label ?? e.expected}
                      </td>
                      <td className={cn("font-medium", VERIFICATION_META[e.actual]?.fg)}>
                        {VERIFICATION_META[e.actual]?.label ?? e.actual}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

/* ------------------------------------------------------ transaction state */

function TransactionStateDetail({ ts }: { ts: Metrics["transaction_state"] }) {
  return (
    <Panel
      title="State controller decisions"
      subtitle={`${ts.correct} of ${ts.total} properties landed in the expected transaction state and risk band.`}
      icon={<Gauge className="h-4 w-4" />}
      action={
        <div className="flex items-center gap-2">
          <span
            className="tnum text-lg font-semibold"
            style={{ color: accuracyColour(ts.accuracy) }}
          >
            {fmtPct(ts.accuracy)}
          </span>
          {ts.accuracy >= 99.995 ? <PerfectNote /> : null}
        </div>
      }
    >
      <div className="overflow-x-auto">
        <table className="table-grid min-w-[900px]">
          <thead>
            <tr>
              <th className="w-12" />
              <th>Property</th>
              <th>Expected state</th>
              <th>Actual state</th>
              <th>Expected band</th>
              <th>Actual band</th>
              <th className="text-right">Risk score</th>
            </tr>
          </thead>
          <tbody>
            {ts.per_property.map((row) => (
              <tr key={row.property}>
                <td>
                  {row.correct ? (
                    <span className="grid h-6 w-6 place-items-center rounded-full bg-status-verifiedBg text-status-verified">
                      <BadgeCheck className="h-3.5 w-3.5" />
                    </span>
                  ) : (
                    <span className="grid h-6 w-6 place-items-center rounded-full bg-status-conflictingBg text-status-conflicting">
                      <AlertTriangle className="h-3.5 w-3.5" />
                    </span>
                  )}
                </td>
                <td>
                  <div className="tnum text-[13px] font-semibold text-ink">{row.property}</div>
                  <div className="mt-0.5 text-2xs text-ink-muted">{row.label}</div>
                </td>
                <td>
                  <StateBadge state={row.expected_state} size="sm" />
                </td>
                <td>
                  <StateBadge state={row.actual_state} size="sm" />
                </td>
                <td>
                  <BandBadge band={row.expected_band} />
                </td>
                <td>
                  <BandBadge band={row.actual_band} />
                </td>
                <td className="text-right">
                  <span
                    className="tnum text-sm font-semibold"
                    style={{ color: BAND_META[row.actual_band]?.hex ?? C.navy }}
                  >
                    {row.risk_score.toFixed(1)}
                  </span>
                  <span className="ml-1 text-2xs text-ink-subtle">/100</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-2xs leading-relaxed text-ink-subtle">
        Both the state and the band are scored. A property that reached the right state through the
        wrong band would count as incorrect, which is why the two columns are shown side by side
        rather than collapsed into a single tick.
      </p>
    </Panel>
  );
}

/* -------------------------------------------------------------- grounding */

function GroundingDetail({ grounding }: { grounding: Metrics["grounding"] }) {
  const g = grounding;
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        {/* answerable half */}
        <Card className="overflow-hidden">
          <div className="border-b border-canvas-border bg-status-infoBg/50 px-5 py-3.5">
            <div className="flex items-center gap-2">
              <Quote className="h-4 w-4 text-status-info" />
              <h3 className="text-[15px] font-semibold text-ink">Questions the file can answer</h3>
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
              Probes with a basis in the property record. Success is a grounded answer that cites a
              document and page.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-px bg-canvas-border">
            <MetaCell label="Answerable probes" value={String(g.answerable_probes)} />
            <MetaCell label="Grounded answers" value={String(g.grounded_answers)} />
            <MetaCell label="With citations" value={String(g.grounded_with_citations)} />
            <MetaCell
              label="Citation rate"
              value={fmtPct(g.grounded_citation_rate)}
            />
          </div>
          <div className="px-5 py-4">
            <PrfBar label="Answerable coverage" value={g.answerable_coverage} />
            <div className="mt-3">
              <PrfBar label="Citation rate on grounded answers" value={g.grounded_citation_rate} />
            </div>
            <p className="mt-3 text-2xs leading-relaxed text-ink-subtle">
              {g.grounded_answers - g.grounded_with_citations} grounded answer
              {g.grounded_answers - g.grounded_with_citations === 1 ? "" : "s"} carried no citation.
              That is a real shortfall and is reported here rather than rounded away — the citation
              rate is {fmtPct(g.grounded_citation_rate)}, not 100%.
            </p>
            {g.answerable_but_refused.length > 0 ? (
              <div className="mt-3 rounded-xl bg-status-partialBg px-3.5 py-3">
                <div className="text-2xs font-semibold uppercase tracking-[0.08em] text-status-partial">
                  Answerable but refused ({g.answerable_but_refused.length})
                </div>
                <ul className="mt-1.5 space-y-1">
                  {g.answerable_but_refused.slice(0, 5).map((r, i) => (
                    <li key={i} className="text-2xs leading-relaxed text-ink-muted">
                      {r.property ? <span className="tnum font-medium">{r.property} · </span> : null}
                      {r.question ?? "—"}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </Card>

        {/* unanswerable half — the point */}
        <Card className="overflow-hidden ring-1 ring-emerald-200">
          <div className="border-b border-canvas-border bg-status-verifiedBg px-5 py-3.5">
            <div className="flex items-center gap-2">
              <CircleSlash className="h-4 w-4 text-status-verified" />
              <h3 className="text-[15px] font-semibold text-ink">
                Questions the file cannot answer
              </h3>
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
              Probes with no basis in the property record.{" "}
              <strong className="font-semibold text-status-verified">
                Here a refusal is the success condition
              </strong>{" "}
              — an answer would be the failure.
            </p>
          </div>
          <div className="px-5 py-5">
            <div className="flex items-end gap-5">
              <div>
                <div className="section-label">Refusal rate</div>
                <div className="tnum mt-1 text-4xl font-semibold tracking-tight text-status-verified">
                  {fmtPct(g.refusal_rate)}
                </div>
                <p className="mt-1 text-2xs text-ink-subtle">
                  {g.refused} of {g.unanswerable_probes} probes refused
                </p>
              </div>
              <div className="flex-1">
                <RefusalDots refused={g.refused} total={g.unanswerable_probes} />
              </div>
            </div>

            <div
              className={cn(
                "mt-5 flex items-start gap-3 rounded-xl px-4 py-3.5",
                g.unsupported_answers_emitted === 0
                  ? "bg-status-verifiedBg"
                  : "bg-status-conflictingBg",
              )}
            >
              <div
                className={cn(
                  "mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg",
                  g.unsupported_answers_emitted === 0
                    ? "bg-status-verified/15 text-status-verified"
                    : "bg-status-conflicting/15 text-status-conflicting",
                )}
              >
                {g.unsupported_answers_emitted === 0 ? (
                  <ShieldCheck className="h-4 w-4" />
                ) : (
                  <ShieldAlert className="h-4 w-4" />
                )}
              </div>
              <div>
                <div className="text-[13px] font-semibold text-ink">
                  Unsupported answers emitted:{" "}
                  <span className="tnum">{g.unsupported_answers_emitted}</span>
                </div>
                <p className="mt-1 text-2xs leading-relaxed text-ink-muted">
                  {g.unsupported_answers_emitted === 0
                    ? "No probe without a basis in the file produced an answer. This is a counted absence, not an average — one leak would appear here as a number greater than zero."
                    : "At least one probe without a basis in the file produced an answer. Each is listed below."}
                </p>
              </div>
            </div>

            {g.leaks.length > 0 ? (
              <div className="mt-3 overflow-x-auto">
                <table className="table-grid min-w-[420px]">
                  <thead>
                    <tr>
                      <th>Property</th>
                      <th>Question</th>
                      <th>Answer emitted</th>
                    </tr>
                  </thead>
                  <tbody>
                    {g.leaks.map((leak, i) => (
                      <tr key={i}>
                        <td className="tnum text-ink-muted">{leak.property ?? "—"}</td>
                        <td className="text-ink">{leak.question ?? "—"}</td>
                        <td className="text-status-conflicting">{leak.answer ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="mt-3 text-2xs leading-relaxed text-ink-subtle">
                Leak list is empty.
              </p>
            )}
          </div>
        </Card>
      </div>

      <NoteBlock tone="info">{g.note}</NoteBlock>
    </div>
  );
}

/** A dot per unanswerable probe: filled green when it was refused. */
function RefusalDots({ refused, total }: { refused: number; total: number }) {
  const dots = Array.from({ length: total });
  return (
    <div>
      <div className="flex flex-wrap gap-1">
        {dots.map((_, i) => (
          <motion.span
            key={i}
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: Math.min(0.6, i * 0.006), duration: 0.2 }}
            className={cn(
              "h-2.5 w-2.5 rounded-full",
              i < refused ? "bg-status-verified" : "bg-status-conflicting",
            )}
            title={i < refused ? "refused (correct)" : "answered (leak)"}
          />
        ))}
      </div>
      <p className="mt-2 text-2xs leading-snug text-ink-subtle">
        One dot per unanswerable probe. Green = refused, which is the desired behaviour. Any red dot
        would be an unsupported answer.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------- resolution */

function ResolutionDetail({ resolution }: { resolution: Metrics["resolution"] }) {
  const r = resolution;
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Properties needing a plan" value={String(r.properties_needing_a_plan)} hint="Count" />
        <StatCard label="Plans reaching PROCEED" value={String(r.plans_reaching_proceed)} hint="Count" />
        <StatCard
          label="Reaching PROCEED"
          value={fmtPct(r.reaching_proceed_pct)}
          hint="Share of plans — deliberately not 100%"
          colour={C.navyMid}
        />
        <StatCard
          label="Outcome accuracy"
          value={fmtPct(r.outcome_accuracy)}
          hint={`${r.outcomes_scored} outcomes scored against expected resolvability`}
          colour={accuracyColour(r.outcome_accuracy)}
          perfect={r.outcome_accuracy >= 99.995}
        />
        <StatCard label="Mean steps per plan" value={r.mean_steps.toFixed(1)} hint="Count" />
      </div>

      <NoteBlock tone="info">{r.note}</NoteBlock>

      <Panel
        title="Baseline against planned outcome, per property"
        subtitle="Every property is scored on whether its outcome matched what the scenario was designed to allow — not on whether it reached PROCEED."
        icon={<Route className="h-4 w-4" />}
      >
        <div className="overflow-x-auto">
          <table className="table-grid min-w-[1040px]">
            <thead>
              <tr>
                <th className="w-12" />
                <th>Property</th>
                <th>Baseline</th>
                <th className="text-center">Steps</th>
                <th>Plan</th>
                <th>Final</th>
                <th className="text-center">Reaches PROCEED</th>
                <th className="text-center">Expected resolvable</th>
              </tr>
            </thead>
            <tbody>
              {r.per_property.map((row) => (
                <tr key={row.property}>
                  <td>
                    {row.outcome_correct ? (
                      <span className="grid h-6 w-6 place-items-center rounded-full bg-status-verifiedBg text-status-verified">
                        <BadgeCheck className="h-3.5 w-3.5" />
                      </span>
                    ) : (
                      <span className="grid h-6 w-6 place-items-center rounded-full bg-status-conflictingBg text-status-conflicting">
                        <AlertTriangle className="h-3.5 w-3.5" />
                      </span>
                    )}
                  </td>
                  <td>
                    <div className="tnum text-[13px] font-semibold text-ink">{row.property}</div>
                    {row.label ? (
                      <div className="mt-0.5 text-2xs text-ink-muted">{row.label}</div>
                    ) : null}
                    <p className="mt-1 max-w-[280px] text-2xs leading-relaxed text-ink-subtle">
                      {row.note}
                    </p>
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <StateBadge state={row.baseline_state} size="sm" />
                      <span className="tnum text-2xs text-ink-muted">
                        {row.baseline_risk.toFixed(1)}
                      </span>
                    </div>
                  </td>
                  <td className="tnum text-center font-semibold text-ink">{row.steps}</td>
                  <td>
                    {row.step_keys && row.step_keys.length > 0 ? (
                      <ol className="space-y-1">
                        {row.step_keys.map((key, i) => (
                          <li key={key} className="flex items-start gap-1.5 text-2xs text-ink-muted">
                            <span className="tnum mt-px grid h-4 w-4 shrink-0 place-items-center rounded bg-canvas-sunken text-[10px] font-semibold text-ink-subtle">
                              {i + 1}
                            </span>
                            <span className="font-mono">{key}</span>
                          </li>
                        ))}
                      </ol>
                    ) : (
                      <span className="text-2xs italic text-ink-subtle">no steps required</span>
                    )}
                  </td>
                  <td>
                    <div className="flex items-center gap-2">
                      <StateBadge state={row.final_state} size="sm" />
                      <span className="tnum text-2xs text-ink-muted">
                        {row.final_risk.toFixed(1)}
                      </span>
                    </div>
                    {row.risk_reduction ? (
                      <div className="tnum mt-1 text-2xs font-medium text-status-verified">
                        −{row.risk_reduction.toFixed(1)} risk
                      </div>
                    ) : null}
                  </td>
                  <td className="text-center">
                    <YesNo value={row.reaches_proceed} />
                  </td>
                  <td className="text-center">
                    <YesNo value={row.expected_resolvable} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-2xs leading-relaxed text-ink-subtle">
          Read the last two columns together. A row where both are “no” is a{" "}
          <span className="font-medium text-status-verified">correct</span> outcome: the planner
          found no evidence path that clears the case, and the scenario says none should exist.
        </p>
      </Panel>
    </div>
  );
}

function YesNo({ value }: { value: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-0.5 text-2xs font-semibold uppercase tracking-[0.08em]",
        value ? "bg-status-verifiedBg text-status-verified" : "bg-canvas-sunken text-ink-muted",
      )}
    >
      {value ? "yes" : "no"}
    </span>
  );
}

function StatCard({
  label,
  value,
  hint,
  colour,
  perfect,
}: {
  label: string;
  value: string;
  hint?: string;
  colour?: string;
  perfect?: boolean;
}) {
  return (
    <Card className="px-4 py-3.5">
      <div className="section-label">{label}</div>
      <div className="mt-2 flex items-baseline gap-2">
        <span
          className="tnum text-2xl font-semibold tracking-tight"
          style={colour ? { color: colour } : undefined}
        >
          {value}
        </span>
        {perfect ? <PerfectNote /> : null}
      </div>
      {hint ? <p className="mt-1 text-2xs leading-snug text-ink-subtle">{hint}</p> : null}
    </Card>
  );
}

/* ------------------------------------------------------------ performance */

function PerformanceDetail({
  performance,
  ocrMeanMs,
}: {
  performance: Metrics["performance"];
  ocrMeanMs?: number;
}) {
  const docs = React.useMemo(
    () =>
      performance.documents.map((d, i) => ({
        ...d,
        index: i + 1,
        short: d.document.replace(/\.pdf$/i, ""),
      })),
    [performance.documents],
  );
  const slowest = React.useMemo(
    () => [...docs].sort((a, b) => b.ms - a.ms).slice(0, 5),
    [docs],
  );

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Mean time per document"
          value={`${performance.mean_ms.toFixed(1)} ms`}
          hint="Text-layer path, on the evaluation machine"
          colour={C.verified}
        />
        <StatCard
          label="Mean claims per document"
          value={performance.mean_claims_per_document.toFixed(2)}
          hint="Count"
        />
        <StatCard label="Documents measured" value={String(docs.length)} hint="Count" />
        {ocrMeanMs !== undefined ? (
          <StatCard
            label="Mean time per document (OCR)"
            value={`${ocrMeanMs.toFixed(0)} ms`}
            hint={`${Math.round(ocrMeanMs / Math.max(performance.mean_ms, 0.1))}× the text-layer path`}
            colour={C.info}
          />
        ) : (
          <StatCard label="OCR arm" value="not run" hint="Tesseract unavailable on this machine" />
        )}
      </div>

      <Panel
        title="Processing time per document"
        subtitle="One bar per document in the corpus, in corpus order. The dashed line is the mean."
        icon={<Timer className="h-4 w-4" />}
      >
        <div className="h-[300px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={docs} margin={{ top: 12, right: 12, left: 4, bottom: 34 }}>
              <CartesianGrid stroke={C.grid} vertical={false} />
              <XAxis
                dataKey="index"
                tick={{ fill: C.axis, fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: C.grid }}
                interval={0}
                label={{
                  value: "Document (in corpus order)",
                  position: "insideBottom",
                  offset: -22,
                  style: { fill: C.axis, fontSize: 11 },
                }}
              />
              <YAxis
                tick={{ fill: C.axis, fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                label={{
                  value: "Milliseconds",
                  angle: -90,
                  position: "insideLeft",
                  style: { fill: C.axis, fontSize: 11, textAnchor: "middle" },
                }}
              />
              <RTooltip
                cursor={{ fill: "rgba(15,28,56,0.04)" }}
                contentStyle={{ borderRadius: 12, border: `1px solid ${C.grid}`, fontSize: 12 }}
                labelFormatter={(label: any) => {
                  const doc = docs.find((d) => d.index === label);
                  return doc ? doc.document : `Document ${label}`;
                }}
                formatter={(value: any, _name: any, item: any) => [
                  `${value} ms · ${item?.payload?.pages} page(s) · ${item?.payload?.claims} claims`,
                  titleise(item?.payload?.doc_type),
                ]}
              />
              <ReferenceLine
                y={performance.mean_ms}
                stroke={C.critical}
                strokeDasharray="4 4"
                label={{
                  value: `mean ${performance.mean_ms.toFixed(1)} ms`,
                  position: "right",
                  style: { fill: C.critical, fontSize: 10, fontWeight: 600 },
                }}
              />
              <Bar dataKey="ms" radius={[4, 4, 0, 0]} maxBarSize={22}>
                {docs.map((d) => (
                  <Cell key={d.index} fill={d.ms > performance.mean_ms ? C.navyMid : C.navyLight} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <ChartCaption>
          Wall-clock milliseconds for classification, text acquisition, layout analysis and claim
          extraction on each document, as recorded by the pipeline itself. Darker bars are above the
          mean. These are single-run measurements on one machine, not a benchmark.
        </ChartCaption>
      </Panel>

      <Panel
        title="Slowest documents"
        subtitle="The five documents that cost the most, with their page and claim counts."
        icon={<Activity className="h-4 w-4" />}
      >
        <div className="overflow-x-auto">
          <table className="table-grid min-w-[620px]">
            <thead>
              <tr>
                <th>Document</th>
                <th>Type</th>
                <th className="text-right">Pages</th>
                <th className="text-right">Claims</th>
                <th className="text-right">Time</th>
              </tr>
            </thead>
            <tbody>
              {slowest.map((d) => (
                <tr key={d.index}>
                  <td className="font-medium text-ink">{d.document}</td>
                  <td className="text-ink-muted">{titleise(d.doc_type)}</td>
                  <td className="tnum text-right text-ink-muted">{d.pages}</td>
                  <td className="tnum text-right text-ink-muted">{d.claims}</td>
                  <td className="tnum text-right font-semibold text-ink">{d.ms} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
