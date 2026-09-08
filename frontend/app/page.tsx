"use client";

import { motion } from "framer-motion";
import {
  ArrowRight,
  FileSearch,
  GitBranch,
  Layers3,
  Lock,
  MessagesSquare,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import Link from "next/link";
import React from "react";

import { RoleSwitcher } from "@/components/app-shell";
import { useApi } from "@/components/hooks";
import { Card, PrototypeBadge, StatusBadge } from "@/components/ui";
import { endpoints } from "@/lib/api";
import { DISCLAIMER, WORKFLOW_STEPS } from "@/lib/domain";
import { cn } from "@/lib/format";

export default function LandingPage() {
  const { data: dashboard } = useApi<any>(() => endpoints.dashboard(), []);
  const cards = dashboard?.cards;

  return (
    <div className="min-h-screen bg-canvas">
      <TopNav />
      <Hero cards={cards} />
      <ClaimDemo />
      <Workflow_ />
      <Pillars />
      <Positioning />
      <Footer />
    </div>
  );
}

/* ------------------------------------------------------------------ header */

function TopNav() {
  return (
    <header className="absolute inset-x-0 top-0 z-30">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2.5">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-white/10 text-white ring-1 ring-white/15">
            <ShieldCheck className="h-4.5 w-4.5" strokeWidth={2.2} />
          </div>
          <div className="leading-tight text-white">
            <div className="text-[15px] font-semibold tracking-tight">LandTrust</div>
            <div className="text-2xs font-medium uppercase tracking-[0.16em] text-white/55">
              Connect
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/research-gap"
            className="hidden text-[13px] font-medium text-white/70 transition hover:text-white sm:block"
          >
            Research gap
          </Link>
          <Link
            href="/architecture"
            className="hidden text-[13px] font-medium text-white/70 transition hover:text-white sm:block"
          >
            Architecture
          </Link>
          <div className="[&_button]:border-white/20 [&_button]:bg-white/10 [&_button]:text-white hover:[&_button]:bg-white/15">
            <RoleSwitcher />
          </div>
        </div>
      </div>
    </header>
  );
}

/* -------------------------------------------------------------------- hero */

function Hero({ cards }: { cards?: any }) {
  return (
    <section className="relative overflow-hidden bg-navy-fade pb-20 pt-32 text-white">
      <div className="pointer-events-none absolute inset-0 bg-hero-grid [background-size:56px_56px]" />
      <div
        className="pointer-events-none absolute -right-40 -top-40 h-[520px] w-[520px] rounded-full opacity-40 blur-3xl"
        style={{ background: "radial-gradient(circle, #1fa678 0%, transparent 66%)" }}
      />
      <div
        className="pointer-events-none absolute -bottom-56 -left-32 h-[460px] w-[460px] rounded-full opacity-25 blur-3xl"
        style={{ background: "radial-gradient(circle, #48649d 0%, transparent 68%)" }}
      />

      <div className="relative mx-auto max-w-7xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="max-w-3xl"
        >
          <div className="mb-6 flex flex-wrap items-center gap-2.5">
            <PrototypeBadge className="!bg-white/10 !text-emerald-200 !ring-white/15" />
            <span className="rounded-full bg-white/8 px-2.5 py-1 text-2xs font-medium uppercase tracking-[0.1em] text-white/60 ring-1 ring-white/12">
              Review-2 · B.Tech research project
            </span>
          </div>

          <h1 className="text-[2.75rem] font-semibold leading-[1.08] tracking-tight sm:text-6xl">
            Trust every claim.
            <br />
            <span className="text-emerald-300">Verify every transaction.</span>
          </h1>

          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-white/70">
            AI-powered, evidence-gated land intelligence for safer and more transparent property
            transactions.
          </p>

          <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-white/55">
            LandTrust Connect does not merely extract information from property documents. It binds
            every claim to the evidence behind it, reasons across documents and ownership history,
            controls what may be disclosed and to whom, continuously re-evaluates transaction risk,
            stops unsafe progression, and computes the minimum evidence needed to resolve what it
            found.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link
              href="/dashboard"
              className="group inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-navy-900 shadow-raised transition hover:bg-emerald-50"
            >
              Explore demo
              <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </Link>
            <Link
              href="/properties"
              className="inline-flex items-center gap-2 rounded-xl bg-white/10 px-5 py-3 text-sm font-semibold text-white ring-1 ring-white/20 transition hover:bg-white/15"
            >
              <ScanSearch className="h-4 w-4" />
              Verify a property
            </Link>
            <Link
              href="/presentation"
              className="inline-flex items-center gap-2 px-2 py-3 text-sm font-medium text-white/60 transition hover:text-white"
            >
              Presentation mode
            </Link>
          </div>
        </motion.div>

        {cards ? (
          <motion.dl
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.16 }}
            className="mt-16 grid max-w-4xl grid-cols-2 gap-px overflow-hidden rounded-2xl bg-white/10 sm:grid-cols-4"
          >
            {[
              ["Properties", cards.total_properties],
              ["Documents processed", cards.documents_processed],
              ["Claims extracted", cards.claims_extracted],
              ["Contradictions found", cards.contradictions_found],
            ].map(([label, value]) => (
              <div key={label as string} className="bg-navy-950/40 px-5 py-4 backdrop-blur">
                <dd className="tnum text-2xl font-semibold tracking-tight text-white">
                  {value as number}
                </dd>
                <dt className="mt-0.5 text-2xs font-medium uppercase tracking-[0.1em] text-white/45">
                  {label as string}
                </dt>
              </div>
            ))}
          </motion.dl>
        ) : null}
      </div>
    </section>
  );
}

/* --------------------------------------------------- the contribution, shown */

const DEMO_ROWS = [
  {
    label: "Survey Number",
    value: "142/3A",
    status: "VERIFIED" as const,
    note: "Sale Deed, Encumbrance Certificate and Survey Record agree exactly.",
    sources: 3,
  },
  {
    label: "Property Area",
    value: "1800 sq.ft",
    status: "CONFLICTING" as const,
    note: "The Encumbrance Certificate records 1650 sq.ft — a 150 sq.ft disagreement.",
    sources: 2,
  },
  {
    label: "Owner Name",
    value: "Priya Sharma",
    status: "PARTIALLY_VERIFIED" as const,
    note: "One source writes 'Priya S. Sharma'. Close enough to rule out a different person; not exact enough to certify.",
    sources: 3,
  },
  {
    label: "Mortgage Status",
    value: "Active — ₹18,00,000",
    status: "VERIFIED" as const,
    note: "The encumbrance authority of record reports a subsisting charge.",
    sources: 2,
  },
  {
    label: "Encumbrance (no certificate)",
    value: "Not evidenced",
    status: "PENDING" as const,
    note: "No document asserts this. Absence of evidence is recorded, not treated as absence of risk.",
    sources: 0,
  },
];

function ClaimDemo() {
  return (
    <section className="border-b border-canvas-border bg-canvas-raised py-20">
      <div className="mx-auto max-w-7xl px-6">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-center">
          <div>
            <div className="section-label mb-3">The central idea</div>
            <h2 className="text-3xl font-semibold leading-tight tracking-tight text-ink">
              A claim is not verified because it appeared in a document.
            </h2>
            <p className="mt-4 text-[15px] leading-relaxed text-ink-muted">
              Appearing once proves only that someone wrote it down. On this platform every land
              detail carries its own evidence — the document, the page, the region of that page, the
              extraction confidence, what corroborates it and what contradicts it — and a{" "}
              <em>separate</em> resolver decides its status from that evidence set.
            </p>
            <p className="mt-4 text-[15px] leading-relaxed text-ink-muted">
              The extractor is not permitted to mark anything verified. That separation is enforced
              in code, and it is why a single uploaded deed can never make a buyer see a green tick.
            </p>
            <Link
              href="/properties"
              className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-navy-900 transition hover:gap-3"
            >
              See it on a real file
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>

          <Card className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-canvas-border bg-canvas-sunken px-5 py-3">
              <span className="text-[13px] font-semibold text-ink">Claim–Evidence Matrix</span>
              <span className="text-2xs text-ink-subtle">illustrative extract</span>
            </div>
            <ul className="divide-y divide-canvas-border">
              {DEMO_ROWS.map((row, i) => (
                <motion.li
                  key={row.label}
                  initial={{ opacity: 0, x: -8 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true, margin: "-60px" }}
                  transition={{ duration: 0.35, delay: i * 0.07 }}
                  className="px-5 py-3.5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-2xs font-medium uppercase tracking-wide text-ink-subtle">
                        {row.label}
                      </div>
                      <div
                        className={cn(
                          "mt-0.5 text-sm font-medium",
                          row.status === "PENDING" ? "text-ink-subtle italic" : "text-ink",
                        )}
                      >
                        {row.value}
                      </div>
                    </div>
                    <StatusBadge status={row.status} size="sm" withTooltip={false} />
                  </div>
                  <p className="mt-1.5 text-2xs leading-relaxed text-ink-muted">
                    {row.note}
                    {row.sources > 0 ? (
                      <span className="ml-1 text-ink-subtle">
                        · {row.sources} source{row.sources > 1 ? "s" : ""}
                      </span>
                    ) : null}
                  </p>
                </motion.li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- workflow */

function Workflow_() {
  return (
    <section className="bg-canvas py-20">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mb-10 max-w-2xl">
          <div className="section-label mb-3">How it works</div>
          <h2 className="text-3xl font-semibold tracking-tight text-ink">
            Eight stages, each one traceable
          </h2>
          <p className="mt-3 text-[15px] leading-relaxed text-ink-muted">
            Every stage writes evidence the next one can cite, and the whole chain re-runs whenever a
            document is added — so what a buyer sees is always the current consequence of the current
            evidence, never a cached verdict.
          </p>
        </div>

        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {WORKFLOW_STEPS.map((step, i) => (
            <motion.li
              key={step.key}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.4, delay: i * 0.05 }}
              className="group relative"
            >
              <Card className="h-full p-4 transition group-hover:shadow-raised">
                <div className="flex items-center gap-2.5">
                  <span className="tnum grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-navy-900 text-2xs font-bold text-white">
                    {i + 1}
                  </span>
                  <span className="text-[13px] font-semibold text-ink">{step.label}</span>
                </div>
                <p className="mt-2 text-2xs leading-relaxed text-ink-muted">{step.blurb}</p>
              </Card>
              {i < WORKFLOW_STEPS.length - 1 ? (
                <div className="pointer-events-none absolute -right-1.5 top-1/2 hidden h-px w-3 bg-canvas-borderStrong lg:block" />
              ) : null}
            </motion.li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- pillars */

const PILLARS = [
  {
    icon: FileSearch,
    title: "Claim-level provenance",
    body: "Every value resolves to a document, a page and a highlighted region of that page — including values recovered by geometry when a file's reading order has been disturbed.",
  },
  {
    icon: GitBranch,
    title: "Temporal ownership reasoning",
    body: "Successive deeds and a discharged mortgage form a chain of title, not a pile of contradictions. The graph carries validity intervals, so the system knows when a fact stopped being true.",
  },
  {
    icon: Lock,
    title: "Evidence-gated disclosure",
    body: "Status is decided by evidence; visibility is decided by consent. The two are independent, so a buyer always learns whether a fact is supported — even when they may not see its value.",
  },
  {
    icon: MessagesSquare,
    title: "Consent-based interaction",
    body: "A property-scoped relay with itemised, time-limited, revocable grants. Identity documents are refused outright, with or without consent.",
  },
  {
    icon: Workflow,
    title: "Dynamic transaction state",
    body: "Risk recomputes on every evidence change, and the state controller actually blocks progression rather than displaying a warning next to an enabled button.",
  },
  {
    icon: Sparkles,
    title: "Minimum-evidence resolution",
    body: "A counterfactual search over the risk model for the smallest set of documents that would clear the hold — with the predicted score for each step, computed rather than estimated.",
  },
];

function Pillars() {
  return (
    <section className="border-y border-canvas-border bg-canvas-raised py-20">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mb-10 max-w-2xl">
          <div className="section-label mb-3">What is combined here</div>
          <h2 className="text-3xl font-semibold tracking-tight text-ink">
            Six mechanisms, one framework
          </h2>
          <p className="mt-3 text-[15px] leading-relaxed text-ink-muted">
            Each of these has been studied on its own. The contribution of this project is that they
            operate together on one claim store, so a disclosure decision and a transaction decision
            rest on the same evidence.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {PILLARS.map((p, i) => {
            const Icon = p.icon;
            return (
              <motion.div
                key={p.title}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.4, delay: i * 0.05 }}
              >
                <Card className="h-full p-5">
                  <div className="grid h-9 w-9 place-items-center rounded-xl bg-navy-50 text-navy-700">
                    <Icon className="h-4.5 w-4.5" strokeWidth={1.9} />
                  </div>
                  <h3 className="mt-3.5 text-[15px] font-semibold text-ink">{p.title}</h3>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted">{p.body}</p>
                </Card>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------- positioning */

function Positioning() {
  return (
    <section className="bg-canvas py-20">
      <div className="mx-auto max-w-7xl px-6">
        <div className="grid gap-10 lg:grid-cols-2">
          <Card className="p-7">
            <div className="section-label mb-3">What this is</div>
            <p className="text-[15px] leading-relaxed text-ink">
              A privacy-first, evidence-gated land transaction{" "}
              <strong className="font-semibold">decision-support platform</strong>. It reasons about
              the documents you give it and tells you, with citations, what they do and do not
              establish.
            </p>
            <div className="mt-6 space-y-2.5">
              {[
                "Reads real uploaded PDFs — text layer by default, Tesseract OCR for scans",
                "Explains every risk point by the rule and evidence that produced it",
                "Refuses to answer when the file holds no supporting record",
                "Runs entirely offline: no API keys, no external services required",
              ].map((line) => (
                <div key={line} className="flex items-start gap-2.5">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-status-verified" />
                  <span className="text-[13px] leading-relaxed text-ink-muted">{line}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card className="border-status-partial/25 bg-status-partialBg/40 p-7">
            <div className="section-label mb-3 !text-status-partial">What this is not</div>
            <p className="text-[15px] leading-relaxed text-ink">
              It is <strong className="font-semibold">not</strong> an official record and does not
              pretend to be one. Where the prototype cannot verify something, it says so rather than
              simulating success.
            </p>
            <ul className="mt-6 space-y-2.5">
              {[
                "Not a government land registry or a registrar's confirmation",
                "Not a legal-title certification, and not a substitute for an advocate",
                "Not an identity-verification service — identity documents are never disclosed",
                "Not a payment system — no transaction on this platform moves money",
              ].map((line) => (
                <li key={line} className="flex items-start gap-2.5">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-status-partial" />
                  <span className="text-[13px] leading-relaxed text-ink-muted">{line}</span>
                </li>
              ))}
            </ul>
            <p className="mt-6 text-2xs leading-relaxed text-ink-subtle">
              Every property, person, survey number and institution in this demonstration is
              synthetic. No real land record is reproduced.
            </p>
          </Card>
        </div>

        <div className="mt-10 flex flex-wrap gap-3">
          <Link
            href="/research"
            className="inline-flex items-center gap-2 rounded-xl bg-navy-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-navy-800"
          >
            <Layers3 className="h-4 w-4" />
            Measured results
          </Link>
          <Link
            href="/research-gap"
            className="inline-flex items-center gap-2 rounded-xl bg-canvas-raised px-5 py-3 text-sm font-semibold text-ink ring-1 ring-canvas-borderStrong transition hover:bg-canvas-sunken"
          >
            Research gap
          </Link>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-canvas-border bg-canvas-raised py-10">
      <div className="mx-auto max-w-7xl px-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-navy-fade text-white">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <div>
              <div className="text-[13px] font-semibold text-ink">LandTrust Connect</div>
              <div className="text-2xs text-ink-subtle">
                An AI-based evidence-gated land ownership verification, secure owner interaction and
                autonomous transaction risk resolution system
              </div>
            </div>
          </div>
          <PrototypeBadge />
        </div>
        <p className="mt-6 max-w-4xl text-2xs leading-relaxed text-ink-subtle">{DISCLAIMER}</p>
      </div>
    </footer>
  );
}
