"use client";

/**
 * Document viewer — the claim-level provenance surface.
 *
 * Left: the real stored PDF, with an evidence overlay drawn from each claim's
 * normalised `source_region`. Because an embedded PDF viewer decides its own page
 * margins and zoom, that overlay is an approximation — so a text view sits one click
 * away that highlights the matched span inside the page's extracted text. That view
 * is exact, and it is the one to trust when the geometry looks off.
 *
 * Right: every claim extracted from this document. Selecting one drives the left
 * pane: page, highlight and provenance caption all follow the selection.
 */

import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Crosshair,
  FileText,
  Info,
  Layers,
  Lock,
  ScanLine,
  ShieldAlert,
} from "lucide-react";
import React from "react";

import { useApi } from "@/components/hooks";
import {
  Card,
  CardHeader,
  Chip,
  ConfidenceBar,
  EmptyState,
  ErrorState,
  LoadingCard,
  SeverityBadge,
  StatusBadge,
  Tooltip,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import type { Severity, VerificationStatus } from "@/lib/domain";
import { cn, pct, titleise } from "@/lib/format";

/* ------------------------------------------------------------------- types */

type SourceRegion = {
  x: number;
  y: number;
  w: number;
  h: number;
  label?: string | null;
  recovered_by?: string | null;
};

type ViewerClaim = {
  id: string;
  claim_type: string;
  label: string;
  value: string;
  masked?: boolean;
  mask_reason?: string | null;
  normalized_value?: string | null;
  source_page?: number | null;
  source_span?: string | null;
  source_region?: SourceRegion | null;
  confidence: number;
  verification_status: VerificationStatus;
  status_explanation?: string | null;
  extraction_method?: string | null;
};

type ViewerPage = {
  page_number: number;
  text: string;
  width: number;
  height: number;
  ocr_confidence: number | null;
  layout_blocks?: { x: number; y: number; w: number; h: number; kind?: string }[] | null;
};

type IntegrityFlag = {
  code: string;
  label: string;
  detail: string;
  severity: Severity;
  page?: number | null;
};

type ViewerDocument = {
  id: string;
  filename: string;
  doc_type: string;
  doc_type_label: string;
  classification_confidence: number;
  page_count: number;
  extraction_mode: string;
  ocr_engine: string;
  quality_score: number | null;
  integrity_flags: IntegrityFlag[];
  pages: ViewerPage[];
};

type ViewerPayload = { document: ViewerDocument; claims: ViewerClaim[] };

/* --------------------------------------------------------------- utilities */

/** Whitespace-tolerant needle → the page text keeps newlines where a span has spaces. */
function buildNeedle(needle: string): RegExp | null {
  const trimmed = needle.trim();
  if (trimmed.length < 2) return null;
  const escaped = trimmed.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+");
  try {
    return new RegExp(escaped, "i");
  } catch {
    return null;
  }
}

/**
 * Locate a claim inside a page's text.
 *
 * Preference order matters: the literal value is the tightest and most honest match;
 * a masked value will never appear in the text, so the extracted span is the fallback
 * that still points at the right part of the page.
 */
function locateClaim(
  text: string,
  claim: ViewerClaim,
): { start: number; end: number; via: string } | null {
  const candidates: { needle?: string | null; via: string }[] = [
    { needle: claim.value, via: "value" },
    { needle: claim.normalized_value, via: "normalised value" },
    { needle: claim.source_span, via: "extracted span" },
    { needle: claim.source_region?.label, via: "field label" },
  ];
  for (const candidate of candidates) {
    if (!candidate.needle) continue;
    // A masked value is a placeholder ("S***** B***"); never match it against the page.
    if (claim.masked && (candidate.via === "value" || candidate.via === "normalised value")) {
      continue;
    }
    const re = buildNeedle(String(candidate.needle));
    if (!re) continue;
    const match = re.exec(text);
    if (match) return { start: match.index, end: match.index + match[0].length, via: candidate.via };
  }
  return null;
}

const HIGH_SEVERITIES: Severity[] = ["HIGH", "CRITICAL"];

/* ------------------------------------------------------------ main surface */

export function DocumentViewer({
  propertyId,
  documentId,
}: {
  propertyId: string;
  documentId: string;
}) {
  const { data, error, loading, refetch } = useApi<ViewerPayload>(
    () => endpoints.document(propertyId, documentId),
    [propertyId, documentId],
  );

  const [page, setPage] = React.useState(1);
  const [activeClaimId, setActiveClaimId] = React.useState<string | null>(null);
  const [mode, setMode] = React.useState<"pdf" | "text">("pdf");

  // A fresh document resets the pane; otherwise page 7 of the last file sticks.
  React.useEffect(() => {
    setPage(1);
    setActiveClaimId(null);
  }, [documentId]);

  const doc = data?.document;
  const claims = React.useMemo(() => data?.claims ?? [], [data]);
  const activeClaim = React.useMemo(
    () => claims.find((c) => c.id === activeClaimId) ?? null,
    [claims, activeClaimId],
  );

  const pages = doc?.pages ?? [];
  const currentPage = pages.find((p) => p.page_number === page) ?? pages[0] ?? null;
  // Navigate over the pages that are actually present. A document that *declares* more
  // pages than it carries is a finding in its own right, surfaced below rather than
  // hidden behind a page button that leads nowhere.
  const pageCount = pages.length || doc?.page_count || 1;
  const declaredPages = doc?.page_count ?? pageCount;

  const selectClaim = React.useCallback((claim: ViewerClaim) => {
    setActiveClaimId(claim.id);
    if (claim.source_page) setPage(claim.source_page);
  }, []);

  if (loading) {
    return (
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <LoadingCard rows={10} title="Document page" />
        <LoadingCard rows={8} title="Extracted claims" />
      </div>
    );
  }
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (!doc) return <ErrorState error="This document returned no content." onRetry={refetch} />;

  const highSeverityFlags = (doc.integrity_flags ?? []).filter((f) =>
    HIGH_SEVERITIES.includes(f.severity),
  );
  const otherFlags = (doc.integrity_flags ?? []).filter(
    (f) => !HIGH_SEVERITIES.includes(f.severity),
  );

  // Only the highlight for the page currently on screen may be drawn.
  const activeRegion =
    activeClaim &&
    activeClaim.source_region &&
    (activeClaim.source_page ?? 1) === page
      ? activeClaim.source_region
      : null;

  return (
    <div className="space-y-4">
      <DocumentSummary doc={doc} claimCount={claims.length} />

      {highSeverityFlags.length ? (
        <div className="rounded-2xl border border-status-conflicting/30 bg-status-conflictingBg px-4 py-3.5">
          <div className="flex items-start gap-3">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-status-conflicting" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-status-conflicting">
                {highSeverityFlags.length === 1
                  ? "Integrity indicator requires examination"
                  : `${highSeverityFlags.length} integrity indicators require examination`}
              </p>
              <ul className="mt-2 space-y-2">
                {highSeverityFlags.map((flag) => (
                  <li key={flag.code} className="text-[13px] leading-relaxed text-ink">
                    <span className="inline-flex items-center gap-2">
                      <SeverityBadge severity={flag.severity} />
                      <span className="font-medium">{flag.label}</span>
                      {flag.page ? (
                        <span className="text-2xs text-ink-muted">page {flag.page}</span>
                      ) : null}
                    </span>
                    <p className="mt-1 text-ink-muted">{flag.detail}</p>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-2xs leading-relaxed text-ink-muted">
                An indicator is a prompt to examine the original document. It is not a finding
                of forgery, and this prototype does not make one.
              </p>
            </div>
          </div>
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_400px]">
        {/* ------------------------------------------------------------ left */}
        <Card className="flex min-w-0 flex-col overflow-hidden">
          <CardHeader
            title={mode === "pdf" ? "Rendered page" : "Extracted page text"}
            subtitle={
              mode === "pdf"
                ? "Overlay position is derived from the claim's normalised page region."
                : "Exact match of the claim inside the text this page produced."
            }
            icon={mode === "pdf" ? <FileText className="h-4 w-4" /> : <ScanLine className="h-4 w-4" />}
            action={
              <div className="flex items-center gap-1 rounded-lg bg-canvas-sunken p-0.5">
                <ViewToggle active={mode === "pdf"} onClick={() => setMode("pdf")} label="PDF" />
                <ViewToggle active={mode === "text"} onClick={() => setMode("text")} label="Text" />
              </div>
            }
          />

          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-canvas-border px-4 py-2.5">
            <PageNav page={page} pageCount={pageCount} onChange={setPage} />
            <div className="flex flex-wrap items-center gap-2">
              {declaredPages > pageCount ? (
                <Tooltip content={`The document declares ${declaredPages} pages but only ${pageCount} are present in the stored file. Only the pages that exist can be shown.`}>
                  <span className="cursor-help text-2xs font-semibold text-status-conflicting">
                    {pageCount} of {declaredPages} pages present
                  </span>
                </Tooltip>
              ) : null}
              {currentPage?.ocr_confidence !== null && currentPage?.ocr_confidence !== undefined ? (
                <Tooltip content="Mean confidence of the text acquired for this page. 100% means an embedded text layer was read directly rather than OCR'd.">
                  <span className="text-2xs text-ink-subtle">
                    text confidence{" "}
                    <span className="tnum font-semibold text-ink-muted">
                      {pct(currentPage.ocr_confidence)}
                    </span>
                  </span>
                </Tooltip>
              ) : null}
              {currentPage?.layout_blocks?.length ? (
                <span className="text-2xs text-ink-subtle">
                  <span className="tnum font-semibold text-ink-muted">
                    {currentPage.layout_blocks.length}
                  </span>{" "}
                  layout blocks
                </span>
              ) : null}
            </div>
          </div>

          {mode === "pdf" ? (
            <PdfPane
              documentId={doc.id}
              page={page}
              pageWidth={currentPage?.width ?? 595}
              pageHeight={currentPage?.height ?? 842}
              region={activeRegion}
            />
          ) : (
            <TextPane page={currentPage} claim={activeClaim} activePage={page} />
          )}

          <ProvenanceCaption doc={doc} claim={activeClaim} mode={mode} />
        </Card>

        {/* ----------------------------------------------------------- right */}
        <Card className="flex min-w-0 flex-col overflow-hidden">
          <CardHeader
            title="Extracted claims"
            subtitle={`${claims.length} field${claims.length === 1 ? "" : "s"} bound to a page and region in this document.`}
            icon={<Crosshair className="h-4 w-4" />}
          />
          {claims.length === 0 ? (
            <div className="p-5">
              <EmptyState
                title="No claims extracted from this document"
                description="The pipeline classified the file but found no field it could bind to a page region. That is itself an evidential result — nothing here can support a claim."
                icon={<Info className="h-5 w-5" />}
              />
            </div>
          ) : (
            <ul className="max-h-[620px] divide-y divide-canvas-border/70 overflow-y-auto">
              {claims.map((claim) => (
                <ClaimRow
                  key={claim.id}
                  claim={claim}
                  active={claim.id === activeClaimId}
                  onSelect={() => selectClaim(claim)}
                />
              ))}
            </ul>
          )}
          {otherFlags.length ? (
            <div className="border-t border-canvas-border px-4 py-3">
              <div className="section-label mb-2">Other integrity indicators</div>
              <ul className="space-y-2">
                {otherFlags.map((flag) => (
                  <li key={flag.code} className="text-2xs leading-relaxed text-ink-muted">
                    <span className="inline-flex items-center gap-2">
                      <SeverityBadge severity={flag.severity} />
                      <span className="font-medium text-ink">{flag.label}</span>
                    </span>
                    <p className="mt-0.5">{flag.detail}</p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </Card>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- sub-parts */

function ViewToggle({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-md px-2.5 py-1 text-2xs font-semibold uppercase tracking-[0.08em] transition",
        active ? "bg-canvas-raised text-navy-900 shadow-card" : "text-ink-subtle hover:text-ink",
      )}
    >
      {label}
    </button>
  );
}

function PageNav({
  page,
  pageCount,
  onChange,
}: {
  page: number;
  pageCount: number;
  onChange: (n: number) => void;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <button
        onClick={() => onChange(Math.max(1, page - 1))}
        disabled={page <= 1}
        className="rounded-md p-1 text-ink-subtle transition hover:bg-canvas-sunken hover:text-ink disabled:opacity-35 disabled:hover:bg-transparent"
        aria-label="Previous page"
      >
        <ChevronLeft className="h-4 w-4" />
      </button>
      <div className="flex items-center gap-1">
        {Array.from({ length: pageCount }).map((_, i) => {
          const n = i + 1;
          return (
            <button
              key={n}
              onClick={() => onChange(n)}
              className={cn(
                "tnum h-6 min-w-6 rounded-md px-1.5 text-2xs font-semibold transition",
                n === page
                  ? "bg-navy-900 text-white"
                  : "bg-canvas-sunken text-ink-muted hover:bg-canvas-border/60",
              )}
            >
              {n}
            </button>
          );
        })}
      </div>
      <button
        onClick={() => onChange(Math.min(pageCount, page + 1))}
        disabled={page >= pageCount}
        className="rounded-md p-1 text-ink-subtle transition hover:bg-canvas-sunken hover:text-ink disabled:opacity-35 disabled:hover:bg-transparent"
        aria-label="Next page"
      >
        <ChevronRight className="h-4 w-4" />
      </button>
      <span className="ml-1 text-2xs text-ink-subtle">
        of <span className="tnum">{pageCount}</span>
      </span>
    </div>
  );
}

/**
 * The PDF pane.
 *
 * The overlay box is fitted to the page's own aspect ratio inside the iframe so the
 * normalised region lands close to the right place, but an embedded viewer controls
 * its own zoom and margins — hence the standing note and the text view.
 */
function PdfPane({
  documentId,
  page,
  pageWidth,
  pageHeight,
  region,
}: {
  documentId: string;
  page: number;
  pageWidth: number;
  pageHeight: number;
  region: SourceRegion | null;
}) {
  const src = `${endpoints.documentFileUrl(documentId)}#page=${page}&toolbar=0&navpanes=0&view=Fit`;

  return (
    <div className="relative bg-canvas-sunken">
      <div className="relative h-[560px] w-full">
        <iframe
          key={`${documentId}-${page}`}
          src={src}
          title={`Document page ${page}`}
          className="h-full w-full border-0 bg-canvas-sunken"
        />
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div
            className="relative h-full"
            style={{ aspectRatio: `${pageWidth} / ${pageHeight}` }}
          >
            <div
              className="evidence-highlight"
              style={{
                left: `${Math.max(0, ((region?.x ?? 0.5) - 0.006)) * 100}%`,
                top: `${Math.max(0, ((region?.y ?? 0.5) - 0.006)) * 100}%`,
                width: `${Math.min(1, (region?.w ?? 0.1) + 0.012) * 100}%`,
                height: `${Math.min(1, (region?.h ?? 0.02) + 0.012) * 100}%`,
                opacity: region ? 1 : 0,
              }}
            />
          </div>
        </div>
      </div>
      <p className="flex items-start gap-2 border-t border-canvas-border bg-canvas-raised px-4 py-2 text-2xs leading-relaxed text-ink-muted">
        <Info className="mt-px h-3.5 w-3.5 shrink-0 text-ink-subtle" />
        <span>
          The overlay is positioned from the claim&apos;s normalised page region. The embedded
          PDF viewer sets its own zoom and margins, so alignment here is indicative — switch to{" "}
          <span className="font-semibold text-ink">Text</span> for the exact matched span.
        </span>
      </p>
    </div>
  );
}

function TextPane({
  page,
  claim,
  activePage,
}: {
  page: ViewerPage | null;
  claim: ViewerClaim | null;
  activePage: number;
}) {
  const markRef = React.useRef<HTMLElement>(null);

  const text = page?.text ?? "";
  const onThisPage = claim ? (claim.source_page ?? 1) === activePage : false;
  const hit = React.useMemo(
    () => (claim && onThisPage && text ? locateClaim(text, claim) : null),
    [claim, onThisPage, text],
  );

  React.useEffect(() => {
    if (markRef.current) markRef.current.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [hit?.start, hit?.end]);

  if (!page) {
    return (
      <div className="p-5">
        <EmptyState
          title="No text for this page"
          description="This page produced no extractable text. A scan with no text layer would be routed to OCR instead."
        />
      </div>
    );
  }

  return (
    <div className="min-w-0 bg-canvas-raised">
      <div className="h-[560px] overflow-auto px-4 py-3">
        <pre className="whitespace-pre-wrap break-words font-mono text-[12.5px] leading-relaxed text-ink">
          {hit ? (
            <>
              {text.slice(0, hit.start)}
              <mark
                ref={markRef}
                className="rounded-[3px] bg-emerald-200/70 px-0.5 text-ink ring-1 ring-emerald-500/70"
              >
                {text.slice(hit.start, hit.end)}
              </mark>
              {text.slice(hit.end)}
            </>
          ) : (
            text
          )}
        </pre>
      </div>
      <p className="flex items-start gap-2 border-t border-canvas-border px-4 py-2 text-2xs leading-relaxed text-ink-muted">
        <Info className="mt-px h-3.5 w-3.5 shrink-0 text-ink-subtle" />
        <span>
          {claim
            ? onThisPage
              ? hit
                ? `Matched on this page by ${hit.via}.`
                : "This claim's value could not be matched literally in the page text — it was anchored by page geometry instead."
              : `Selected claim sits on page ${claim.source_page ?? 1}.`
            : "Select a claim on the right to highlight the text it was read from."}
        </span>
      </p>
    </div>
  );
}

function ProvenanceCaption({
  doc,
  claim,
  mode,
}: {
  doc: ViewerDocument;
  claim: ViewerClaim | null;
  mode: "pdf" | "text";
}) {
  return (
    <div className="border-t border-canvas-border bg-canvas-sunken/60 px-4 py-3">
      <AnimatePresence mode="wait">
        {claim ? (
          <motion.div
            key={claim.id}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.16 }}
            className="min-w-0"
          >
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px]">
              <span className="section-label">Source</span>
              <span className="truncate font-medium text-ink">{doc.filename}</span>
              <span className="text-ink-subtle">·</span>
              <span className="text-ink-muted">Page {claim.source_page ?? 1}</span>
              <span className="text-ink-subtle">·</span>
              <span className="tnum text-ink-muted">Confidence {pct(claim.confidence)}</span>
              {claim.source_region?.label ? (
                <>
                  <span className="text-ink-subtle">·</span>
                  <span className="text-ink-muted">
                    Field &ldquo;{claim.source_region.label}&rdquo;
                  </span>
                </>
              ) : null}
            </div>
            <p className="mt-1 text-2xs leading-relaxed text-ink-muted">
              {claim.label}: <span className="font-medium text-ink">{claim.value}</span>
              {claim.extraction_method ? ` · extracted by ${claim.extraction_method}` : null}
              {mode === "pdf" && claim.source_region
                ? ` · region x${claim.source_region.x.toFixed(3)} y${claim.source_region.y.toFixed(3)}`
                : null}
            </p>
          </motion.div>
        ) : (
          <motion.p
            key="empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="text-2xs leading-relaxed text-ink-muted"
          >
            Every claim on the right carries the document, page and region it was read from.
            Select one to see the provenance for that value.
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}

function ClaimRow({
  claim,
  active,
  onSelect,
}: {
  claim: ViewerClaim;
  active: boolean;
  onSelect: () => void;
}) {
  const recovered = claim.source_region?.recovered_by === "layout";
  return (
    <li>
      <button
        onClick={onSelect}
        className={cn(
          "w-full px-4 py-3 text-left transition",
          active ? "bg-navy-50" : "hover:bg-canvas-sunken/70",
        )}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="section-label">{claim.label || titleise(claim.claim_type)}</div>
            <div className="mt-1 flex items-center gap-1.5">
              {claim.masked ? <Lock className="h-3 w-3 shrink-0 text-ink-subtle" /> : null}
              <span
                className={cn(
                  "truncate text-sm font-medium",
                  claim.masked ? "font-mono text-[13px] text-ink-muted" : "text-ink",
                )}
              >
                {claim.value}
              </span>
            </div>
          </div>
          <StatusBadge status={claim.verification_status} size="sm" />
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <span className="text-2xs text-ink-subtle">
            Page <span className="tnum font-semibold text-ink-muted">{claim.source_page ?? 1}</span>
          </span>
          <ConfidenceBar value={claim.confidence} />
          {recovered ? (
            <Tooltip content="The value was not adjacent to its label in the document's reading order, so it was recovered from word geometry — the field was located on the page by position rather than by sequence. This is the signature of a field having been overtyped after the document was produced.">
              <Chip tone="amber" className="cursor-help">
                <Layers className="h-3 w-3" />
                recovered by layout
              </Chip>
            </Tooltip>
          ) : null}
          {claim.masked && claim.mask_reason ? (
            <Tooltip content={claim.mask_reason}>
              <span className="text-2xs text-ink-subtle underline decoration-dotted">
                why masked
              </span>
            </Tooltip>
          ) : null}
        </div>

        {claim.source_span ? (
          <p className="mt-2 rounded-lg bg-canvas-sunken px-2.5 py-1.5 font-mono text-2xs leading-relaxed text-ink-muted">
            …{claim.source_span.trim()}…
          </p>
        ) : null}

        {active && claim.status_explanation ? (
          <p className="mt-2 flex items-start gap-1.5 text-2xs leading-relaxed text-ink-muted">
            <AlertTriangle className="mt-px h-3 w-3 shrink-0 text-ink-subtle" />
            <span>{claim.status_explanation}</span>
          </p>
        ) : null}
      </button>
    </li>
  );
}

function DocumentSummary({ doc, claimCount }: { doc: ViewerDocument; claimCount: number }) {
  return (
    <div className="scroll-x">
      <div className="flex min-w-max flex-wrap items-center gap-x-5 gap-y-2 rounded-2xl border border-canvas-border bg-canvas-raised px-4 py-3">
        <div className="flex items-center gap-2.5">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-navy-50 text-navy-700">
            <FileText className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-semibold text-ink">{doc.filename}</div>
            <div className="text-2xs text-ink-muted">
              {doc.doc_type_label} · classified at{" "}
              <span className="tnum">{pct(doc.classification_confidence)}</span> confidence
            </div>
          </div>
        </div>
        <Facet label="Pages" value={doc.page_count} />
        <Facet label="Claims" value={claimCount} />
        <Facet label="Mode" value={`${doc.extraction_mode} · ${doc.ocr_engine}`} />
        <Facet
          label="Quality"
          value={doc.quality_score === null ? "—" : pct(doc.quality_score)}
        />
      </div>
    </div>
  );
}

function Facet({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="section-label">{label}</div>
      <div className="tnum mt-0.5 text-[13px] font-medium text-ink">{value}</div>
    </div>
  );
}
