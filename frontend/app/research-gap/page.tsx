"use client";

/**
 * Research Gap — literature positioning.
 *
 * The argument of this page is a table. Five mature research areas, what each one
 * already does well, where each one stops, and what this platform adds at that exact
 * point. The novelty claim is deliberately modest and is rendered in the backend's own
 * wording: these capabilities are individually mature and are *rarely combined*. No
 * claim is made that any single one of them is unprecedented, and the page says so.
 */

import { motion } from "framer-motion";
import {
  ArrowRight,
  BookMarked,
  Braces,
  Building2,
  Fingerprint,
  GitCompareArrows,
  Layers3,
  Link2,
  Quote,
  Scale,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Target,
  Workflow,
} from "lucide-react";
import React from "react";

import { useApi } from "@/components/hooks";
import {
  Card,
  CardHeader,
  Chip,
  Disclaimer,
  ErrorState,
  LoadingCard,
  PrototypeBadge,
  SectionHeading,
  Skeleton,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import { cn } from "@/lib/format";

/* -------------------------------------------------------------------- types */

type GapRow = {
  area: string;
  representative_works: string;
  existing_capability: string;
  limitation: string;
  contribution: string;
  implemented_in: string[];
};

type Pillar = { pillar: string; detail: string };

type ResearchGap = {
  statement: string;
  novelty_wording: string;
  rows: GapRow[];
  combination: Pillar[];
  disclaimer: string;
};

/* ------------------------------------------------------------------- icons */

const AREA_ICONS: { match: RegExp; icon: React.ReactNode }[] = [
  { match: /extraction/i, icon: <ScanSearch className="h-4 w-4" /> },
  { match: /identity|blockchain|registr/i, icon: <Fingerprint className="h-4 w-4" /> },
  { match: /graph|valuation/i, icon: <Building2 className="h-4 w-4" /> },
  { match: /forgery|fraud/i, icon: <ShieldCheck className="h-4 w-4" /> },
  { match: /grounded|privacy|ai/i, icon: <Sparkles className="h-4 w-4" /> },
];

function areaIcon(area: string): React.ReactNode {
  return AREA_ICONS.find((a) => a.match.test(area))?.icon ?? <BookMarked className="h-4 w-4" />;
}

const PILLAR_ICONS: React.ReactNode[] = [
  <Link2 key="0" className="h-4 w-4" />,
  <ShieldCheck key="1" className="h-4 w-4" />,
  <Workflow key="2" className="h-4 w-4" />,
  <Fingerprint key="3" className="h-4 w-4" />,
  <Scale key="4" className="h-4 w-4" />,
  <Target key="5" className="h-4 w-4" />,
];

/* -------------------------------------------------------------------- page */

export default function ResearchGapPage() {
  const { data, error, loading, refetch } = useApi<ResearchGap>(() => endpoints.researchGap(), []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="max-w-4xl">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="mt-4 h-8 w-96" />
          <Skeleton className="mt-4 h-4 w-full" />
          <Skeleton className="mt-2 h-4 w-11/12" />
          <Skeleton className="mt-2 h-4 w-9/12" />
        </div>
        <LoadingCard rows={8} title="Loading literature positioning" />
        <LoadingCard rows={6} />
      </div>
    );
  }

  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!data) return null;

  return (
    <div className="space-y-10 pb-4">
      {/* ------------------------------------------------------ statement */}
      <header className="max-w-5xl">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <PrototypeBadge />
          <span className="inline-flex items-center gap-1.5 rounded-full bg-navy-50 px-2.5 py-1 text-2xs font-semibold uppercase tracking-[0.1em] text-navy-700 ring-1 ring-navy-200">
            <GitCompareArrows className="h-3 w-3" />
            Literature positioning
          </span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Research gap</h1>
        <motion.p
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="mt-4 text-[17px] leading-[1.75] text-ink"
        >
          {data.statement}
        </motion.p>
      </header>

      {/* ----------------------------------------------------- the table */}
      <section>
        <SectionHeading
          eyebrow="The argument"
          title="Where each research area stops, and what is added there"
          description="Five mature areas, read left to right: what already works, the point at which it stops being sufficient for land-title decisions, and the mechanism this platform puts at that point."
        />
        <GapTable rows={data.rows} />
        <GapCards rows={data.rows} />
      </section>

      {/* ------------------------------------------------- the combination */}
      <section>
        <SectionHeading
          eyebrow="What is combined here"
          title="Six pillars, one mechanism"
          description="None of these six is individually novel. The contribution being claimed is that they operate as a single mechanism over the same claim records — a status decided by one pillar is the input another pillar gates on."
        />
        <CombinationComposition pillars={data.combination} />
      </section>

      {/* -------------------------------------------------- novelty wording */}
      <section>
        <SectionHeading
          eyebrow="Claim discipline"
          title="How the novelty is claimed"
          description="The wording below is the wording the system returns. It is careful on purpose, and the care is the point."
        />
        <NoveltyCallout wording={data.novelty_wording} />
      </section>

      <Disclaimer text={data.disclaimer} />
    </div>
  );
}

/* ------------------------------------------------------------ the table */

function GapTable({ rows }: { rows: GapRow[] }) {
  return (
    <Card className="hidden overflow-hidden lg:block">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1180px] border-separate border-spacing-0 text-sm">
          <thead>
            <tr>
              <th className="w-[19%] border-b border-canvas-border bg-canvas-sunken px-5 py-3.5 text-left text-2xs font-semibold uppercase tracking-[0.1em] text-ink-muted">
                Research area
              </th>
              <th className="w-[19%] border-b border-canvas-border bg-canvas-sunken px-5 py-3.5 text-left text-2xs font-semibold uppercase tracking-[0.1em] text-ink-muted">
                Existing capability
              </th>
              <th className="w-[22%] border-b border-l border-canvas-border bg-status-conflictingBg/60 px-5 py-3.5 text-left text-2xs font-semibold uppercase tracking-[0.1em] text-status-conflicting">
                Limitation
              </th>
              <th className="w-[26%] border-b border-l border-canvas-border bg-status-verifiedBg/70 px-5 py-3.5 text-left text-2xs font-semibold uppercase tracking-[0.1em] text-status-verified">
                LandTrust contribution
              </th>
              <th className="w-[14%] border-b border-l border-canvas-border bg-canvas-sunken px-5 py-3.5 text-left text-2xs font-semibold uppercase tracking-[0.1em] text-ink-muted">
                Implemented in
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <motion.tr
                key={row.area}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06, duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                className="align-top"
              >
                <td className="border-b border-canvas-border px-5 py-5">
                  <div className="flex items-start gap-2.5">
                    <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-navy-50 text-navy-700">
                      {areaIcon(row.area)}
                    </span>
                    <div className="min-w-0">
                      <div className="text-[14px] font-semibold leading-snug text-ink">
                        {row.area}
                      </div>
                      <p className="mt-2 text-2xs leading-relaxed text-ink-subtle">
                        <span className="font-semibold uppercase tracking-[0.08em]">
                          Representative work ·{" "}
                        </span>
                        {row.representative_works}
                      </p>
                    </div>
                  </div>
                </td>
                <td className="border-b border-canvas-border px-5 py-5">
                  <p className="text-[13.5px] leading-[1.7] text-ink-muted">
                    {row.existing_capability}
                  </p>
                </td>
                <td className="border-b border-l border-canvas-border bg-status-conflictingBg/25 px-5 py-5">
                  <p className="text-[13.5px] leading-[1.7] text-ink">
                    <span className="mr-1.5 inline-block h-1.5 w-1.5 -translate-y-px rounded-full bg-status-conflicting align-middle" />
                    {row.limitation}
                  </p>
                </td>
                <td className="border-b border-l border-canvas-border bg-status-verifiedBg/35 px-5 py-5">
                  <p className="text-[13.5px] font-medium leading-[1.7] text-ink">
                    {row.contribution}
                  </p>
                </td>
                <td className="border-b border-l border-canvas-border px-5 py-5">
                  <div className="flex flex-wrap gap-1.5">
                    {row.implemented_in.map((mod) => (
                      <Chip key={mod} tone="navy">
                        {mod}
                      </Chip>
                    ))}
                  </div>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-canvas-border bg-canvas-sunken/60 px-5 py-3">
        <LegendDot colour="bg-status-conflicting" label="Limitation — where the existing work stops" />
        <LegendDot colour="bg-status-verified" label="Contribution — what this platform puts at that point" />
        <span className="text-2xs text-ink-subtle">
          Bracketed numbers are the reference indices from the Review-1 proposal bibliography.
        </span>
      </div>
    </Card>
  );
}

/** Below `lg` the five-column table stops being readable, so the same rows become cards. */
function GapCards({ rows }: { rows: GapRow[] }) {
  return (
    <div className="space-y-4 lg:hidden">
      {rows.map((row) => (
        <Card key={row.area} className="overflow-hidden">
          <CardHeader
            title={row.area}
            subtitle={row.representative_works}
            icon={areaIcon(row.area)}
          />
          <div className="space-y-4 p-5">
            <div>
              <div className="section-label">Existing capability</div>
              <p className="mt-1.5 text-[13.5px] leading-[1.7] text-ink-muted">
                {row.existing_capability}
              </p>
            </div>
            <div className="rounded-xl bg-status-conflictingBg/40 px-4 py-3">
              <div className="text-2xs font-semibold uppercase tracking-[0.1em] text-status-conflicting">
                Limitation
              </div>
              <p className="mt-1.5 text-[13.5px] leading-[1.7] text-ink">{row.limitation}</p>
            </div>
            <div className="rounded-xl bg-status-verifiedBg/60 px-4 py-3">
              <div className="text-2xs font-semibold uppercase tracking-[0.1em] text-status-verified">
                LandTrust contribution
              </div>
              <p className="mt-1.5 text-[13.5px] font-medium leading-[1.7] text-ink">
                {row.contribution}
              </p>
            </div>
            <div>
              <div className="section-label mb-1.5">Implemented in</div>
              <div className="flex flex-wrap gap-1.5">
                {row.implemented_in.map((mod) => (
                  <Chip key={mod} tone="navy">
                    {mod}
                  </Chip>
                ))}
              </div>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

function LegendDot({ colour, label }: { colour: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-2xs text-ink-muted">
      <span className={cn("h-1.5 w-1.5 rounded-full", colour)} />
      {label}
    </span>
  );
}

/* ------------------------------------------------------- the combination */

/**
 * The six pillars are drawn converging on one statement rather than listed, because
 * the claim being made is about the convergence and not about any single pillar.
 */
function CombinationComposition({ pillars }: { pillars: Pillar[] }) {
  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {pillars.map((p, i) => (
          <motion.div
            key={p.pillar}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ delay: i * 0.07, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            className="relative"
          >
            <Card className="h-full p-5">
              <div className="flex items-start gap-3">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-navy-fade text-white shadow-card">
                  {PILLAR_ICONS[i % PILLAR_ICONS.length]}
                </span>
                <div className="min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span className="tnum text-2xs font-semibold text-ink-subtle">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <h3 className="text-[15px] font-semibold leading-tight text-ink">{p.pillar}</h3>
                  </div>
                  <p className="mt-2 text-[13.5px] leading-[1.7] text-ink-muted">{p.detail}</p>
                </div>
              </div>
            </Card>
            {/* connective tissue: every card points at the statement below */}
            <div className="pointer-events-none absolute inset-x-0 -bottom-4 hidden justify-center xl:flex">
              <ArrowRight className="h-3.5 w-3.5 rotate-90 text-canvas-borderStrong" />
            </div>
          </motion.div>
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="relative overflow-hidden rounded-2xl bg-navy-fade px-6 py-7 text-white shadow-raised"
      >
        <div className="absolute inset-0 bg-hero-grid [background-size:26px_26px]" />
        <div className="relative flex flex-wrap items-start gap-4">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/10 text-white ring-1 ring-white/20">
            <Layers3 className="h-5 w-5" />
          </span>
          <div className="min-w-0 max-w-3xl">
            <div className="text-2xs font-semibold uppercase tracking-[0.14em] text-white/50">
              The claimed contribution
            </div>
            <p className="mt-2 text-[15.5px] leading-[1.75] text-white/95">
              Six pillars operating over one set of claim records. A claim&rsquo;s provenance decides
              its verification status; that status decides what may be disclosed; consent decides
              who may see it; the ownership graph decides whether a superseded value is history or a
              contradiction; the risk ledger turns all of it into a transaction state; and the
              planner searches backwards from that state for the smallest set of documents that
              would clear it. Remove any one pillar and the chain stops being a mechanism.
            </p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

/* ----------------------------------------------------- novelty statement */

function NoveltyCallout({ wording }: { wording: string }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
      <Card className="overflow-hidden border-status-info/25">
        <div className="flex items-center gap-2 border-b border-canvas-border bg-status-infoBg px-5 py-3">
          <Quote className="h-4 w-4 text-status-info" />
          <h3 className="text-[13px] font-semibold uppercase tracking-[0.1em] text-status-info">
            How the novelty is claimed
          </h3>
        </div>
        <blockquote className="px-6 py-6">
          <p className="text-[17px] font-medium leading-[1.75] text-ink">
            <span className="mr-1 text-2xl leading-none text-status-info">&ldquo;</span>
            {wording}
            <span className="ml-1 text-2xl leading-none text-status-info">&rdquo;</span>
          </p>
          <footer className="mt-4 text-2xs uppercase tracking-[0.1em] text-ink-subtle">
            Returned verbatim by <code className="font-mono normal-case">GET /api/research/gap</code>
          </footer>
        </blockquote>
      </Card>

      <Card className="p-5">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-canvas-sunken text-ink-muted">
            <Braces className="h-4 w-4" />
          </span>
          <div>
            <h3 className="text-[15px] font-semibold text-ink">What is not being claimed</h3>
            <ul className="mt-3 space-y-2.5 text-[13px] leading-relaxed text-ink-muted">
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-ink-subtle" />
                <span>
                  No claim is made that any of these six capabilities is individually
                  unprecedented. Each has a mature literature of its own, cited in the table above.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-ink-subtle" />
                <span>
                  The wording is <em>&ldquo;rarely combine&hellip; in one framework&rdquo;</em> — a
                  statement about how often the combination appears, not an assertion that it has
                  never been attempted.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-ink-subtle" />
                <span>
                  Nothing here is a claim about legal validity. The platform reports agreement
                  between the documents uploaded to it; it does not certify title.
                </span>
              </li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
}
