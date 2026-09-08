"use client";

import { Filter, History, Search } from "lucide-react";
import React from "react";

import { useApi } from "@/components/hooks";
import {
  Card,
  CardHeader,
  Chip,
  EmptyState,
  ErrorState,
  LoadingCard,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import { cn, dateTime, relative, titleise } from "@/lib/format";

/** Actions grouped by what they tell a reviewer, so the trail is skimmable. */
const GROUPS: { key: string; label: string; actions: string[]; tone: string }[] = [
  {
    key: "ingest",
    label: "Ingestion",
    tone: "bg-navy-500",
    actions: ["DOCUMENT_UPLOADED", "DOCUMENT_CLASSIFIED", "OCR_EXECUTED", "CLAIM_EXTRACTED"],
  },
  {
    key: "reasoning",
    label: "Reasoning",
    tone: "bg-emerald-500",
    actions: ["CLAIM_STATUS_CHANGED", "CONTRADICTION_DETECTED", "CONTRADICTION_RESOLVED"],
  },
  {
    key: "control",
    label: "Control",
    tone: "bg-risk-high",
    actions: [
      "RISK_RECALCULATED",
      "TRANSACTION_HELD",
      "TRANSACTION_RELEASED",
      "TRANSACTION_ESCALATED",
      "RESOLUTION_PLAN_GENERATED",
      "RESOLUTION_ACTION_APPLIED",
      "EVIDENCE_ADDED",
    ],
  },
  {
    key: "privacy",
    label: "Consent & interaction",
    tone: "bg-status-owner",
    actions: [
      "CONSENT_REQUESTED",
      "CONSENT_APPROVED",
      "CONSENT_DENIED",
      "CONSENT_EXPIRED",
      "DISCLOSURE_VIEWED",
      "MESSAGE_SENT",
    ],
  },
  {
    key: "assistant",
    label: "Assistant",
    tone: "bg-status-info",
    actions: ["ASSISTANT_QUERY", "ASSISTANT_REFUSAL"],
  },
];

function groupOf(action: string) {
  return GROUPS.find((g) => g.actions.includes(action));
}

export function AuditTab({ propertyId, version }: { propertyId: string; version: number }) {
  const { data, error, loading, refetch } = useApi<any>(
    () => endpoints.audit(propertyId),
    [propertyId, version],
  );
  const [group, setGroup] = React.useState<string | null>(null);
  const [query, setQuery] = React.useState("");

  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (loading || !data) return <LoadingCard rows={12} title="Audit trail" />;

  let items: any[] = data.items ?? [];
  if (group) {
    const actions = GROUPS.find((g) => g.key === group)?.actions ?? [];
    items = items.filter((e) => actions.includes(e.action));
  }
  if (query.trim()) {
    const q = query.toLowerCase();
    items = items.filter(
      (e) =>
        e.summary.toLowerCase().includes(q) ||
        e.action.toLowerCase().includes(q) ||
        e.actor_name.toLowerCase().includes(q),
    );
  }

  const counts: Record<string, number> = {};
  for (const e of data.items ?? []) {
    const g = groupOf(e.action);
    if (g) counts[g.key] = (counts[g.key] || 0) + 1;
  }

  return (
    <Card>
      <CardHeader
        title={`Audit trail · ${data.count} events`}
        subtitle="Append-only. Every consequential action — an upload, an OCR run, a status change, a consent decision, a hold, an assistant refusal — is recorded with the evidence it rests on."
        icon={<History className="h-4 w-4" />}
      />

      <div className="flex flex-wrap items-center gap-2 border-b border-canvas-border px-5 py-3">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-subtle" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search the trail…"
            className="w-full rounded-lg border border-canvas-borderStrong bg-canvas-raised py-1.5 pl-8 pr-3 text-2xs text-ink placeholder:text-ink-subtle"
          />
        </div>
        <Filter className="h-3.5 w-3.5 text-ink-subtle" />
        <Chip tone={group === null ? "navy" : "neutral"} active={group === null} onClick={() => setGroup(null)}>
          All · {data.count}
        </Chip>
        {GROUPS.filter((g) => counts[g.key]).map((g) => (
          <Chip
            key={g.key}
            tone={group === g.key ? "navy" : "neutral"}
            active={group === g.key}
            onClick={() => setGroup(group === g.key ? null : g.key)}
          >
            {g.label} · {counts[g.key]}
          </Chip>
        ))}
      </div>

      {items.length === 0 ? (
        <div className="p-5">
          <EmptyState title="No matching events" />
        </div>
      ) : (
        <ol className="max-h-[720px] overflow-y-auto">
          {items.map((e) => {
            const g = groupOf(e.action);
            const isRefusal = e.action === "ASSISTANT_REFUSAL";
            const isBlocked = e.result === "BLOCKED";
            return (
              <li
                key={e.id}
                className="flex gap-3 border-b border-canvas-border/70 px-5 py-3 last:border-b-0"
              >
                <div className="flex shrink-0 flex-col items-center">
                  <span className={cn("mt-1.5 h-2 w-2 rounded-full", g?.tone ?? "bg-canvas-borderStrong")} />
                  <span className="mt-1 w-px flex-1 bg-canvas-border" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="text-[13px] font-medium text-ink">{titleise(e.action)}</span>
                    {e.result && e.result !== "OK" ? (
                      <span
                        className={cn(
                          "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                          isBlocked || ["CRITICAL", "HIGH"].includes(e.result)
                            ? "bg-status-conflictingBg text-status-conflicting"
                            : isRefusal
                              ? "bg-status-infoBg text-status-info"
                              : "bg-canvas-sunken text-ink-muted",
                        )}
                      >
                        {e.result}
                      </span>
                    ) : null}
                    <span className="text-2xs text-ink-subtle">
                      {e.actor_name} · {e.actor_role.toLowerCase()}
                    </span>
                  </div>
                  <p className="mt-0.5 text-2xs leading-relaxed text-ink-muted">{e.summary}</p>
                  {e.evidence_refs?.length ? (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {e.evidence_refs.slice(0, 4).map((r: any, i: number) => (
                        <span
                          key={i}
                          className="rounded bg-canvas-sunken px-1.5 py-0.5 font-mono text-[10px] text-ink-subtle"
                        >
                          {r.kind}
                          {r.page ? ` p${r.page}` : ""}
                          {r.label ? ` · ${String(r.label).slice(0, 40)}` : ""}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
                <time
                  className="shrink-0 text-2xs text-ink-subtle"
                  title={dateTime(e.created_at)}
                  dateTime={e.created_at}
                >
                  {relative(e.created_at)}
                </time>
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}
