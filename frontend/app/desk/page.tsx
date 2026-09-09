"use client";

/**
 * The verification desk.
 *
 * One route, three views, chosen by role — because the three jobs are stages of
 * the same workflow and splitting them across three URLs would hide that. A
 * verifier examines the documents the pipeline flagged; the legal reviewer who
 * supervises them sees the desk's record and owns the escalated cases; the
 * administrator sees the whole estate.
 *
 * Nothing here can mark a claim verified. A verifier records what the original
 * document showed; the resolver still decides what the evidence set supports.
 */

import {
  BadgeCheck,
  ClipboardList,
  FileWarning,
  Gavel,
  Lock,
  ShieldCheck,
  TrendingUp,
  Users,
} from "lucide-react";
import Link from "next/link";
import React from "react";

import { useApi, useCapabilities, useRole } from "@/components/hooks";
import {
  BandBadge,
  Button,
  Card,
  CardHeader,
  Chip,
  Disclaimer,
  EmptyState,
  ErrorState,
  LoadingCard,
  SectionHeading,
  StateBadge,
  StatTile,
} from "@/components/ui";
import { api, endpoints } from "@/lib/api";
import { cn } from "@/lib/format";

export default function DeskPage() {
  const [role] = useRole();
  const caps = useCapabilities();

  // `can` is permissive until the capability table arrives, which is right for a
  // button (the server refuses an early click anyway) and wrong here: this page
  // chooses *which view* to render, so an optimistic answer would flash the
  // administrator's estate view at a buyer before correcting itself.
  const ready = caps.ready;
  const isVerifier = ready && caps.can("RECORD_FINDING");
  const isSupervisor = ready && caps.can("SUPERVISE_DESK");
  const isHead = ready && caps.can("PLATFORM_OVERSIGHT");

  return (
    <div className="space-y-6 pb-6">
      <SectionHeading
        eyebrow="Verification desk"
        title={
          isHead
            ? "The whole estate, and the desk working it"
            : isSupervisor
              ? "Your verifiers, and the cases the platform refused to decide"
              : isVerifier
                ? "Properties on your desk"
                : "The verification desk"
        }
        description="The platform derives every claim's status from evidence. This is the human work around that: who is responsible for a file, what an examination established, and who owns a case the machine declined to decide."
      />

      {!ready ? <LoadingCard /> : null}

      {ready && !isVerifier && !isSupervisor && !isHead ? (
        <Card className="p-6">
          <EmptyState
            icon={<Lock className="h-5 w-5" />}
            title="This desk belongs to the verification team"
            description="Switch to Verifier, Legal Reviewer or Administrator in the role selector to open it. As a buyer or owner you see the outcome of this work on the property pages, not the queue behind it."
          />
        </Card>
      ) : null}

      {isVerifier ? <VerifierQueue /> : null}
      {isSupervisor ? <SupervisorView /> : null}
      {isHead ? <HeadOverview /> : null}

      <Disclaimer />
    </div>
  );
}

/* ------------------------------------------------------------- the verifier */

function VerifierQueue() {
  const q = useApi<any>(() => endpoints.deskQueue(), []);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [note, setNote] = React.useState("");
  const [error, setError] = React.useState<string>("");

  if (q.loading) return <LoadingCard />;
  if (q.error) return <ErrorState error={q.error} onRetry={q.refetch} />;
  const data = q.data;

  const record = async (propertyId: string, documentId: string | null, outcome: string) => {
    setBusy(`${propertyId}:${documentId}`);
    setError("");
    try {
      await endpoints.recordFinding({
        property_id: propertyId,
        document_id: documentId,
        outcome,
        note,
      });
      setNote("");
      q.refetch();
    } catch (e: any) {
      setError(e?.detail || "Could not record the finding.");
    } finally {
      setBusy(null);
    }
  };

  const signOff = async (assignmentId: string) => {
    setBusy(assignmentId);
    setError("");
    try {
      await endpoints.signOff(assignmentId);
      q.refetch();
    } catch (e: any) {
      setError(e?.detail || "Could not sign off.");
    } finally {
      setBusy(null);
    }
  };

  const outstanding = data.assignments.reduce(
    (n: number, a: any) => n + a.outstanding,
    0,
  );

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <StatTile label="On your desk" value={data.assignments.length} icon={<ClipboardList className="h-4 w-4" />} hint="Properties you are responsible for" />
        <StatTile
          label="Documents to examine"
          value={outstanding}
          tone={outstanding ? "warn" : undefined}
          icon={<FileWarning className="h-4 w-4" />}
          hint="Flagged by the pipeline, not yet examined"
        />
        <StatTile
          label="Signed off"
          value={data.assignments.filter((a: any) => a.status === "COMPLETED").length}
          icon={<BadgeCheck className="h-4 w-4" />}
          hint="Closed, with the state recorded"
        />
      </div>

      <Card className="bg-status-infoBg p-4 ring-1 ring-status-info/15">
        <p className="text-[13px] leading-relaxed text-ink">{data.note}</p>
      </Card>

      {error ? (
        <Card className="border-status-conflicting/30 bg-status-conflictingBg p-4">
          <p className="text-sm text-status-conflicting">{error}</p>
        </Card>
      ) : null}

      {data.assignments.length === 0 ? (
        <Card className="p-6">
          <EmptyState title="Nothing assigned" description="No property is currently on your desk." />
        </Card>
      ) : null}

      {data.assignments.map((a: any) => (
        <Card key={a.assignment_id}>
          <CardHeader
            title={`${a.property.reference} · Survey ${a.property.survey_number}`}
            subtitle={`${a.property.village}, ${a.property.district} · ${a.property.scenario_label}`}
            action={
              <div className="flex flex-wrap items-center gap-2">
                {a.transaction_state ? <StateBadge state={a.transaction_state} size="sm" /> : null}
                {a.risk_band ? <BandBadge band={a.risk_band} /> : null}
                <Chip tone={a.status === "COMPLETED" ? "emerald" : "neutral"}>{a.status_label}</Chip>
                {a.onboarded_by_me ? <Chip tone="navy">onboarded by you</Chip> : null}
              </div>
            }
          />
          <div className="space-y-3 p-4">
            {a.documents_to_examine.length === 0 ? (
              <p className="text-[13px] text-ink-muted">
                The pipeline raised no integrity indicator on this file, so there is nothing to
                examine against an original.
              </p>
            ) : (
              a.documents_to_examine.map((d: any) => (
                <div key={d.id} className="rounded-xl border border-canvas-border p-3.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-[13px] font-semibold text-ink">{d.filename}</p>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {d.indicators.map((code: string) => (
                          <Chip key={code} tone="red">{code}</Chip>
                        ))}
                      </div>
                    </div>
                    {d.examined ? <Chip tone="emerald">examined</Chip> : null}
                  </div>
                  {!d.examined ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {data.outcomes.map((o: any) => (
                        <Button
                          key={o.key}
                          size="sm"
                          variant="secondary"
                          disabled={busy !== null}
                          onClick={() => record(a.property.id, d.id, o.key)}
                        >
                          {o.label}
                        </Button>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))
            )}

            {a.findings.length ? (
              <div className="rounded-xl bg-canvas-sunken p-3.5">
                <div className="section-label mb-2">Findings recorded</div>
                {a.findings.map((f: any) => (
                  <div key={f.id} className="mb-1.5 text-2xs text-ink-muted">
                    <span className="font-medium text-ink">{f.outcome_label}</span>
                    {f.agrees_with_platform === true ? (
                      <Chip tone="emerald" className="ml-2">agrees with the pipeline</Chip>
                    ) : f.agrees_with_platform === false ? (
                      <Chip tone="amber" className="ml-2">differs from the pipeline</Chip>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-2">
              <Link href={`/properties/${a.property.reference}`}>
                <Button variant="secondary" size="sm">Open the full file</Button>
              </Link>
              {a.status !== "COMPLETED" ? (
                <Button
                  size="sm"
                  disabled={busy !== null || a.outstanding > 0}
                  title={
                    a.outstanding > 0
                      ? "Examine every flagged document before signing off."
                      : "Closes the assignment and records the state it was closed in."
                  }
                  onClick={() => signOff(a.assignment_id)}
                >
                  Sign off
                </Button>
              ) : (
                <span className="text-2xs text-ink-subtle">
                  Signed off in state {a.state_at_signoff}
                </span>
              )}
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

/* ----------------------------------------------------------- the supervisor */

function SupervisorView() {
  const team = useApi<any>(() => endpoints.deskTeam(), []);
  const esc = useApi<any>(() => endpoints.deskEscalations(), []);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [reasoning, setReasoning] = React.useState("");
  const [error, setError] = React.useState("");

  const decide = async (propertyId: string, outcome: string) => {
    setBusy(propertyId);
    setError("");
    try {
      await endpoints.recordDetermination({
        property_id: propertyId,
        outcome,
        reasoning,
      });
      setReasoning("");
      esc.refetch();
    } catch (e: any) {
      setError(e?.detail || "Could not record the determination.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <div className="section-label mb-2">1 · The desk</div>
        {team.loading ? <LoadingCard /> : team.error ? (
          <ErrorState error={team.error} onRetry={team.refetch} />
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile label="Verifiers" value={team.data.totals.verifiers} icon={<Users className="h-4 w-4" />} />
              <StatTile label="Properties handled" value={team.data.totals.properties_handled} hint={`${team.data.totals.properties_onboarded} onboarded through the desk`} />
              <StatTile
                label="Agreement with the pipeline"
                value={team.data.totals.desk_agreement_rate === null ? "—" : `${team.data.totals.desk_agreement_rate}%`}
                icon={<TrendingUp className="h-4 w-4" />}
                hint="Examinations that matched the automated indicators"
              />
              <StatTile
                label="Sign-offs since reversed"
                value={team.data.totals.regressions}
                tone={team.data.totals.regressions ? "danger" : undefined}
                hint="What a buyer feels as the platform changing its mind"
              />
            </div>

            <Card className="mt-3">
              <CardHeader title="Each verifier's record" subtitle={team.data.note} />
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[13px]">
                  <thead className="bg-canvas-sunken text-2xs uppercase tracking-wider text-ink-muted">
                    <tr>
                      <th className="px-4 py-2.5">Verifier</th>
                      <th className="px-4 py-2.5">Handled</th>
                      <th className="px-4 py-2.5">Signed off</th>
                      <th className="px-4 py-2.5">Onboarded</th>
                      <th className="px-4 py-2.5">Open</th>
                      <th className="px-4 py-2.5">Agreement</th>
                      <th className="px-4 py-2.5">Reversed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {team.data.verifiers.map((v: any) => (
                      <tr key={v.verifier.id} className="border-t border-canvas-border">
                        <td className="px-4 py-2.5">
                          <div className="font-medium text-ink">{v.verifier.name}</div>
                          <div className="text-2xs text-ink-subtle">{v.verifier.organisation}</div>
                        </td>
                        <td className="px-4 py-2.5 tnum">{v.handled}</td>
                        <td className="px-4 py-2.5 tnum">{v.completed}</td>
                        <td className="px-4 py-2.5 tnum">{v.onboarded}</td>
                        <td className="px-4 py-2.5 tnum">{v.open}</td>
                        <td className="px-4 py-2.5 tnum">
                          {v.agreement_rate === null ? (
                            <span className="text-ink-subtle">no findings yet</span>
                          ) : (
                            <span className={cn(v.agreement_rate < 60 && "text-status-partial")}>
                              {v.agreement_rate}%
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 tnum">
                          {v.regression_count ? (
                            <span className="text-status-conflicting">{v.regression_count}</span>
                          ) : (
                            "0"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )}
      </div>

      <div>
        <div className="section-label mb-2">2 · Escalated cases</div>
        {esc.loading ? <LoadingCard /> : esc.error ? (
          <ErrorState error={esc.error} onRetry={esc.refetch} />
        ) : (
          <>
            <Card className="mb-3 bg-status-infoBg p-4 ring-1 ring-status-info/15">
              <p className="text-[13px] leading-relaxed text-ink">{esc.data.note}</p>
            </Card>
            {error ? (
              <Card className="mb-3 border-status-conflicting/30 bg-status-conflictingBg p-4">
                <p className="text-sm text-status-conflicting">{error}</p>
              </Card>
            ) : null}
            {esc.data.items.length === 0 ? (
              <Card className="p-6">
                <EmptyState title="No escalated cases" description="The platform has not refused to decide any file on the current evidence." />
              </Card>
            ) : null}
            {esc.data.items.map((item: any) => (
              <Card key={item.property_id} className="mb-3">
                <CardHeader
                  title={`${item.reference} · Survey ${item.survey_number}`}
                  subtitle={`${item.village}, ${item.district} · ${item.scenario_label}`}
                  action={
                    <div className="flex items-center gap-2">
                      <StateBadge state={item.state} size="sm" />
                      {item.risk_band ? <BandBadge band={item.risk_band} /> : null}
                    </div>
                  }
                />
                <div className="space-y-3 p-4">
                  <p className="text-[13px] leading-relaxed text-ink-muted">{item.state_reason}</p>
                  {item.assigned_verifier ? (
                    <p className="text-2xs text-ink-subtle">
                      Verifier on this file: <span className="font-medium text-ink">{item.assigned_verifier.name}</span>
                    </p>
                  ) : null}

                  {item.determination ? (
                    <div className="rounded-xl bg-status-verifiedBg p-3.5 ring-1 ring-status-verified/20">
                      <div className="section-label text-status-verified">Determination recorded</div>
                      <p className="mt-1 text-[13px] font-medium text-ink">{item.determination.outcome}</p>
                      {item.determination.reasoning ? (
                        <p className="mt-1 text-2xs leading-relaxed text-ink-muted">{item.determination.reasoning}</p>
                      ) : null}
                      <p className="mt-1.5 text-2xs text-ink-subtle">by {item.determination.reviewer}</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <textarea
                        rows={2}
                        value={reasoning}
                        onChange={(e) => setReasoning(e.target.value)}
                        placeholder="Your reasoning — recorded with the determination in the audit trail."
                        className="w-full rounded-lg border border-canvas-border bg-canvas-raised px-3 py-2 text-[13px] text-ink outline-none focus:border-navy-400"
                      />
                      <div className="flex flex-wrap gap-2">
                        {esc.data.outcomes.map((o: any) => (
                          <Button
                            key={o.key}
                            size="sm"
                            variant="secondary"
                            disabled={busy !== null}
                            onClick={() => decide(item.property_id, o.key)}
                          >
                            {o.label}
                          </Button>
                        ))}
                      </div>
                    </div>
                  )}
                  <Link href={`/properties/${item.reference}`}>
                    <Button variant="secondary" size="sm">Examine the full file</Button>
                  </Link>
                </div>
              </Card>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ the head */

function HeadOverview() {
  const q = useApi<any>(() => endpoints.deskOverview(), []);
  if (q.loading) return <LoadingCard />;
  if (q.error) return <ErrorState error={q.error} onRetry={q.refetch} />;
  const d = q.data;

  const tone = (s: string) =>
    s === "HIGH" ? "red" : s === "MEDIUM" ? "amber" : s === "INFO" ? "emerald" : "neutral";

  return (
    <div className="space-y-5">
      <div>
        <div className="section-label mb-2">Requires attention</div>
        <Card className="divide-y divide-canvas-border">
          {d.attention.map((a: any, i: number) => (
            <div key={i} className="flex items-start gap-3 p-4">
              <Chip tone={tone(a.severity) as any}>{a.severity}</Chip>
              <div className="min-w-0">
                <p className="text-[13px] font-semibold text-ink">{a.title}</p>
                <p className="mt-0.5 text-2xs leading-relaxed text-ink-muted">{a.detail}</p>
              </div>
            </div>
          ))}
        </Card>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Properties" value={d.estate.properties} icon={<ShieldCheck className="h-4 w-4" />} hint={`${d.estate.documents} documents on file`} />
        <StatTile label="Assigned" value={d.estate.assigned} tone={d.estate.unassigned ? "warn" : undefined} hint={`${d.estate.unassigned} with no verifier`} />
        <StatTile label="Verifiers" value={d.desk.verifiers} icon={<Users className="h-4 w-4" />} hint={`${d.desk.open} assignments open`} />
        <StatTile
          label="Escalations open"
          value={d.escalations.awaiting_determination}
          tone={d.escalations.awaiting_determination ? "danger" : undefined}
          icon={<Gavel className="h-4 w-4" />}
          hint={`${d.escalations.total} escalated in total`}
        />
      </div>

      <Card>
        <CardHeader title="The estate by transaction state" subtitle="Where every property currently stands." />
        <div className="flex flex-wrap gap-3 p-4">
          {Object.entries(d.estate.by_transaction_state).map(([state, count]: any) => (
            <div key={state} className="rounded-xl border border-canvas-border px-4 py-3">
              <StateBadge state={state} size="sm" />
              <div className="tnum mt-1.5 text-xl font-semibold text-ink">{count}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="The desk" subtitle="Every verifier, and what their record shows." />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <thead className="bg-canvas-sunken text-2xs uppercase tracking-wider text-ink-muted">
              <tr>
                <th className="px-4 py-2.5">Verifier</th>
                <th className="px-4 py-2.5">Handled</th>
                <th className="px-4 py-2.5">Onboarded</th>
                <th className="px-4 py-2.5">Findings</th>
                <th className="px-4 py-2.5">Agreement</th>
                <th className="px-4 py-2.5">Reversed</th>
              </tr>
            </thead>
            <tbody>
              {d.verifiers.map((v: any) => (
                <tr key={v.verifier.id} className="border-t border-canvas-border">
                  <td className="px-4 py-2.5 font-medium text-ink">{v.verifier.name}</td>
                  <td className="px-4 py-2.5 tnum">{v.handled}</td>
                  <td className="px-4 py-2.5 tnum">{v.onboarded}</td>
                  <td className="px-4 py-2.5 tnum">{v.findings}</td>
                  <td className="px-4 py-2.5 tnum">
                    {v.agreement_rate === null ? "—" : `${v.agreement_rate}%`}
                  </td>
                  <td className="px-4 py-2.5 tnum">{v.regression_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
