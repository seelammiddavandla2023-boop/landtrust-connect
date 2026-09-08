"use client";

import {
  AlertTriangle,
  Eye,
  FileStack,
  FileWarning,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import React from "react";

import { DocumentViewer } from "@/components/document-viewer";
import {
  Card,
  CardHeader,
  Chip,
  ConfidenceBar,
  Drawer,
  EmptyState,
  LoadingCard,
  Tooltip,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import { DOC_TYPE_LABEL } from "@/lib/domain";
import { cn, pct, shortDate } from "@/lib/format";

const SEVERITY_TONE: Record<string, "red" | "amber" | "neutral"> = {
  HIGH: "red",
  MEDIUM: "amber",
  LOW: "neutral",
};

export function DocumentsTab({
  propertyId,
  documents,
}: {
  propertyId: string;
  documents: any;
}) {
  const [open, setOpen] = React.useState<string | null>(null);

  if (!documents) return <LoadingCard rows={8} title="Evidence" />;

  const items: any[] = documents.items ?? [];
  const flagged = items.filter((d) => (d.integrity_flags ?? []).length > 0);
  const expired = items.filter((d) => d.is_expired);

  return (
    <div className="space-y-4">
      {(flagged.length > 0 || expired.length > 0) && (
        <Card className="border-status-partial/30 bg-status-partialBg/40">
          <CardHeader
            title="Document indicators requiring review"
            subtitle="These are indicators computed from the files themselves — an incremental save, an isolated font, a page count that does not match. None of them is a finding that a document is forged; each is a prompt for examination by an authorised person."
            icon={<FileWarning className="h-4 w-4" />}
          />
          <ul className="divide-y divide-canvas-border/70">
            {items
              .filter((d) => (d.integrity_flags ?? []).length || d.is_expired)
              .map((d) => (
                <li key={d.id} className="px-5 py-3.5">
                  <button
                    onClick={() => setOpen(d.id)}
                    className="text-[13px] font-medium text-ink hover:underline"
                  >
                    {d.filename}
                  </button>
                  <ul className="mt-2 space-y-2">
                    {d.is_expired ? (
                      <li className="flex items-start gap-2">
                        <Chip tone="amber">EXPIRED</Chip>
                        <p className="text-2xs leading-relaxed text-ink-muted">
                          Validity ended {shortDate(d.valid_until)}. Claims resting solely on this
                          document are held at EXPIRED rather than verified.
                        </p>
                      </li>
                    ) : null}
                    {(d.integrity_flags ?? []).map((f: any, i: number) => (
                      <li key={i} className="flex items-start gap-2">
                        <Chip tone={SEVERITY_TONE[f.severity] ?? "neutral"}>{f.code}</Chip>
                        <p className="text-2xs leading-relaxed text-ink-muted">{f.detail}</p>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
          </ul>
        </Card>
      )}

      <Card>
        <CardHeader
          title="Evidence on file"
          subtitle="Every document was classified, read and linked by the pipeline. Confidence, quality and processing time are measured, not assigned."
          icon={<FileStack className="h-4 w-4" />}
          action={
            <Link
              href="/documents"
              className="text-[13px] font-medium text-navy-700 hover:underline"
            >
              Upload more evidence
            </Link>
          }
        />
        {items.length === 0 ? (
          <div className="p-5">
            <EmptyState
              title="No documents"
              description="This property has no evidence on file, so nothing about it can be verified."
            />
          </div>
        ) : (
          <div className="scroll-x">
            <table className="table-grid">
              <thead>
                <tr>
                  <th className="min-w-[230px]">Document</th>
                  <th className="min-w-[180px]">Classified as</th>
                  <th>Pages</th>
                  <th>Claims</th>
                  <th className="min-w-[110px]">Quality</th>
                  <th className="min-w-[150px]">Dates</th>
                  <th className="min-w-[140px]">Reader</th>
                  <th className="min-w-[130px]">Indicators</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((d) => (
                  <tr key={d.id} className="clickable" onClick={() => setOpen(d.id)}>
                    <td>
                      <div className="font-medium text-ink">{d.filename}</div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-2xs text-ink-subtle">
                        <span>{(d.size_bytes / 1024).toFixed(0)} KB</span>
                        {d.reference_number ? (
                          <span className="font-mono">{d.reference_number}</span>
                        ) : null}
                        <span className="font-mono">{d.checksum}…</span>
                      </div>
                    </td>
                    <td>
                      <div className="text-[13px] text-ink">
                        {DOC_TYPE_LABEL[d.doc_type] ?? d.doc_type_label}
                      </div>
                      <div className="mt-1">
                        <ConfidenceBar value={d.classification_confidence} />
                      </div>
                    </td>
                    <td className="tnum text-[13px] text-ink-muted">{d.page_count}</td>
                    <td className="tnum text-[13px] text-ink-muted">{d.claim_count ?? "—"}</td>
                    <td>
                      <ConfidenceBar value={d.quality_score} />
                    </td>
                    <td className="text-2xs text-ink-muted">
                      <div>issued {shortDate(d.issued_on)}</div>
                      {d.valid_until ? (
                        <div className={cn(d.is_expired && "font-medium text-status-conflicting")}>
                          valid to {shortDate(d.valid_until)}
                        </div>
                      ) : null}
                    </td>
                    <td className="text-2xs text-ink-muted">
                      <div className="font-mono">{d.ocr_engine}</div>
                      <div>
                        {d.extraction_mode} mode · {d.processing_ms} ms
                      </div>
                    </td>
                    <td>
                      {d.is_expired || (d.integrity_flags ?? []).length ? (
                        <div className="flex flex-wrap gap-1">
                          {d.is_expired ? <Chip tone="amber">expired</Chip> : null}
                          {(d.integrity_flags ?? []).map((f: any, i: number) => (
                            <Tooltip key={i} content={f.detail}>
                              <Chip tone={SEVERITY_TONE[f.severity] ?? "neutral"}>
                                {f.code.replace(/_/g, " ").toLowerCase()}
                              </Chip>
                            </Tooltip>
                          ))}
                        </div>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-2xs text-status-verified">
                          <ShieldCheck className="h-3 w-3" />
                          none
                        </span>
                      )}
                    </td>
                    <td>
                      <span className="inline-flex items-center gap-1 text-2xs font-medium text-navy-700">
                        <Eye className="h-3.5 w-3.5" />
                        View
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Drawer
        open={Boolean(open)}
        onClose={() => setOpen(null)}
        title="Document viewer"
        subtitle="Click any extracted claim to highlight the region of the page it came from."
        width="max-w-6xl"
      >
        {open ? <DocumentViewer propertyId={propertyId} documentId={open} /> : null}
      </Drawer>
    </div>
  );
}
