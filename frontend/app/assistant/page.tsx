"use client";

/**
 * AI Evidence Assistant.
 *
 * The point of this screen is not that it answers. It is that it refuses.
 *
 * A grounded answer arrives with the document, page and confidence behind every
 * sentence. When the file holds no record that bears on the question, the assistant
 * declines instead of inferring — and a decline is rendered here as a composed,
 * deliberate outcome, never as an error. The second row of suggested questions exists
 * specifically so a reviewer can trigger that behaviour on purpose.
 */

import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowUp,
  BookOpen,
  CircleSlash,
  FileSearch,
  FolderOpen,
  Info,
  ListFilter,
  Loader2,
  MessageSquare,
  Quote,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";
import React from "react";

import { useApi, useQueryParam } from "@/components/hooks";
import {
  BandBadge,
  Button,
  Card,
  CardHeader,
  Chip,
  ConfidenceBar,
  DemoDataBadge,
  Disclaimer,
  EmptyState,
  ErrorState,
  EvidenceChip,
  LoadingCard,
  SectionHeading,
  Skeleton,
  StateBadge,
  StatusBadge,
  Tooltip,
} from "@/components/ui";
import { ApiError, endpoints } from "@/lib/api";
import { DISCLAIMER, type VerificationStatus } from "@/lib/domain";
import { cn, dateTime, pct, relative, titleise } from "@/lib/format";

/* ------------------------------------------------------------------- types */

type AnswerKind = "GROUNDED" | "REFUSED" | "OUT_OF_SCOPE";

type Citation = {
  kind: string;
  document_id: string | null;
  document_name: string;
  page: number | null;
  confidence: number | null;
  excerpt: string;
  claim_id: string | null;
  verification_status: VerificationStatus | null;
};

type Answer = {
  kind: AnswerKind;
  answer: string;
  confidence: number;
  intent: string;
  evidence: Citation[];
  caveats: string[];
  backend: string;
  disclaimer: string;
};

type Turn = {
  id: string;
  question: string;
  answer: Answer | null;
  error: string | null;
  askedAt: string;
};

type LogEntry = {
  id: string;
  question: string;
  intent: string;
  answer_kind: AnswerKind;
  answer: string;
  confidence: number;
  evidence: Citation[];
  created_at: string;
};

/**
 * Questions the assistant is designed to decline.
 *
 * Held on the client on purpose: the suggestions endpoint offers what the system can
 * answer, and a reviewer also needs one click to the boundary of what it will not.
 */
const BOUNDARY_QUESTIONS = [
  "What will this property be worth in 2030?",
  "Should I buy this property?",
  "Who is the neighbouring plot's owner?",
  "Give me the owner's phone number.",
];

const KIND_META: Record<
  AnswerKind,
  { label: string; blurb: string; accent: string; ring: string; icon: React.ReactNode }
> = {
  GROUNDED: {
    label: "Grounded",
    blurb: "Every sentence below is derived from a claim or contradiction record on this file.",
    accent: "text-status-verified",
    ring: "ring-status-verified/20 bg-status-verifiedBg",
    icon: <ShieldCheck className="h-3.5 w-3.5" />,
  },
  REFUSED: {
    label: "Declined — no supporting record",
    blurb:
      "The file holds no claim that bears on this question, so the assistant declines rather than inferring an answer. This is the designed behaviour, not a failure.",
    accent: "text-status-info",
    ring: "ring-status-info/20 bg-status-infoBg",
    icon: <CircleSlash className="h-3.5 w-3.5" />,
  },
  OUT_OF_SCOPE: {
    label: "Outside scope",
    blurb:
      "The question is not one a land-evidence file can answer — valuation, legal advice and third-party personal details sit outside what this system is for.",
    accent: "text-status-owner",
    ring: "ring-status-owner/20 bg-status-ownerBg",
    icon: <ListFilter className="h-3.5 w-3.5" />,
  },
};

/* -------------------------------------------------------------------- page */

export default function AssistantPage() {
  const [propertyRef, setPropertyRef] = useQueryParam("property", "LTC-PR-0002");

  const properties = useApi<{ items: any[] }>(() => endpoints.properties(), []);
  const suggestions = useApi<{ questions: string[]; contract: string }>(
    () => endpoints.assistantSuggestions(),
    [],
  );
  const log = useApi<{ count: number; items: LogEntry[] }>(
    () => endpoints.assistantLog(propertyRef),
    [propertyRef],
  );

  const [turns, setTurns] = React.useState<Turn[]>([]);
  const [draft, setDraft] = React.useState("");
  const [pending, setPending] = React.useState(false);
  const streamRef = React.useRef<HTMLDivElement>(null);

  // A new property is a new evidence file; the transcript does not carry over.
  React.useEffect(() => {
    setTurns([]);
  }, [propertyRef]);

  React.useEffect(() => {
    streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  const ask = React.useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || pending) return;
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      setTurns((prev) => [
        ...prev,
        { id, question: trimmed, answer: null, error: null, askedAt: new Date().toISOString() },
      ]);
      setDraft("");
      setPending(true);
      try {
        const answer = (await endpoints.ask(propertyRef, trimmed)) as Answer;
        setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, answer } : t)));
        log.refetch();
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.detail
            : (err as Error)?.message || "The assistant could not be reached.";
        setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, error: message } : t)));
      } finally {
        setPending(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [propertyRef, pending],
  );

  const currentProperty = (properties.data?.items ?? []).find(
    (p: any) => p.reference === propertyRef || p.id === propertyRef,
  );

  const contract = suggestions.data?.contract;
  const disclaimer =
    turns.find((t) => t.answer?.disclaimer)?.answer?.disclaimer ?? DISCLAIMER;

  return (
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Module 6"
        title="Evidence Assistant"
        description="Ask about one property's evidence file. Answers are assembled from claim and contradiction records and cite the document and page they came from. When no such record exists the assistant declines — deliberately, and visibly."
        action={<DemoDataBadge />}
      />

      {/* The guarantee, stated before anything is asked. */}
      <Card className="border-navy-200 bg-navy-50/60 px-5 py-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-navy-900 text-white">
            <BookOpen className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="section-label">The contract</div>
            {suggestions.loading ? (
              <Skeleton className="mt-2 h-4 w-3/4" />
            ) : (
              <p className="mt-1 text-[13px] leading-relaxed text-ink">
                {contract ??
                  "Every answer is derived from records on this property's file and cites the document and page it came from."}
              </p>
            )}
          </div>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        {/* ------------------------------------------------------ chat pane */}
        <div className="space-y-4">
          <Card>
            <CardHeader
              title="Scope"
              subtitle="The assistant only ever sees one property's evidence file."
              icon={<FolderOpen className="h-4 w-4" />}
              action={
                turns.length ? (
                  <Button variant="ghost" size="sm" onClick={() => setTurns([])}>
                    <Trash2 className="h-3.5 w-3.5" />
                    Clear
                  </Button>
                ) : null
              }
            />
            <div className="space-y-3 p-5">
              {properties.loading ? (
                <Skeleton className="h-10 w-full" />
              ) : properties.error ? (
                <ErrorState error={properties.error} onRetry={properties.refetch} />
              ) : (
                <div>
                  <label className="section-label mb-1.5 block" htmlFor="assistant-property">
                    Property
                  </label>
                  <select
                    id="assistant-property"
                    value={propertyRef}
                    onChange={(e) => setPropertyRef(e.target.value)}
                    className="w-full rounded-lg border border-canvas-borderStrong bg-canvas-raised px-3 py-2 text-sm text-ink transition hover:bg-canvas-sunken"
                  >
                    {(properties.data?.items ?? []).map((p: any) => (
                      <option key={p.id} value={p.reference}>
                        {p.reference} — {p.village}, {p.district} ({p.scenario_label})
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {currentProperty ? (
                <div className="flex flex-wrap items-center gap-2">
                  <StateBadge state={currentProperty.transaction_state} size="sm" />
                  <BandBadge band={currentProperty.risk_band} />
                  <Chip tone="neutral">
                    {currentProperty.document_count} documents · {currentProperty.claim_count} claims
                  </Chip>
                  <Chip tone="neutral">
                    {currentProperty.contradiction_count} contradictions
                  </Chip>
                </div>
              ) : null}
            </div>
          </Card>

          <Card className="flex min-h-[520px] flex-col overflow-hidden">
            <CardHeader
              title="Conversation"
              subtitle={`Scoped to ${propertyRef}. Nothing outside this property's file is consulted.`}
              icon={<MessageSquare className="h-4 w-4" />}
            />

            <div ref={streamRef} className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
              {turns.length === 0 ? (
                <EmptyState
                  title="Ask something about this property's evidence"
                  description="Start with one of the suggested questions below — or pick one from the second row to see the assistant decline on purpose."
                  icon={<Sparkles className="h-5 w-5" />}
                />
              ) : (
                turns.map((turn) => (
                  <TurnBlock key={turn.id} turn={turn} onRetry={() => ask(turn.question)} />
                ))
              )}
            </div>

            <div className="border-t border-canvas-border p-4">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  ask(draft);
                }}
                className="flex items-end gap-2"
              >
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      ask(draft);
                    }
                  }}
                  rows={2}
                  placeholder={`Ask about ${propertyRef} — ownership, extent, encumbrances, missing evidence…`}
                  className="min-h-[52px] flex-1 resize-y rounded-xl border border-canvas-borderStrong bg-canvas-raised px-3.5 py-2.5 text-sm text-ink placeholder:text-ink-subtle"
                />
                <Button type="submit" disabled={pending || !draft.trim()} className="h-[52px]">
                  {pending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <ArrowUp className="h-4 w-4" />
                  )}
                  Ask
                </Button>
              </form>
              <p className="mt-2 text-2xs text-ink-subtle">
                Enter to send · Shift+Enter for a new line
              </p>
            </div>
          </Card>

          <SuggestionRows
            questions={suggestions.data?.questions ?? []}
            loading={suggestions.loading}
            error={suggestions.error}
            onRetry={suggestions.refetch}
            disabled={pending}
            onAsk={ask}
          />

          <Disclaimer text={disclaimer} />
        </div>

        {/* ------------------------------------------------------- log pane */}
        <div className="space-y-4">
          <QueryLog
            entries={log.data?.items ?? []}
            count={log.data?.count ?? 0}
            loading={log.loading}
            error={log.error}
            onRetry={log.refetch}
            onReask={ask}
          />
        </div>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------- suggestions */

function SuggestionRows({
  questions,
  loading,
  error,
  onRetry,
  disabled,
  onAsk,
}: {
  questions: string[];
  loading: boolean;
  error: any;
  onRetry: () => void;
  disabled: boolean;
  onAsk: (q: string) => void;
}) {
  return (
    <Card>
      <CardHeader
        title="Suggested questions"
        subtitle="The first row is what the evidence file can answer. The second is the boundary — click one to watch the assistant decline."
        icon={<Sparkles className="h-4 w-4" />}
      />
      <div className="space-y-4 p-5">
        <div>
          <div className="section-label mb-2">Questions it can answer from evidence</div>
          {loading ? (
            <div className="flex flex-wrap gap-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-7 w-40 rounded-full" />
              ))}
            </div>
          ) : error ? (
            <ErrorState error={error} onRetry={onRetry} />
          ) : (
            <div className="flex flex-wrap gap-2">
              {questions.map((q) => (
                <Chip key={q} tone="navy" onClick={disabled ? undefined : () => onAsk(q)}>
                  <FileSearch className="h-3 w-3" />
                  {q}
                </Chip>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="section-label mb-2 flex items-center gap-2">
            Questions it should refuse
            <Tooltip content="Refusal is the central guarantee of this system: without a supporting record on the file, no answer is produced. These four exercise the three ways that happens — no record, legal advice, out-of-file subject, and personal contact detail.">
              <Info className="h-3 w-3 cursor-help text-ink-subtle" />
            </Tooltip>
          </div>
          <div className="flex flex-wrap gap-2">
            {BOUNDARY_QUESTIONS.map((q) => (
              <Chip key={q} tone="amber" onClick={disabled ? undefined : () => onAsk(q)}>
                <CircleSlash className="h-3 w-3" />
                {q}
              </Chip>
            ))}
          </div>
          <p className="mt-2 text-2xs leading-relaxed text-ink-muted">
            A decline here is a success. The system is designed to stop rather than to
            approximate, and the response it gives says which of the two it is doing.
          </p>
        </div>
      </div>
    </Card>
  );
}

/* ----------------------------------------------------------------- a turn */

function TurnBlock({ turn, onRetry }: { turn: Turn; onRetry: () => void }) {
  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-navy-900 px-3.5 py-2.5 text-sm leading-relaxed text-white">
          {turn.question}
        </div>
      </div>

      <AnimatePresence mode="wait">
        {turn.error ? (
          <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <ErrorState error={turn.error} onRetry={onRetry} />
          </motion.div>
        ) : turn.answer ? (
          <motion.div
            key="answer"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
          >
            <AnswerBlock answer={turn.answer} />
          </motion.div>
        ) : (
          <motion.div
            key="pending"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-2 text-[13px] text-ink-muted"
          >
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Searching this property&apos;s claim and contradiction records…
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function AnswerBlock({ answer }: { answer: Answer }) {
  const meta = KIND_META[answer.kind] ?? KIND_META.GROUNDED;
  const grounded = answer.kind === "GROUNDED";

  return (
    <div
      className={cn(
        "rounded-2xl border px-4 py-4",
        grounded ? "border-canvas-border bg-canvas-raised" : "border-transparent ring-1",
        grounded ? "" : meta.ring,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span
          className={cn(
            "inline-flex items-center gap-1.5 text-2xs font-semibold uppercase tracking-[0.1em]",
            meta.accent,
          )}
        >
          {meta.icon}
          {meta.label}
        </span>
        <div className="flex items-center gap-3">
          {grounded ? (
            <Tooltip content="How strongly the supporting records agree. It is a property of the evidence, not of a language model.">
              <span className="inline-flex items-center gap-2">
                <span className="text-2xs text-ink-subtle">confidence</span>
                <ConfidenceBar value={answer.confidence} />
              </span>
            </Tooltip>
          ) : null}
          <Tooltip content={`Intent classified as ${titleise(answer.intent)}. Answering runs on the ${answer.backend} backend — no free-form generation.`}>
            <code className="cursor-help font-mono text-2xs text-ink-subtle">
              {answer.intent}
            </code>
          </Tooltip>
        </div>
      </div>

      <AnswerText text={answer.answer} />

      {!grounded ? (
        <p className="mt-3 flex items-start gap-2 rounded-xl bg-canvas-raised/70 px-3 py-2 text-2xs leading-relaxed text-ink-muted">
          <Info className="mt-px h-3.5 w-3.5 shrink-0 text-ink-subtle" />
          <span>{meta.blurb}</span>
        </p>
      ) : null}

      {answer.caveats?.length ? (
        <div className="mt-3">
          <div className="section-label mb-1.5">Caveats</div>
          <ul className="space-y-1">
            {answer.caveats.map((c, i) => (
              <li key={i} className="text-2xs leading-relaxed text-ink-muted">
                {c}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {grounded ? (
        <div className="mt-4 border-t border-canvas-border pt-3">
          <div className="section-label mb-2">
            Evidence · {answer.evidence?.length ?? 0} citation
            {(answer.evidence?.length ?? 0) === 1 ? "" : "s"}
          </div>
          {answer.evidence?.length ? (
            <ul className="space-y-2.5">
              {answer.evidence.map((cite, i) => (
                <CitationRow key={`${cite.claim_id ?? cite.document_name}-${i}`} cite={cite} />
              ))}
            </ul>
          ) : (
            <p className="text-2xs leading-relaxed text-ink-muted">
              This answer summarises the file&apos;s own state rather than quoting one record, so
              it carries no per-document citation.
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}

/** Preserves the newlines and "• " bullets the API returns, without inventing markup. */
function AnswerText({ text }: { text: string }) {
  const lines = (text ?? "").split("\n");
  return (
    <div className="mt-2.5 space-y-1.5">
      {lines.map((line, i) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={i} className="h-1.5" />;
        if (trimmed.startsWith("• ")) {
          return (
            <div key={i} className="flex items-start gap-2 pl-1">
              <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-ink-subtle" />
              <span className="text-sm leading-relaxed text-ink">{trimmed.slice(2)}</span>
            </div>
          );
        }
        return (
          <p key={i} className="text-sm leading-relaxed text-ink">
            {trimmed}
          </p>
        );
      })}
    </div>
  );
}

function CitationRow({ cite }: { cite: Citation }) {
  return (
    <li className="rounded-xl bg-canvas-sunken/70 px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <EvidenceChip
          document={cite.document_name}
          page={cite.page}
          confidence={cite.confidence}
        />
        <Chip tone="neutral">{titleise(cite.kind)}</Chip>
        {cite.verification_status ? (
          <StatusBadge status={cite.verification_status} size="sm" />
        ) : null}
      </div>
      {cite.excerpt ? (
        <p className="mt-2 flex items-start gap-1.5 font-mono text-2xs leading-relaxed text-ink-muted">
          <Quote className="mt-0.5 h-3 w-3 shrink-0 text-ink-subtle" />
          <span>{cite.excerpt}</span>
        </p>
      ) : null}
    </li>
  );
}

/* -------------------------------------------------------------- query log */

function QueryLog({
  entries,
  count,
  loading,
  error,
  onRetry,
  onReask,
}: {
  entries: LogEntry[];
  count: number;
  loading: boolean;
  error: any;
  onRetry: () => void;
  onReask: (q: string) => void;
}) {
  const tally = React.useMemo(() => {
    const acc: Record<string, number> = { GROUNDED: 0, REFUSED: 0, OUT_OF_SCOPE: 0 };
    for (const e of entries) acc[e.answer_kind] = (acc[e.answer_kind] ?? 0) + 1;
    return acc;
  }, [entries]);

  if (loading) return <LoadingCard rows={6} title="Query log" />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;

  return (
    <Card className="overflow-hidden">
      <CardHeader
        title="Query log"
        subtitle="Every question put to this property's file, with what the assistant did about it."
        icon={<ScrollText className="h-4 w-4" />}
        action={
          <Button variant="ghost" size="sm" onClick={onRetry}>
            Refresh
          </Button>
        }
      />

      <div className="grid grid-cols-3 gap-px border-b border-canvas-border bg-canvas-border">
        <TallyCell label="Grounded" value={tally.GROUNDED} tone="text-status-verified" />
        <TallyCell label="Declined" value={tally.REFUSED} tone="text-status-info" />
        <TallyCell label="Out of scope" value={tally.OUT_OF_SCOPE} tone="text-status-owner" />
      </div>

      {entries.length === 0 ? (
        <div className="p-5">
          <EmptyState
            title="Nothing asked yet"
            description="Ask a question — the log records the grounded/declined mix so the balance is visible at a glance."
          />
        </div>
      ) : (
        <ul className="max-h-[560px] divide-y divide-canvas-border/70 overflow-y-auto">
          {entries.map((entry) => {
            const meta = KIND_META[entry.answer_kind] ?? KIND_META.GROUNDED;
            return (
              <li key={entry.id} className="px-4 py-3">
                <div className="flex items-start justify-between gap-2">
                  <button
                    onClick={() => onReask(entry.question)}
                    className="min-w-0 flex-1 text-left text-[13px] font-medium leading-snug text-ink transition hover:text-navy-700"
                  >
                    {entry.question}
                  </button>
                  <Tooltip content={dateTime(entry.created_at)}>
                    <span className="shrink-0 text-2xs text-ink-subtle">
                      {relative(entry.created_at)}
                    </span>
                  </Tooltip>
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-2">
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 text-2xs font-semibold uppercase tracking-[0.08em]",
                      meta.accent,
                    )}
                  >
                    {meta.icon}
                    {entry.answer_kind === "REFUSED" ? "Declined" : titleise(entry.answer_kind)}
                  </span>
                  <code className="font-mono text-2xs text-ink-subtle">{entry.intent}</code>
                  {entry.answer_kind === "GROUNDED" ? (
                    <span className="tnum text-2xs text-ink-subtle">
                      {pct(entry.confidence)} · {entry.evidence?.length ?? 0} citation
                      {(entry.evidence?.length ?? 0) === 1 ? "" : "s"}
                    </span>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <p className="border-t border-canvas-border px-4 py-3 text-2xs leading-relaxed text-ink-subtle">
        {count} logged quer{count === 1 ? "y" : "ies"} on this property. The mix is the metric that
        matters: a system that answers everything is not grounded.
      </p>
    </Card>
  );
}

function TallyCell({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="bg-canvas-raised px-3 py-3 text-center">
      <div className={cn("tnum text-xl font-semibold", tone)}>{value}</div>
      <div className="section-label mt-0.5">{label}</div>
    </div>
  );
}
