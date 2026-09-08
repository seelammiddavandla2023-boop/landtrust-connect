"use client";

/**
 * Buyer portal index.
 *
 * The point of this screen is comparison: six listings that look equally confident
 * on a classifieds site are separated here by what their documents actually support.
 */

import { motion } from "framer-motion";
import {
  ArrowRight,
  Building2,
  CircleAlert,
  MapPin,
  Ruler,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import React from "react";

import { useApi, useQueryParam, useRole } from "@/components/hooks";
import {
  BandBadge,
  Card,
  Chip,
  Disclaimer,
  EmptyState,
  ErrorState,
  LoadingCard,
  SectionHeading,
  StateBadge,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import { STATE_META, type RiskBand, type TransactionState } from "@/lib/domain";
import { cn, inr, pct, sqft } from "@/lib/format";

type PropertySummary = {
  id: string;
  reference: string;
  survey_number: string;
  district: string;
  village: string;
  state: string;
  property_type: string;
  claimed_area_sqft: number | null;
  asking_price_inr: number | null;
  guideline_value_inr: number | null;
  scenario_label: string;
  document_count: number;
  contradiction_count: number;
  critical_contradictions: number;
  verification_level: number;
  verification_counts: Record<string, number>;
  risk_score: number;
  risk_band: RiskBand;
  transaction_state: TransactionState;
};

const STATE_ORDER: TransactionState[] = ["PROCEED", "WARN", "HOLD", "ESCALATE", "REJECT"];

export default function BuyerIndexPage() {
  const [role] = useRole();
  const [filter, setFilter] = useQueryParam("state", "ALL");
  const { data, error, loading, refetch } = useApi<{ count: number; items: PropertySummary[] }>(
    () => endpoints.properties(),
    [role],
  );

  const items = data?.items ?? [];
  const counts = React.useMemo(() => {
    const map: Record<string, number> = {};
    for (const p of items) map[p.transaction_state] = (map[p.transaction_state] ?? 0) + 1;
    return map;
  }, [items]);

  const visible = filter === "ALL" ? items : items.filter((p) => p.transaction_state === filter);

  return (
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Buyer portal"
        title="Listings, sorted by what the evidence supports"
        description="Every field a buyer sees on this platform carries its verification status. Open a property to see the same profile the seller published, split into what the documents corroborate, what they only partially support, what they contradict, and what is nothing more than the owner's word."
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-4">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-status-verifiedBg text-status-verified">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <div>
              <p className="text-[13px] font-semibold text-ink">Evidence before presentation</p>
              <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
                A value is shown as verified only when independent documents agree, or the
                authority of record for that attribute says so.
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-status-conflictingBg text-status-conflicting">
              <CircleAlert className="h-4 w-4" />
            </div>
            <div>
              <p className="text-[13px] font-semibold text-ink">Conflicts stay visible</p>
              <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
                Where documents disagree, the buyer sees both figures and the difference — the
                platform does not quietly pick a winner.
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-navy-50 text-navy-700">
              <Building2 className="h-4 w-4" />
            </div>
            <div>
              <p className="text-[13px] font-semibold text-ink">State is enforced, not advisory</p>
              <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
                A held or escalated transaction refuses progression on the server, and tells the
                buyer exactly which rule refused it.
              </p>
            </div>
          </div>
        </Card>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="section-label mr-1">Transaction state</span>
        <Chip tone="navy" active={filter === "ALL"} onClick={() => setFilter("ALL")}>
          All
          <span className="tnum text-navy-500">{items.length}</span>
        </Chip>
        {STATE_ORDER.map((s) => (
          <Chip
            key={s}
            tone="neutral"
            active={filter === s}
            onClick={() => setFilter(s)}
            className={cn(counts[s] ? STATE_META[s].fg : "opacity-60")}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", STATE_META[s].dot)} />
            {STATE_META[s].label}
            <span className="tnum">{counts[s] ?? 0}</span>
          </Chip>
        ))}
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <LoadingCard key={i} rows={6} />
          ))}
        </div>
      ) : error ? (
        <ErrorState error={error} onRetry={refetch} />
      ) : visible.length === 0 ? (
        <EmptyState
          title="No properties in this state"
          description="Clear the filter to see every listing in the synthetic corpus."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((p, i) => (
            <PropertyCard key={p.id} property={p} index={i} />
          ))}
        </div>
      )}

      <Disclaimer />
    </div>
  );
}

function PropertyCard({ property: p, index }: { property: PropertySummary; index: number }) {
  const verified = p.verification_counts?.VERIFIED ?? 0;
  const conflicting = p.verification_counts?.CONFLICTING ?? 0;
  const level = Math.round((p.verification_level ?? 0) * 100);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.04, 0.24) }}
    >
      <Link href={`/buyer/${p.reference}`} className="group block h-full">
        <Card className="flex h-full flex-col p-5 transition group-hover:-translate-y-0.5 group-hover:shadow-raised">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="font-mono text-[13px] font-semibold text-navy-700">
                {p.reference}
              </div>
              <p className="mt-1 text-[15px] font-semibold leading-tight text-ink">
                {p.property_type}
              </p>
              <p className="mt-0.5 text-2xs uppercase tracking-[0.1em] text-ink-subtle">
                {p.scenario_label}
              </p>
            </div>
            <StateBadge state={p.transaction_state} size="sm" />
          </div>

          <dl className="mt-4 grid grid-cols-2 gap-3 text-[13px]">
            <div>
              <dt className="section-label">Survey no.</dt>
              <dd className="mt-1 font-mono text-ink">{p.survey_number}</dd>
            </div>
            <div>
              <dt className="section-label">Area (claimed)</dt>
              <dd className="tnum mt-1 text-ink">
                <Ruler className="mr-1 inline h-3.5 w-3.5 text-ink-subtle" />
                {sqft(p.claimed_area_sqft)}
              </dd>
            </div>
            <div className="col-span-2">
              <dt className="section-label">Location</dt>
              <dd className="mt-1 text-ink">
                <MapPin className="mr-1 inline h-3.5 w-3.5 text-ink-subtle" />
                {p.village}, {p.district} · {p.state}
              </dd>
            </div>
            <div className="col-span-2">
              <dt className="section-label">Asking price</dt>
              <dd className="tnum mt-1 text-[15px] font-semibold text-ink">
                <Wallet className="mr-1.5 inline h-3.5 w-3.5 text-ink-subtle" />
                {inr(p.asking_price_inr)}
                <span className="ml-2 text-2xs font-normal text-ink-subtle">
                  guideline {inr(p.guideline_value_inr, { compact: true })}
                </span>
              </dd>
            </div>
          </dl>

          <div className="mt-4">
            <div className="flex items-center justify-between text-2xs font-medium text-ink-muted">
              <span className="section-label">Verification level</span>
              <span className="tnum">{pct(p.verification_level)}</span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-canvas-sunken">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  level >= 70
                    ? "bg-status-verified"
                    : level >= 40
                      ? "bg-status-partial"
                      : "bg-status-conflicting",
                )}
                style={{ width: `${Math.max(level, 2)}%` }}
              />
            </div>
            <p className="mt-1.5 text-2xs text-ink-subtle">
              Share of profile attributes that reach verified on the current evidence.
            </p>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-canvas-border pt-4">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-status-verifiedBg px-2 py-0.5 text-2xs font-semibold text-status-verified ring-1 ring-status-verified/20">
              <span className="tnum">{verified}</span> verified
            </span>
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-2xs font-semibold ring-1",
                conflicting
                  ? "bg-status-conflictingBg text-status-conflicting ring-status-conflicting/20"
                  : "bg-canvas-sunken text-ink-subtle ring-canvas-border",
              )}
            >
              <span className="tnum">{conflicting}</span> conflicting
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-canvas-sunken px-2 py-0.5 text-2xs font-medium text-ink-muted ring-1 ring-canvas-border">
              <span className="tnum">{p.contradiction_count}</span> contradictions
            </span>
          </div>

          <div className="mt-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <BandBadge band={p.risk_band} />
              <span className="tnum text-2xs text-ink-subtle">{Math.round(p.risk_score)}/100</span>
            </div>
            <span className="inline-flex items-center gap-1 text-[13px] font-medium text-navy-700 transition group-hover:gap-2">
              Open profile
              <ArrowRight className="h-3.5 w-3.5" />
            </span>
          </div>
        </Card>
      </Link>
    </motion.div>
  );
}
