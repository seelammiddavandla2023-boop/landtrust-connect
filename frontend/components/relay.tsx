"use client";

/**
 * Secure owner ↔ buyer relay.
 *
 * The channel is property-scoped and the server redacts before it stores: the body
 * that arrives here is already the redacted text, so a message that carried a phone
 * number can never be recovered from the client. When the send response carries a
 * `warning`, it is surfaced deliberately — a buyer being told *why* the platform
 * removed their phone number is the teaching moment, not an error.
 */

import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Building2,
  Loader2,
  MessagesSquare,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import React from "react";

import { useApi, useRole } from "@/components/hooks";
import {
  Button,
  Card,
  CardHeader,
  Chip,
  EmptyState,
  ErrorState,
  LoadingCard,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import type { Role } from "@/lib/domain";
import { cn, dateTime, relative, titleise } from "@/lib/format";

export type RelayMessage = {
  id: string;
  property_id: string;
  sender_role: Role | string;
  sender_name: string;
  body: string;
  contained_sensitive: boolean;
  sensitive_kinds: string[];
  references_claim_id: string | null;
  created_at: string;
};

type MessagesResponse = { count: number; items: RelayMessage[]; notice: string };

const EXAMPLES: { label: string; hint: string; text: string; tone: "navy" | "amber" }[] = [
  {
    label: "Ask about the evidence",
    hint: "A normal, on-platform question",
    tone: "navy",
    text:
      "I would like clarification on the area mismatch detected between the sale deed and the EC.",
  },
  {
    label: "Demonstrates redaction",
    hint: "Contains a phone number and an e-mail — both are stripped before delivery",
    tone: "amber",
    text: "Call me on 9840112233 or email me at test@example.com",
  },
];

/** Per-role presentation. Alignment and colour are driven by who sent the message. */
function senderStyle(role: string) {
  if (role === "OWNER") {
    return {
      align: "items-start",
      bubble: "bg-emerald-50 text-ink ring-1 ring-emerald-200",
      name: "text-emerald-700",
      icon: <Building2 className="h-3.5 w-3.5" />,
      label: "Owner",
    };
  }
  if (role === "BUYER") {
    return {
      align: "items-end",
      bubble: "bg-navy-900 text-white/95 ring-1 ring-navy-900",
      name: "text-navy-700",
      icon: <UserRound className="h-3.5 w-3.5" />,
      label: "Buyer",
    };
  }
  return {
    align: "items-start",
    bubble: "bg-canvas-sunken text-ink ring-1 ring-canvas-border",
    name: "text-ink-muted",
    icon: <ShieldCheck className="h-3.5 w-3.5" />,
    label: titleise(role),
  };
}

export function Relay({ propertyId, className }: { propertyId: string; className?: string }) {
  const [role] = useRole();
  const { data, error, loading, refetch } = useApi<MessagesResponse>(
    () => endpoints.messages(propertyId),
    [propertyId, role],
  );

  const [draft, setDraft] = React.useState("");
  const [sending, setSending] = React.useState(false);
  const [warning, setWarning] = React.useState<string | null>(null);
  const [sendError, setSendError] = React.useState<string | null>(null);
  const composerRef = React.useRef<HTMLTextAreaElement>(null);

  async function send() {
    const body = draft.trim();
    if (!body || sending) return;
    setSending(true);
    setSendError(null);
    try {
      const res = await endpoints.sendMessage({ property_id: propertyId, body }, role);
      setWarning(res?.warning ?? null);
      setDraft("");
      refetch();
    } catch (err: any) {
      setSendError(err?.detail || err?.message || "The message could not be sent.");
    } finally {
      setSending(false);
    }
  }

  function fillExample(text: string) {
    setDraft(text);
    setWarning(null);
    composerRef.current?.focus();
  }

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader
        icon={<MessagesSquare className="h-4 w-4" />}
        title="Secure relay"
        subtitle={
          loading
            ? "Loading the property-scoped channel…"
            : data?.notice ??
              "Property-scoped channel. Personal identifiers are removed before delivery."
        }
        action={
          <Chip tone="navy">
            <ShieldCheck className="h-3.5 w-3.5" />
            Audited channel
          </Chip>
        }
      />

      <div className="px-5 py-4">
        {loading ? (
          <LoadingCard rows={4} />
        ) : error ? (
          <ErrorState error={error} onRetry={refetch} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            title="No messages yet"
            description="Start the conversation below. Everything sent here is scanned, redacted where necessary and recorded in the audit trail."
            icon={<MessagesSquare className="h-5 w-5" />}
          />
        ) : (
          <ol className="space-y-4">
            {data.items.map((m) => {
              const s = senderStyle(String(m.sender_role));
              return (
                <li key={m.id} className={cn("flex flex-col gap-1.5", s.align)}>
                  <div className="flex items-center gap-2 text-2xs font-semibold uppercase tracking-[0.1em]">
                    <span className={cn("inline-flex items-center gap-1.5", s.name)}>
                      {s.icon}
                      {s.label}
                    </span>
                    <span className="font-medium normal-case tracking-normal text-ink-subtle">
                      {m.sender_name}
                    </span>
                    <span
                      className="font-normal normal-case tracking-normal text-ink-subtle"
                      title={dateTime(m.created_at)}
                    >
                      · {relative(m.created_at)}
                    </span>
                  </div>

                  <div
                    className={cn(
                      "max-w-[85%] rounded-2xl px-4 py-2.5 text-[13.5px] leading-relaxed",
                      s.bubble,
                    )}
                  >
                    {m.body}
                  </div>

                  {/* The redaction marker is deliberately loud: the buyer should see that
                      the platform removed something, and exactly what kind of thing. */}
                  {m.contained_sensitive ? (
                    <div className="flex max-w-[85%] flex-wrap items-center gap-2 rounded-xl bg-status-partialBg px-3 py-1.5 ring-1 ring-status-partial/20">
                      <span className="inline-flex items-center gap-1.5 text-2xs font-semibold uppercase tracking-[0.1em] text-status-partial">
                        <AlertTriangle className="h-3.5 w-3.5" />
                        Redacted before delivery
                      </span>
                      {m.sensitive_kinds.map((k) => (
                        <span
                          key={k}
                          className="rounded-full bg-canvas-raised px-2 py-0.5 text-2xs font-medium text-status-partial ring-1 ring-status-partial/25"
                        >
                          {titleise(k)}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ol>
        )}
      </div>

      <div className="border-t border-canvas-border bg-canvas-sunken/40 px-5 py-4">
        <AnimatePresence>
          {warning ? (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mb-3 flex items-start gap-3 rounded-xl bg-status-partialBg px-4 py-3 ring-1 ring-status-partial/25"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-status-partial" />
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-semibold text-status-partial">
                  The relay removed part of that message
                </p>
                <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">{warning}</p>
              </div>
              <button
                onClick={() => setWarning(null)}
                className="text-2xs font-semibold uppercase tracking-[0.1em] text-status-partial hover:underline"
              >
                Dismiss
              </button>
            </motion.div>
          ) : null}
        </AnimatePresence>

        {sendError ? (
          <p className="mb-3 rounded-xl bg-status-conflictingBg px-4 py-2.5 text-[13px] text-status-conflicting ring-1 ring-status-conflicting/20">
            {sendError}
          </p>
        ) : null}

        <div className="mb-2.5 flex flex-wrap items-center gap-2">
          <span className="section-label">Try</span>
          {EXAMPLES.map((ex) => (
            <Chip key={ex.label} tone={ex.tone} onClick={() => fillExample(ex.text)}>
              <Sparkles className="h-3.5 w-3.5" />
              {ex.label}
            </Chip>
          ))}
        </div>
        <p className="mb-3 text-2xs leading-relaxed text-ink-subtle">
          {EXAMPLES[1].hint}. Send it as a buyer to see the platform strip the contact details
          and explain why.
        </p>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <textarea
            ref={composerRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send();
            }}
            rows={3}
            placeholder={`Write as ${titleise(role)} — identifiers are removed before delivery`}
            className="min-h-[76px] w-full flex-1 resize-y rounded-xl border border-canvas-borderStrong bg-canvas-raised px-3.5 py-2.5 text-[13.5px] leading-relaxed text-ink placeholder:text-ink-subtle focus:border-navy-400"
          />
          <Button onClick={send} disabled={sending || !draft.trim()} className="sm:w-auto">
            {sending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            Send as {titleise(role)}
          </Button>
        </div>
        <p className="mt-2 text-2xs text-ink-subtle">
          Sent with the active demo role. ⌘/Ctrl + Enter sends.
        </p>
      </div>
    </Card>
  );
}

export default Relay;
