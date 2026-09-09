"use client";

import { Building2, MapPin, Search, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import React from "react";

import { useApi } from "@/components/hooks";
import { ListPropertyButton } from "@/components/list-property";
import {
  BandBadge,
  Card,
  Chip,
  Disclaimer,
  EmptyState,
  ErrorState,
  SectionHeading,
  Skeleton,
  StateBadge,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import { STATE_META, type TransactionState } from "@/lib/domain";
import { cn, inr, pct, relative, sqft } from "@/lib/format";

const STATES: TransactionState[] = ["PROCEED", "WARN", "HOLD", "ESCALATE", "REJECT"];

export default function PropertiesPage() {
  const { data, error, loading, refetch } = useApi<any>(() => endpoints.properties(), []);
  const [query, setQuery] = React.useState("");
  const [state, setState] = React.useState<TransactionState | null>(null);

  const items: any[] = React.useMemo(() => {
    let rows: any[] = data?.items ?? [];
    if (state) rows = rows.filter((p) => p.transaction_state === state);
    if (query.trim()) {
      const q = query.toLowerCase();
      rows = rows.filter(
        (p) =>
          p.reference.toLowerCase().includes(q) ||
          p.survey_number.toLowerCase().includes(q) ||
          (p.village || "").toLowerCase().includes(q) ||
          (p.district || "").toLowerCase().includes(q) ||
          (p.scenario_label || "").toLowerCase().includes(q),
      );
    }
    return rows;
  }, [data, state, query]);

  if (error) return <ErrorState error={error} onRetry={refetch} />;

  const counts: Record<string, number> = {};
  for (const p of data?.items ?? []) {
    counts[p.transaction_state] = (counts[p.transaction_state] || 0) + 1;
  }

  return (
    <div className="space-y-6">
      {/*
        The listing control sits here as well as in the owner portal. An owner
        following "My properties" in the sidebar arrives on this page, and a
        button that lives only on a different page is a button they will not
        find. It disables itself for every other role.
      */}
      <SectionHeading
        eyebrow="Workspace"
        title="Properties"
        description="Every file on the platform, from a fully corroborated title to one it refuses to let progress. Open any of them to see the evidence behind every figure."
        action={<ListPropertyButton onCreated={refetch} />}
      />

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search reference, survey number, village or scenario…"
            className="w-full rounded-lg border border-canvas-borderStrong bg-canvas-raised py-2 pl-9 pr-3 text-sm text-ink placeholder:text-ink-subtle"
          />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <SlidersHorizontal className="mr-1 h-3.5 w-3.5 text-ink-subtle" />
          <Chip tone={state === null ? "navy" : "neutral"} onClick={() => setState(null)} active={state === null}>
            All {data ? `· ${data.items.length}` : ""}
          </Chip>
          {STATES.filter((s) => counts[s]).map((s) => (
            <Chip
              key={s}
              tone={state === s ? "navy" : "neutral"}
              onClick={() => setState(state === s ? null : s)}
              active={state === s}
            >
              {STATE_META[s].label} · {counts[s]}
            </Chip>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[248px]" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="No properties match"
          description="Clear the search or filter to see the full corpus."
          icon={<Building2 className="h-5 w-5" />}
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((p) => (
            <PropertyCard key={p.id} property={p} />
          ))}
        </div>
      )}

      <Disclaimer />
    </div>
  );
}

function PropertyCard({ property: p }: { property: any }) {
  const conflicting = p.verification_counts?.CONFLICTING ?? 0;
  const verified = p.verification_counts?.VERIFIED ?? 0;

  return (
    <Link href={`/properties/${p.reference}`} className="group block">
      <Card className="flex h-full flex-col overflow-hidden transition group-hover:-translate-y-0.5 group-hover:shadow-raised">
        {/* A hairline in the state colour: the file's status is readable before any text. */}
        <div
          className={cn(
            "h-1 w-full",
            {
              PROCEED: "bg-risk-low",
              WARN: "bg-risk-moderate",
              HOLD: "bg-risk-high",
              ESCALATE: "bg-risk-critical",
              REJECT: "bg-risk-critical",
            }[p.transaction_state as TransactionState] ?? "bg-canvas-borderStrong",
          )}
        />
        <div className="flex flex-1 flex-col p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="font-mono text-2xs text-ink-subtle">{p.reference}</div>
              <h3 className="mt-0.5 truncate text-[15px] font-semibold text-ink">
                {p.scenario_label}
              </h3>
            </div>
            {p.transaction_state ? <StateBadge state={p.transaction_state} size="sm" /> : null}
          </div>

          <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-2xs text-ink-muted">
            <span className="inline-flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {p.village}, {p.district}
            </span>
            <span>Survey {p.survey_number}</span>
            <span>{sqft(p.claimed_area_sqft)}</span>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3">
            <div>
              <div className="section-label">Composite risk</div>
              <div className="mt-1 flex items-center gap-2">
                <span className="tnum text-2xl font-semibold tracking-tight text-ink">
                  {p.risk_score !== null ? Math.round(p.risk_score) : "—"}
                </span>
                {p.risk_band ? <BandBadge band={p.risk_band} /> : null}
              </div>
            </div>
            <div>
              <div className="section-label">Asking price</div>
              <div className="tnum mt-1 text-sm font-medium text-ink">
                {inr(p.asking_price_inr, { compact: true })}
              </div>
              <div className="tnum text-2xs text-ink-subtle">
                guideline {inr(p.guideline_value_inr, { compact: true })}
              </div>
            </div>
          </div>

          <div className="mt-4">
            <div className="flex items-center justify-between text-2xs">
              <span className="section-label">Core claims verified</span>
              <span className="tnum font-medium text-ink-muted">
                {pct(p.verification_level)}
              </span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-canvas-sunken">
              <div
                className="h-full rounded-full bg-status-verified transition-all"
                style={{ width: `${(p.verification_level || 0) * 100}%` }}
              />
            </div>
          </div>

          <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-4">
            <Chip tone="neutral">{p.document_count} documents</Chip>
            <Chip tone="neutral">{p.claim_count} claims</Chip>
            {verified > 0 ? <Chip tone="emerald">{verified} verified</Chip> : null}
            {p.contradiction_count > 0 ? (
              <Chip tone="red">
                {p.contradiction_count} contradiction{p.contradiction_count === 1 ? "" : "s"}
              </Chip>
            ) : null}
          </div>

          <div className="mt-3 flex items-center justify-between border-t border-canvas-border pt-3 text-2xs text-ink-subtle">
            <span>Listed by {p.listed_owner_name}</span>
            <span>{relative(p.updated_at)}</span>
          </div>
        </div>
      </Card>
    </Link>
  );
}
