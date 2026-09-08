"use client";

/**
 * The Claim–Evidence Matrix.
 *
 * One row per land attribute, not per document. Each row shows what the platform
 * believes, how strongly, on what evidence, and what disagrees — and clicking it
 * opens the evidence drawer with the source page text, the region the value came
 * from, and every supporting and conflicting assertion.
 *
 * This is the screen that makes the research gap legible: the same value can be
 * VERIFIED on one file and PARTIALLY_VERIFIED on another purely because of what else
 * is on file, and the row says exactly why.
 */

import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  CircleAlert,
  Clock,
  Eye,
  FileText,
  Filter,
  Layers,
  Link2,
} from "lucide-react";
import React from "react";

import { useApi } from "@/components/hooks";
import {
  Card,
  CardHeader,
  Chip,
  ConfidenceBar,
  Drawer,
  EmptyState,
  ErrorState,
  EvidenceChip,
  KeyValue,
  LoadingCard,
  MaskedValue,
  SeverityBadge,
  StatusBadge,
  Tooltip,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import { VERIFICATION_META, type Severity, type VerificationStatus } from "@/lib/domain";
import { cn, pct, shortDate, titleise } from "@/lib/format";

const MATCH_LABEL: Record<string, { label: string; tone: "emerald" | "amber" | "red" | "neutral" }> =
  {
    EXACT_MATCH: { label: "Exact match", tone: "emerald" },
    NORMALIZED_MATCH: { label: "Match after normalisation", tone: "emerald" },
    PARTIAL_MATCH: { label: "Partial match", tone: "amber" },
    MISMATCH: { label: "Mismatch", tone: "red" },
    MISSING: { label: "Not comparable", tone: "neutral" },
    EXPIRED: { label: "Expired", tone: "amber" },
  };

export function ClaimsTab({ propertyId, claims }: { propertyId: string; claims: any }) {
  const [selected, setSelected] = React.useState<string | null>(null);
  const [statusFilter, setStatusFilter] = React.useState<VerificationStatus | null>(null);
  const [coreOnly, setCoreOnly] = React.useState(false);

  if (!claims) return <LoadingCard rows={10} title="Claim–Evidence Matrix" />;

  const matrix: any[] = claims.matrix ?? [];
  const statusCounts: Record<string, number> = {};
  for (const row of matrix) {
    statusCounts[row.verification_status] = (statusCounts[row.verification_status] || 0) + 1;
  }

  let rows = matrix;
  if (statusFilter) rows = rows.filter((r) => r.verification_status === statusFilter);
  if (coreOnly) rows = rows.filter((r) => r.is_core);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Claim–Evidence Matrix"
          subtitle="Every land detail with the evidence behind it. A status is derived from the whole evidence set — never from the document a value happened to appear in."
          icon={<Layers className="h-4 w-4" />}
          action={
            <div className="flex items-center gap-2 text-2xs text-ink-muted">
              <span className="tnum font-medium text-ink">{pct(claims.verification_level)}</span>
              of core claims verified
            </div>
          }
        />

        <div className="flex flex-wrap items-center gap-1.5 border-b border-canvas-border px-5 py-3">
          <Filter className="mr-1 h-3.5 w-3.5 text-ink-subtle" />
          <Chip
            tone={statusFilter === null ? "navy" : "neutral"}
            active={statusFilter === null}
            onClick={() => setStatusFilter(null)}
          >
            All · {matrix.length}
          </Chip>
          {(Object.keys(statusCounts) as VerificationStatus[])
            .sort()
            .map((s) => (
              <button key={s} onClick={() => setStatusFilter(statusFilter === s ? null : s)}>
                <span
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 transition",
                    VERIFICATION_META[s].fg,
                    VERIFICATION_META[s].bg,
                    statusFilter === s ? "ring-2 ring-navy-500" : VERIFICATION_META[s].ring,
                  )}
                >
                  {VERIFICATION_META[s].label} · {statusCounts[s]}
                </span>
              </button>
            ))}
          <span className="mx-1 h-4 w-px bg-canvas-border" />
          <Chip tone={coreOnly ? "navy" : "neutral"} active={coreOnly} onClick={() => setCoreOnly(!coreOnly)}>
            Core claims only
          </Chip>
        </div>

        {rows.length === 0 ? (
          <div className="p-5">
            <EmptyState title="No claims match this filter" />
          </div>
        ) : (
          <div className="scroll-x">
            <table className="table-grid">
              <thead>
                <tr>
                  <th className="min-w-[150px]">Claim</th>
                  <th className="min-w-[150px]">Claimed value</th>
                  <th className="min-w-[150px]">Source</th>
                  <th>Page</th>
                  <th className="min-w-[110px]">Confidence</th>
                  <th className="min-w-[110px]">Supporting</th>
                  <th className="min-w-[110px]">Conflicting</th>
                  <th className="min-w-[160px]">Status</th>
                  <th className="min-w-[300px]">Explanation</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.claim_type}
                    className={cn("clickable", row.id ? "" : "opacity-90")}
                    onClick={() => row.id && setSelected(row.id)}
                  >
                    <td>
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium text-ink">{row.label}</span>
                        {row.is_core ? (
                          <Tooltip content="One of the six core claims a complete land file must establish.">
                            <span className="rounded bg-navy-50 px-1 py-0.5 text-[9px] font-bold uppercase tracking-wide text-navy-700">
                              core
                            </span>
                          </Tooltip>
                        ) : null}
                      </div>
                      <div className="mt-0.5 font-mono text-[10px] text-ink-subtle">
                        {row.claim_type}
                      </div>
                    </td>
                    <td>
                      {row.masked ? (
                        <MaskedValue value={row.value} reason={row.mask_reason} />
                      ) : (
                        <span
                          className={cn(
                            "text-[13px]",
                            row.id ? "font-medium text-ink" : "italic text-ink-subtle",
                          )}
                        >
                          {row.value}
                        </span>
                      )}
                    </td>
                    <td className="text-[13px] text-ink-muted">
                      {row.document_name ? (
                        <span className="inline-flex items-center gap-1.5">
                          <FileText className="h-3 w-3 shrink-0 text-ink-subtle" />
                          <span className="truncate">{row.document_name}</span>
                        </span>
                      ) : (
                        <span className="text-ink-subtle">—</span>
                      )}
                    </td>
                    <td className="tnum text-[13px] text-ink-muted">
                      {row.source_page ?? "—"}
                    </td>
                    <td>
                      {row.confidence ? <ConfidenceBar value={row.confidence} /> : <span className="text-ink-subtle">—</span>}
                    </td>
                    <td>
                      <span className="text-[13px] text-ink-muted">
                        <span className="tnum font-medium text-status-verified">
                          {row.supporting_documents}
                        </span>{" "}
                        doc{row.supporting_documents === 1 ? "" : "s"}
                      </span>
                    </td>
                    <td>
                      <span className="text-[13px] text-ink-muted">
                        <span
                          className={cn(
                            "tnum font-medium",
                            row.contradictions?.length ? "text-status-conflicting" : "text-ink-subtle",
                          )}
                        >
                          {row.contradictions?.length ?? 0}
                        </span>{" "}
                        conflict{(row.contradictions?.length ?? 0) === 1 ? "" : "s"}
                      </span>
                    </td>
                    <td>
                      <StatusBadge status={row.verification_status} size="sm" />
                    </td>
                    <td>
                      <p className="max-w-[420px] text-2xs leading-relaxed text-ink-muted">
                        {row.explanation}
                      </p>
                      {row.id ? (
                        <span className="mt-1 inline-flex items-center gap-1 text-2xs font-medium text-navy-700">
                          Open evidence <ArrowRight className="h-3 w-3" />
                        </span>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <ClaimHistoryPanel matrix={matrix} />

      <EvidenceDrawer
        propertyId={propertyId}
        claimId={selected}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}

/* --------------------------------------------------------- claim history */

function ClaimHistoryPanel({ matrix }: { matrix: any[] }) {
  // Attributes whose value changed over time are the ones the temporal scoping layer
  // handles; showing them explicitly answers "why isn't this a contradiction?"
  const withHistory = matrix.filter(
    (r) => (r.history?.length ?? 0) > 1 && r.history.some((h: any) => h.superseded),
  );
  if (withHistory.length === 0) return null;

  return (
    <Card>
      <CardHeader
        title="Superseded assertions"
        subtitle="Earlier statements retained as history and excluded from current-state comparison. A chain of title is not a set of contradictions."
        icon={<Clock className="h-4 w-4" />}
      />
      <div className="space-y-4 p-5">
        {withHistory.map((row) => (
          <div key={row.claim_type}>
            <div className="mb-2 flex items-center gap-2">
              <span className="text-[13px] font-semibold text-ink">{row.label}</span>
              <StatusBadge status={row.verification_status} size="sm" withTooltip={false} />
            </div>
            <ol className="relative space-y-2 border-l border-canvas-border pl-4">
              {row.history.map((h: any) => (
                <li key={h.claim_id} className="relative">
                  <span
                    className={cn(
                      "absolute -left-[21px] top-1.5 h-2 w-2 rounded-full ring-2 ring-canvas-raised",
                      h.superseded ? "bg-canvas-borderStrong" : "bg-status-verified",
                    )}
                  />
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span
                      className={cn(
                        "text-[13px]",
                        h.superseded
                          ? "text-ink-subtle line-through decoration-canvas-borderStrong"
                          : "font-medium text-ink",
                      )}
                    >
                      {h.value}
                    </span>
                    <span className="text-2xs text-ink-subtle">
                      {h.document} · p{h.page} · {shortDate(h.effective_date)}
                    </span>
                    {h.superseded ? (
                      <span className="rounded bg-canvas-sunken px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-ink-subtle">
                        superseded
                      </span>
                    ) : (
                      <span className="rounded bg-status-verifiedBg px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-status-verified">
                        current
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        ))}
      </div>
    </Card>
  );
}

/* -------------------------------------------------------- evidence drawer */

function EvidenceDrawer({
  propertyId,
  claimId,
  onClose,
}: {
  propertyId: string;
  claimId: string | null;
  onClose: () => void;
}) {
  const { data, error, loading } = useApi<any>(
    () => endpoints.claimEvidence(propertyId, claimId!),
    [propertyId, claimId],
    { enabled: Boolean(claimId) },
  );

  const claim = data?.claim;
  const source = data?.source;

  return (
    <Drawer
      open={Boolean(claimId)}
      onClose={onClose}
      title={claim ? claim.label : "Evidence"}
      subtitle={
        claim
          ? `${claim.document_name} · page ${claim.source_page} · extraction confidence ${Math.round(
              claim.confidence * 100,
            )}%`
          : undefined
      }
      width="max-w-3xl"
    >
      {loading ? (
        <div className="space-y-3">
          <LoadingCard rows={5} />
          <LoadingCard rows={5} />
        </div>
      ) : error ? (
        <ErrorState error={error} />
      ) : data ? (
        <div className="space-y-5">
          {/* -------------------------------------------------- the claim */}
          <Card className="p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="section-label">Extracted value</div>
                <div className="mt-1 text-lg font-semibold text-ink">
                  {claim.masked ? (
                    <MaskedValue value={claim.value} reason={claim.mask_reason} />
                  ) : (
                    claim.value
                  )}
                </div>
                {claim.normalized_value && claim.normalized_value !== claim.value ? (
                  <div className="mt-1 font-mono text-2xs text-ink-subtle">
                    normalised → {claim.normalized_value}
                  </div>
                ) : null}
              </div>
              <StatusBadge status={claim.verification_status} />
            </div>
            <p className="mt-3 rounded-lg bg-canvas-sunken px-3 py-2.5 text-[13px] leading-relaxed text-ink-muted">
              {claim.status_explanation}
            </p>
            <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <KeyValue
                label="Confidence"
                value={<ConfidenceBar value={claim.confidence} />}
              />
              <KeyValue label="Extraction" value={claim.extraction_method} />
              <KeyValue label="Sensitivity" value={titleise(claim.sensitivity)} />
              <KeyValue
                label="OCR confidence"
                value={source?.ocr_confidence != null ? pct(source.ocr_confidence) : "—"}
              />
            </dl>
          </Card>

          {/* ------------------------------------------------- provenance */}
          <Card>
            <CardHeader
              title="Provenance"
              subtitle="Where in the document this value came from"
              icon={<Link2 className="h-4 w-4" />}
            />
            <div className="space-y-3 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <EvidenceChip
                  document={claim.document_name}
                  page={claim.source_page}
                  confidence={claim.confidence}
                />
                {claim.source_region?.recovered_by === "layout" ? (
                  <Tooltip content="The document's reading order did not carry this value next to its label — a signature of a file edited after issue. The value was recovered from the word geometry on the page instead.">
                    <Chip tone="amber">recovered by layout</Chip>
                  </Tooltip>
                ) : null}
                {source?.document?.is_expired ? <Chip tone="red">document expired</Chip> : null}
              </div>

              {claim.source_span ? (
                <div>
                  <div className="section-label mb-1.5">Source text</div>
                  <p className="rounded-lg border border-canvas-border bg-canvas-sunken px-3 py-2.5 font-mono text-2xs leading-relaxed text-ink-muted">
                    …{claim.source_span}…
                  </p>
                </div>
              ) : null}

              {source?.region?.w ? (
                <div>
                  <div className="section-label mb-1.5">Region on page {claim.source_page}</div>
                  <PageRegionPreview region={source.region} pageText={source.page_text} />
                </div>
              ) : null}

              <a
                href={endpoints.documentFileUrl(claim.document_id)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-2xs font-medium text-navy-700 hover:underline"
              >
                <Eye className="h-3.5 w-3.5" />
                Open the source document
              </a>
            </div>
          </Card>

          {/* --------------------------------------------------- evidence */}
          <div className="grid gap-4 sm:grid-cols-2">
            <RelatedClaims
              title="Supporting evidence"
              tone="verified"
              rows={data.supporting}
              empty="No other document on file asserts this detail. That is why a single source cannot verify it."
            />
            <RelatedClaims
              title="Conflicting evidence"
              tone="conflicting"
              rows={data.conflicting}
              empty="Nothing on file disagrees with this value."
            />
          </div>

          {/* ---------------------------------------------- contradictions */}
          {data.contradictions?.length ? (
            <Card>
              <CardHeader
                title="Recorded contradictions"
                subtitle="Detected by cross-document comparison"
                icon={<CircleAlert className="h-4 w-4" />}
              />
              <ul className="divide-y divide-canvas-border">
                {data.contradictions.map((c: any) => (
                  <li key={c.id} className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <SeverityBadge severity={c.severity as Severity} />
                      <span className="text-[13px] font-medium text-ink">
                        {titleise(c.contradiction_type)}
                      </span>
                      {c.difference ? (
                        <span className="tnum rounded bg-status-conflictingBg px-1.5 py-0.5 text-2xs font-medium text-status-conflicting">
                          {c.difference}
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      <div className="rounded-lg border border-canvas-border p-2.5">
                        <div className="text-2xs text-ink-subtle">{c.left_source}</div>
                        <div className="mt-0.5 text-[13px] font-medium text-ink">
                          {c.left_value}
                        </div>
                      </div>
                      <div className="rounded-lg border border-status-conflicting/25 bg-status-conflictingBg/50 p-2.5">
                        <div className="text-2xs text-ink-subtle">{c.right_source}</div>
                        <div className="mt-0.5 text-[13px] font-medium text-ink">
                          {c.right_value}
                        </div>
                      </div>
                    </div>
                    <p className="mt-2 text-2xs leading-relaxed text-ink-muted">{c.explanation}</p>
                    <div className="mt-1.5 font-mono text-[10px] text-ink-subtle">
                      rule: {c.detection_rule}
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}
        </div>
      ) : null}
    </Drawer>
  );
}

function RelatedClaims({
  title,
  tone,
  rows,
  empty,
}: {
  title: string;
  tone: "verified" | "conflicting";
  rows: any[];
  empty: string;
}) {
  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            {title}
            <span
              className={cn(
                "tnum rounded-full px-1.5 py-0.5 text-2xs font-semibold",
                tone === "verified"
                  ? "bg-status-verifiedBg text-status-verified"
                  : "bg-status-conflictingBg text-status-conflicting",
              )}
            >
              {rows?.length ?? 0}
            </span>
          </span>
        }
      />
      <div className="p-4">
        {!rows?.length ? (
          <p className="text-2xs leading-relaxed text-ink-muted">{empty}</p>
        ) : (
          <ul className="space-y-2.5">
            {rows.map((r: any) => {
              const match = MATCH_LABEL[r.match_type] ?? MATCH_LABEL.MISSING;
              return (
                <li key={r.id} className="rounded-lg border border-canvas-border p-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[13px] font-medium text-ink">
                      {r.masked ? <MaskedValue value={r.value} reason={r.mask_reason} /> : r.value}
                    </span>
                    <Chip tone={match.tone}>{match.label}</Chip>
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2">
                    <EvidenceChip
                      document={r.document_name}
                      page={r.source_page}
                      confidence={r.confidence}
                    />
                  </div>
                  {r.note ? (
                    <p className="mt-1.5 text-2xs leading-relaxed text-ink-muted">{r.note}</p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Card>
  );
}

/**
 * A schematic of where on the page the value sits.
 *
 * Deliberately a schematic rather than a rendered page: the drawer is about the
 * *relationship* between claim and location, and a miniature that always draws
 * correctly is more honest than an embedded PDF that may fail to align. The full
 * side-by-side viewer lives in Document Intelligence.
 */
function PageRegionPreview({ region, pageText }: { region: any; pageText?: string }) {
  return (
    <div className="flex gap-3">
      <div className="relative aspect-[1/1.414] w-24 shrink-0 overflow-hidden rounded-md border border-canvas-border bg-white">
        <div className="absolute inset-x-2 top-2 space-y-1">
          {Array.from({ length: 14 }).map((_, i) => (
            <div
              key={i}
              className="h-[2px] rounded-full bg-canvas-sunken"
              style={{ width: `${55 + ((i * 37) % 40)}%` }}
            />
          ))}
        </div>
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="absolute rounded-[2px] bg-emerald-500/25 ring-1 ring-emerald-600"
          style={{
            left: `${region.x * 100}%`,
            top: `${region.y * 100}%`,
            width: `${Math.max(region.w, 0.02) * 100}%`,
            height: `${Math.max(region.h, 0.012) * 100}%`,
          }}
        />
      </div>
      <div className="min-w-0 flex-1 text-2xs text-ink-muted">
        <p className="leading-relaxed">
          Normalised coordinates{" "}
          <span className="font-mono text-ink">
            x {region.x?.toFixed(3)} · y {region.y?.toFixed(3)} · w {region.w?.toFixed(3)} · h{" "}
            {region.h?.toFixed(3)}
          </span>
          {region.label ? (
            <>
              , anchored to the label <span className="font-medium text-ink">“{region.label}”</span>
            </>
          ) : null}
          .
        </p>
        <p className="mt-1.5 leading-relaxed">
          The same coordinates drive the highlight overlay in the side-by-side document viewer.
        </p>
      </div>
    </div>
  );
}
