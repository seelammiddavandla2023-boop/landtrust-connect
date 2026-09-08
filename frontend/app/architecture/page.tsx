"use client";

/**
 * System Architecture.
 *
 * Two things this page has to do. First, show the pipeline as a pipeline — evidence
 * enters at the top and a transaction decision falls out of the bottom, through five
 * layers that are drawn as a stack rather than five unrelated lists. Second, be honest
 * about what is not built: every component carries a status, and REVIEW_3 means the
 * interface exists but the capability is deliberately out of scope. The platform does
 * not fake government verification, and the architecture says where it stops.
 */

import { motion } from "framer-motion";
import {
  ArrowDown,
  Ban,
  Boxes,
  CheckCircle2,
  ChevronRight,
  CircleDashed,
  FileSearch,
  FlaskConical,
  Gavel,
  Layers3,
  type LucideIcon,
  Network,
  ScanText,
  ShieldCheck,
  Signal,
  Sparkles,
  Workflow,
} from "lucide-react";
import React from "react";

import { useApi } from "@/components/hooks";
import {
  Card,
  Chip,
  Disclaimer,
  ErrorState,
  LoadingCard,
  PrototypeBadge,
  SectionHeading,
  Skeleton,
  Tooltip,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import { cn } from "@/lib/format";

/* -------------------------------------------------------------------- types */

type ComponentStatus = "WORKING" | "PROTOTYPE" | "REVIEW_3";

type ArchComponent = { name: string; module: string; status: ComponentStatus };

type Layer = {
  key: string;
  name: string;
  purpose: string;
  components: ArchComponent[];
};

type Architecture = {
  layers: Layer[];
  flow: string[];
  out_of_scope: string[];
  disclaimer: string;
};

/* ------------------------------------------------------------- status meta */

const STATUS_META: Record<
  ComponentStatus,
  { label: string; fg: string; bg: string; ring: string; dot: string; meaning: string }
> = {
  WORKING: {
    label: "Working",
    fg: "text-status-verified",
    bg: "bg-status-verifiedBg",
    ring: "ring-status-verified/20",
    dot: "bg-status-verified",
    meaning:
      "Implemented and exercised by the evaluation run. The module named on the card is the code that does it.",
  },
  PROTOTYPE: {
    label: "Prototype",
    fg: "text-status-partial",
    bg: "bg-status-partialBg",
    ring: "ring-status-partial/20",
    dot: "bg-status-partial",
    meaning:
      "Present and functional for the demonstration, but simplified — it stands in for a production implementation rather than being one.",
  },
  REVIEW_3: {
    label: "Review-3",
    fg: "text-ink-muted",
    bg: "bg-canvas-sunken",
    ring: "ring-canvas-borderStrong",
    dot: "bg-ink-subtle",
    meaning:
      "Deliberately not implemented. The interface exists so the component has somewhere to attach, but nothing simulates the capability — an empty seat, not a stub that pretends.",
  },
};

const LAYER_ICONS: Record<string, LucideIcon> = {
  INPUT_IDENTITY: ShieldCheck,
  DOCUMENT_INTELLIGENCE: ScanText,
  EVIDENCE_REASONING: Network,
  INTERACTION: Sparkles,
  CONTROL: Gavel,
};

const FLOW_ICONS: LucideIcon[] = [
  FileSearch,
  ScanText,
  ShieldCheck,
  Network,
  Boxes,
  Signal,
  Workflow,
  Gavel,
];

/* -------------------------------------------------------------------- page */

export default function ArchitecturePage() {
  const { data, error, loading, refetch } = useApi<Architecture>(
    () => endpoints.architecture(),
    [],
  );

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="max-w-3xl">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="mt-4 h-8 w-80" />
          <Skeleton className="mt-4 h-4 w-full" />
        </div>
        <Card className="p-6">
          <div className="flex flex-wrap gap-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-40" />
            ))}
          </div>
        </Card>
        <LoadingCard rows={6} title="Loading layers" />
        <LoadingCard rows={6} />
      </div>
    );
  }

  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!data) return null;

  const counts = data.layers
    .flatMap((l) => l.components)
    .reduce<Record<ComponentStatus, number>>(
      (acc, c) => {
        acc[c.status] = (acc[c.status] ?? 0) + 1;
        return acc;
      },
      { WORKING: 0, PROTOTYPE: 0, REVIEW_3: 0 },
    );

  return (
    <div className="space-y-9 pb-4">
      {/* --------------------------------------------------------- header */}
      <header className="max-w-4xl">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <PrototypeBadge />
          <span className="inline-flex items-center gap-1.5 rounded-full bg-navy-50 px-2.5 py-1 text-2xs font-semibold uppercase tracking-[0.1em] text-navy-700 ring-1 ring-navy-200">
            <Layers3 className="h-3 w-3" />
            {data.layers.length} layers · {counts.WORKING + counts.PROTOTYPE + counts.REVIEW_3} components
          </span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">System architecture</h1>
        <p className="mt-3 text-sm leading-relaxed text-ink-muted">
          Evidence enters at the top and a transaction decision falls out of the bottom. Each layer
          consumes only what the layer above produced, so a value shown to a buyer can always be
          traced back through verification, extraction and the page region it came from. The module
          path on every card is a real file in this repository.
        </p>
      </header>

      {/* ----------------------------------------------------------- flow */}
      <section>
        <SectionHeading
          eyebrow="Processing pipeline"
          title="What happens to a document, end to end"
          description="Eight stages. The first four are automatic on upload; the last four run again every time the evidence set changes."
        />
        <FlowPipeline flow={data.flow} />
      </section>

      {/* --------------------------------------------------------- legend */}
      <StatusLegend counts={counts} />

      {/* --------------------------------------------------------- layers */}
      <section>
        <SectionHeading
          eyebrow="Layered design"
          title="Five layers, top to bottom"
          description="Read downward. Nothing in a lower layer reads raw documents; it reads the claim records the layer above produced."
        />
        <LayerStack layers={data.layers} />
      </section>

      {/* -------------------------------------------------- out of scope */}
      <section>
        <SectionHeading
          eyebrow="Scope discipline"
          title="Not implemented — Review-3"
          description="Six capabilities the platform has interfaces for and deliberately does not simulate."
        />
        <OutOfScope items={data.out_of_scope} />
      </section>

      <Disclaimer text={data.disclaimer} />
    </div>
  );
}

/* --------------------------------------------------------------- pipeline */

function FlowPipeline({ flow }: { flow: string[] }) {
  return (
    <Card className="overflow-hidden">
      <div className="relative overflow-x-auto bg-navy-fade px-5 py-6">
        <div className="absolute inset-0 bg-hero-grid [background-size:26px_26px]" />
        <div className="relative flex flex-wrap items-stretch gap-y-4">
          {flow.map((step, i) => {
            const Icon = FLOW_ICONS[i % FLOW_ICONS.length];
            const last = i === flow.length - 1;
            return (
              <React.Fragment key={step}>
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{
                    delay: i * 0.09,
                    duration: 0.4,
                    ease: [0.22, 1, 0.36, 1],
                  }}
                  className={cn(
                    "flex min-w-[136px] flex-1 flex-col justify-between rounded-xl px-3.5 py-3 ring-1 backdrop-blur",
                    last
                      ? "bg-emerald-400/15 ring-emerald-300/40"
                      : "bg-white/[0.07] ring-white/15",
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "grid h-6 w-6 shrink-0 place-items-center rounded-md text-[10px] font-bold",
                        last ? "bg-emerald-300 text-navy-950" : "bg-white/15 text-white/85",
                      )}
                    >
                      {i + 1}
                    </span>
                    <Icon
                      className={cn("h-3.5 w-3.5", last ? "text-emerald-200" : "text-white/60")}
                    />
                  </div>
                  <div
                    className={cn(
                      "mt-2.5 text-[13px] font-semibold leading-snug",
                      last ? "text-emerald-100" : "text-white/95",
                    )}
                  >
                    {step}
                  </div>
                </motion.div>
                {!last ? (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.09 + 0.14, duration: 0.3 }}
                    className="flex w-6 shrink-0 items-center justify-center"
                    aria-hidden
                  >
                    <ChevronRight className="h-4 w-4 text-white/30" />
                  </motion.div>
                ) : null}
              </React.Fragment>
            );
          })}
        </div>
      </div>
      <p className="border-t border-canvas-border px-5 py-3 text-2xs leading-relaxed text-ink-muted">
        Every stage writes an audit event. Stages 6 to 8 re-run whenever a document is added or a
        resolution step is applied, which is why the risk score and transaction state on a property
        move during the demonstration rather than being fixed at upload time.
      </p>
    </Card>
  );
}

/* ----------------------------------------------------------------- legend */

function StatusLegend({ counts }: { counts: Record<ComponentStatus, number> }) {
  const order: ComponentStatus[] = ["WORKING", "PROTOTYPE", "REVIEW_3"];
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="section-label">Component status legend</div>
          <p className="mt-1.5 max-w-2xl text-[13px] leading-relaxed text-ink-muted">
            Every component below carries one of three statuses. The distinction between the second
            and the third is the one that matters to a reviewer: a prototype is simplified, a
            Review-3 component is absent on purpose.
          </p>
        </div>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {order.map((status) => {
          const meta = STATUS_META[status];
          return (
            <div
              key={status}
              className={cn("rounded-xl px-4 py-3 ring-1", meta.bg, meta.ring)}
            >
              <div className="flex items-center justify-between gap-2">
                <span className={cn("inline-flex items-center gap-1.5 text-[13px] font-semibold", meta.fg)}>
                  <span className={cn("h-1.5 w-1.5 rounded-full", meta.dot)} />
                  {meta.label}
                </span>
                <span className={cn("tnum text-sm font-semibold", meta.fg)}>{counts[status]}</span>
              </div>
              <p className="mt-2 text-2xs leading-relaxed text-ink-muted">{meta.meaning}</p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------ layer stack */

function LayerStack({ layers }: { layers: Layer[] }) {
  return (
    <div className="relative">
      {/* the spine: a single line the whole stack hangs off */}
      <div
        className="pointer-events-none absolute bottom-8 left-[19px] top-8 hidden w-px lg:block"
        style={{
          background:
            "linear-gradient(to bottom, #c5d1e6 0%, #48649d 35%, #48649d 70%, #0f8a5f 100%)",
        }}
        aria-hidden
      />
      <ol className="space-y-4">
        {layers.map((layer, i) => (
          <LayerBand key={layer.key} layer={layer} index={i} last={i === layers.length - 1} />
        ))}
      </ol>
    </div>
  );
}

function LayerBand({ layer, index, last }: { layer: Layer; index: number; last: boolean }) {
  const Icon = LAYER_ICONS[layer.key] ?? Layers3;
  return (
    <li className="relative lg:pl-[52px]">
      {/* spine node */}
      <span
        className="absolute left-0 top-[26px] hidden h-[18px] w-[18px] items-center justify-center rounded-full bg-canvas ring-2 ring-navy-300 lg:flex"
        aria-hidden
      >
        <span className="h-2 w-2 rounded-full bg-navy-600" />
      </span>

      <motion.div
        initial={{ opacity: 0, y: 14 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ delay: index * 0.05, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      >
        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-canvas-border bg-canvas-sunken/60 px-5 py-4">
            <div className="flex min-w-0 items-start gap-3">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-navy-900 text-white">
                <Icon className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <div className="flex items-baseline gap-2">
                  <span className="tnum text-2xs font-semibold uppercase tracking-[0.12em] text-ink-subtle">
                    Layer {index + 1}
                  </span>
                  <h3 className="text-[15px] font-semibold leading-tight text-ink">{layer.name}</h3>
                </div>
                <p className="mt-1.5 max-w-3xl text-[13px] leading-relaxed text-ink-muted">
                  {layer.purpose}
                </p>
              </div>
            </div>
            <code className="rounded-md bg-canvas-raised px-2 py-1 font-mono text-2xs text-ink-subtle ring-1 ring-canvas-border">
              {layer.key}
            </code>
          </div>

          <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-3">
            {layer.components.map((component) => (
              <ComponentCard key={`${layer.key}:${component.name}`} component={component} />
            ))}
          </div>
        </Card>
      </motion.div>

      {/* connective tissue between bands */}
      {!last ? (
        <div className="flex justify-center py-1" aria-hidden>
          <motion.span
            initial={{ opacity: 0, y: -4 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.3 }}
            className="inline-flex items-center gap-1.5 rounded-full bg-canvas-sunken px-2.5 py-1 text-2xs font-medium text-ink-subtle"
          >
            <ArrowDown className="h-3 w-3" />
            feeds the layer below
          </motion.span>
        </div>
      ) : null}
    </li>
  );
}

function ComponentCard({ component }: { component: ArchComponent }) {
  const meta = STATUS_META[component.status] ?? STATUS_META.PROTOTYPE;
  const absent = component.status === "REVIEW_3";
  return (
    <div
      className={cn(
        "flex h-full flex-col justify-between rounded-xl border px-3.5 py-3 transition",
        absent
          ? "border-dashed border-canvas-borderStrong bg-canvas-sunken/40"
          : "border-canvas-border bg-canvas-raised hover:shadow-card",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <h4
          className={cn(
            "text-[13.5px] font-semibold leading-snug",
            absent ? "text-ink-muted" : "text-ink",
          )}
        >
          {component.name}
        </h4>
        <Tooltip content={meta.meaning}>
          <span
            className={cn(
              "inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-2xs font-semibold uppercase tracking-[0.06em] ring-1",
              meta.fg,
              meta.bg,
              meta.ring,
            )}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", meta.dot)} />
            {meta.label}
          </span>
        </Tooltip>
      </div>
      <div className="mt-2.5">
        {component.module && component.module !== "—" ? (
          <code className="block break-all font-mono text-[11.5px] leading-relaxed text-ink-subtle">
            {component.module}
          </code>
        ) : (
          <span className="inline-flex items-center gap-1.5 text-2xs italic text-ink-subtle">
            <CircleDashed className="h-3 w-3" />
            no module — nothing implements this
          </span>
        )}
      </div>
    </div>
  );
}

/* ----------------------------------------------------------- out of scope */

function OutOfScope({ items }: { items: string[] }) {
  return (
    <Card className="overflow-hidden">
      <div className="flex items-start gap-3.5 border-b border-canvas-border bg-canvas-sunken/60 px-5 py-4">
        <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-canvas-raised text-ink-muted ring-1 ring-canvas-borderStrong">
          <Ban className="h-4 w-4" />
        </span>
        <div className="max-w-4xl">
          <h3 className="text-[15px] font-semibold text-ink">
            Deliberately out of scope for this review
          </h3>
          <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted">
            Each of these has a defined place in the architecture and an interface it would attach
            to. None of them is simulated. A mocked registry lookup that returns
            &ldquo;verified&rdquo; would make the demonstration look stronger and the research
            weaker: it would put a status on screen that no evidence produced, which is the exact
            failure mode this platform exists to argue against. The gap is left visible instead.
          </p>
        </div>
      </div>
      <ul className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((item, i) => (
          <motion.li
            key={item}
            initial={{ opacity: 0, y: 8 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.05, duration: 0.3 }}
            className="flex items-start gap-2.5 rounded-xl border border-dashed border-canvas-borderStrong bg-canvas-sunken/40 px-3.5 py-3"
          >
            <CircleDashed className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-subtle" />
            <span className="text-[13px] leading-relaxed text-ink-muted">{item}</span>
          </motion.li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-2 border-t border-canvas-border px-5 py-3.5">
        <Chip tone="neutral">
          <FlaskConical className="h-3 w-3" />
          Review-3 scope
        </Chip>
        <span className="text-2xs leading-relaxed text-ink-muted">
          What <em>is</em> built is measured — see{" "}
          <span className="font-medium text-ink">Research Results</span> for the evaluation output
          against the synthetic corpus.
        </span>
        <span className="ml-auto inline-flex items-center gap-1.5 text-2xs text-ink-subtle">
          <CheckCircle2 className="h-3 w-3 text-status-verified" />
          interfaces present, capability absent
        </span>
      </div>
    </Card>
  );
}
