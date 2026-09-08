"use client";

/**
 * Shared UI primitives.
 *
 * The rule this file exists to enforce: a verification status, a risk band and a
 * transaction state always look the same wherever they appear. A reviewer should be
 * able to learn the visual language once, on the dashboard, and read it correctly on
 * every other screen without being told again.
 */

import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Check,
  ChevronRight,
  CircleAlert,
  Clock,
  FileWarning,
  Info,
  Lock,
  ShieldCheck,
  ShieldQuestion,
  User,
  X,
} from "lucide-react";
import React from "react";

import {
  BAND_META,
  DISCLAIMER,
  SEVERITY_META,
  STATE_META,
  VERIFICATION_META,
  type RiskBand,
  type Severity,
  type TransactionState,
  type VerificationStatus,
} from "@/lib/domain";
import { cn } from "@/lib/format";

/* ------------------------------------------------------------------ layout */

export function Card({
  className,
  children,
  ...rest
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("card", className)} {...rest}>
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
  icon,
  className,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-start justify-between gap-4 border-b border-canvas-border px-5 py-4",
        className,
      )}
    >
      <div className="flex min-w-0 items-start gap-3">
        {icon ? (
          <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-navy-50 text-navy-700">
            {icon}
          </div>
        ) : null}
        <div className="min-w-0">
          <h3 className="text-[15px] font-semibold leading-tight text-ink">{title}</h3>
          {subtitle ? (
            <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">{subtitle}</p>
          ) : null}
        </div>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-3xl">
        {eyebrow ? <div className="section-label mb-1.5">{eyebrow}</div> : null}
        <h2 className="text-xl font-semibold tracking-tight text-ink">{title}</h2>
        {description ? (
          <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

/* ------------------------------------------------------------------ badges */

export function StatusBadge({
  status,
  size = "md",
  withTooltip = true,
}: {
  status: VerificationStatus;
  size?: "sm" | "md";
  withTooltip?: boolean;
}) {
  const meta = VERIFICATION_META[status] ?? VERIFICATION_META.UNVERIFIED;
  const icon = {
    VERIFIED: <ShieldCheck className="h-3.5 w-3.5" />,
    PARTIALLY_VERIFIED: <ShieldQuestion className="h-3.5 w-3.5" />,
    CONFLICTING: <CircleAlert className="h-3.5 w-3.5" />,
    PENDING: <Clock className="h-3.5 w-3.5" />,
    EXPIRED: <FileWarning className="h-3.5 w-3.5" />,
    OWNER_PROVIDED: <User className="h-3.5 w-3.5" />,
    UNVERIFIED: <Info className="h-3.5 w-3.5" />,
  }[status];

  const badge = (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-semibold ring-1",
        meta.fg,
        meta.bg,
        meta.ring,
        size === "sm" ? "px-2 py-0.5 text-2xs" : "px-2.5 py-1 text-xs",
      )}
    >
      {icon}
      {meta.label}
    </span>
  );
  return withTooltip ? <Tooltip content={meta.meaning}>{badge}</Tooltip> : badge;
}

export function StateBadge({
  state,
  size = "md",
}: {
  state: TransactionState;
  size?: "sm" | "md" | "lg";
}) {
  const meta = STATE_META[state] ?? STATE_META.WARN;
  return (
    <Tooltip content={meta.blurb}>
      <span
        className={cn(
          "inline-flex items-center gap-2 rounded-full font-semibold uppercase tracking-wide",
          meta.fg,
          meta.bg,
          size === "sm" ? "px-2 py-0.5 text-2xs" : size === "lg" ? "px-4 py-1.5 text-sm" : "px-3 py-1 text-xs",
        )}
      >
        <span className={cn("h-1.5 w-1.5 rounded-full", meta.dot)} />
        {meta.label}
      </span>
    </Tooltip>
  );
}

export function BandBadge({ band }: { band: RiskBand }) {
  const meta = BAND_META[band] ?? BAND_META.LOW;
  return (
    <span className={cn("rounded-full px-2.5 py-1 text-xs font-semibold", meta.fg, meta.bg)}>
      {meta.label} risk
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const meta = SEVERITY_META[severity] ?? SEVERITY_META.INFO;
  return (
    <span className={cn("rounded px-1.5 py-0.5 text-2xs font-semibold uppercase tracking-wide", meta.fg, meta.bg)}>
      {meta.label}
    </span>
  );
}

export function Chip({
  children,
  tone = "neutral",
  className,
  onClick,
  active,
}: {
  children: React.ReactNode;
  tone?: "neutral" | "navy" | "emerald" | "amber" | "red";
  className?: string;
  onClick?: () => void;
  active?: boolean;
}) {
  const tones = {
    neutral: "bg-canvas-sunken text-ink-muted ring-canvas-border",
    navy: "bg-navy-50 text-navy-700 ring-navy-200",
    emerald: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    amber: "bg-status-partialBg text-status-partial ring-status-partial/20",
    red: "bg-status-conflictingBg text-status-conflicting ring-status-conflicting/20",
  }[tone];
  const Comp: any = onClick ? "button" : "span";
  return (
    <Comp
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1",
        tones,
        onClick && "transition hover:brightness-95",
        active && "ring-2 ring-navy-500",
        className,
      )}
    >
      {children}
    </Comp>
  );
}

/** An evidence chip: document name + page, the atom of provenance in this UI. */
export function EvidenceChip({
  document,
  page,
  confidence,
  onClick,
}: {
  document: string;
  page?: number | null;
  confidence?: number | null;
  onClick?: () => void;
}) {
  return (
    <Chip tone="navy" onClick={onClick} className="max-w-full">
      <span className="truncate">{document}</span>
      {page ? <span className="text-navy-500">p{page}</span> : null}
      {confidence !== undefined && confidence !== null ? (
        <span className="tnum rounded bg-white/70 px-1 text-2xs text-navy-600">
          {Math.round(confidence * 100)}%
        </span>
      ) : null}
    </Chip>
  );
}

/* ---------------------------------------------------------------- controls */

export function Button({
  variant = "primary",
  size = "md",
  className,
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "subtle";
  size?: "sm" | "md" | "lg";
}) {
  const variants = {
    primary: "bg-navy-900 text-white hover:bg-navy-800 disabled:bg-navy-900/40",
    secondary:
      "bg-canvas-raised text-ink ring-1 ring-canvas-borderStrong hover:bg-canvas-sunken disabled:text-ink-subtle",
    subtle: "bg-canvas-sunken text-ink-muted hover:bg-canvas-border/60",
    ghost: "text-ink-muted hover:bg-canvas-sunken hover:text-ink",
    danger: "bg-status-conflicting text-white hover:brightness-110",
  }[variant];
  const sizes = {
    sm: "px-2.5 py-1.5 text-xs",
    md: "px-3.5 py-2 text-sm",
    lg: "px-5 py-2.5 text-sm",
  }[size];
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
        variants,
        sizes,
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: string; label: string; count?: number; icon?: React.ReactNode }[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="scroll-x -mb-px flex gap-1 border-b border-canvas-border">
      {tabs.map((t) => {
        const isActive = t.key === active;
        return (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            className={cn(
              "relative flex shrink-0 items-center gap-2 whitespace-nowrap px-3.5 py-2.5 text-sm font-medium transition",
              isActive ? "text-navy-900" : "text-ink-muted hover:text-ink",
            )}
          >
            {t.icon}
            {t.label}
            {t.count !== undefined ? (
              <span
                className={cn(
                  "tnum rounded-full px-1.5 py-0.5 text-2xs font-semibold",
                  isActive ? "bg-navy-900 text-white" : "bg-canvas-sunken text-ink-subtle",
                )}
              >
                {t.count}
              </span>
            ) : null}
            {isActive ? (
              <motion.span
                layoutId="tab-underline"
                className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-navy-900"
              />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

export function Tooltip({
  content,
  children,
  side = "top",
}: {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "bottom";
}) {
  const [open, setOpen] = React.useState(false);
  if (!content) return <>{children}</>;
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      <AnimatePresence>
        {open ? (
          <motion.span
            initial={{ opacity: 0, y: side === "top" ? 4 : -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.14 }}
            className={cn(
              "pointer-events-none absolute left-1/2 z-50 w-64 -translate-x-1/2 rounded-lg bg-navy-950 px-3 py-2 text-xs font-normal leading-relaxed text-white/90 shadow-raised",
              side === "top" ? "bottom-full mb-2" : "top-full mt-2",
            )}
          >
            {content}
          </motion.span>
        ) : null}
      </AnimatePresence>
    </span>
  );
}

/* ------------------------------------------------------------------ drawer */

export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  children,
  width = "max-w-2xl",
}: {
  open: boolean;
  onClose: () => void;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  children: React.ReactNode;
  width?: string;
}) {
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-navy-950/35 backdrop-blur-[2px]"
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 32, stiffness: 320 }}
            className={cn(
              "fixed inset-y-0 right-0 z-50 flex w-full flex-col bg-canvas-raised shadow-drawer",
              width,
            )}
          >
            <div className="flex items-start justify-between gap-4 border-b border-canvas-border px-6 py-4">
              <div className="min-w-0">
                <h2 className="text-base font-semibold text-ink">{title}</h2>
                {subtitle ? (
                  <p className="mt-1 text-[13px] text-ink-muted">{subtitle}</p>
                ) : null}
              </div>
              <button
                onClick={onClose}
                className="rounded-lg p-1.5 text-ink-subtle transition hover:bg-canvas-sunken hover:text-ink"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
          </motion.aside>
        </>
      ) : null}
    </AnimatePresence>
  );
}

/* ------------------------------------------------------------------- state */

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}

export function LoadingCard({ rows = 4, title }: { rows?: number; title?: string }) {
  return (
    <Card className="p-5">
      {title ? <div className="section-label mb-3">{title}</div> : null}
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className={cn("h-4", i === 0 ? "w-1/3" : i % 2 ? "w-full" : "w-4/5")} />
        ))}
      </div>
    </Card>
  );
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: { message?: string; detail?: string } | string;
  onRetry?: () => void;
}) {
  const message = typeof error === "string" ? error : error.detail || error.message || "Something went wrong.";
  return (
    <Card className="p-6">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-status-conflictingBg text-status-conflicting">
          <AlertTriangle className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-ink">Could not load this view</h3>
          <p className="mt-1 text-sm leading-relaxed text-ink-muted">{message}</p>
          {onRetry ? (
            <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
              Try again
            </Button>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

export function EmptyState({
  title,
  description,
  icon,
  action,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-canvas-borderStrong bg-canvas-raised/60 px-6 py-12 text-center">
      <div className="mb-3 grid h-10 w-10 place-items-center rounded-xl bg-canvas-sunken text-ink-subtle">
        {icon ?? <Info className="h-5 w-5" />}
      </div>
      <p className="text-sm font-semibold text-ink">{title}</p>
      {description ? (
        <p className="mt-1.5 max-w-md text-[13px] leading-relaxed text-ink-muted">{description}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ meters */

export function ConfidenceBar({ value, label }: { value: number; label?: string }) {
  const pctValue = Math.round((value <= 1 ? value * 100 : value));
  const tone = pctValue >= 90 ? "bg-status-verified" : pctValue >= 70 ? "bg-status-partial" : "bg-status-conflicting";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-canvas-sunken">
        <div className={cn("h-full rounded-full transition-all", tone)} style={{ width: `${pctValue}%` }} />
      </div>
      <span className="tnum text-2xs font-medium text-ink-muted">{label ?? `${pctValue}%`}</span>
    </div>
  );
}

/** Semi-circular risk gauge. Animates from the previous value so a drop is felt. */
export function RiskGauge({
  score,
  band,
  size = 200,
  label,
}: {
  score: number;
  band: RiskBand;
  size?: number;
  label?: string;
}) {
  const meta = BAND_META[band] ?? BAND_META.LOW;
  const radius = size / 2 - 16;
  const circumference = Math.PI * radius;
  const offset = circumference * (1 - Math.min(100, Math.max(0, score)) / 100);

  return (
    <div className="flex flex-col items-center" style={{ width: size }}>
      <svg width={size} height={size / 2 + 14} viewBox={`0 0 ${size} ${size / 2 + 14}`}>
        <path
          d={`M 16 ${size / 2} A ${radius} ${radius} 0 0 1 ${size - 16} ${size / 2}`}
          fill="none"
          stroke="#e6ecf5"
          strokeWidth="13"
          strokeLinecap="round"
        />
        <motion.path
          d={`M 16 ${size / 2} A ${radius} ${radius} 0 0 1 ${size - 16} ${size / 2}`}
          fill="none"
          stroke={meta.hex}
          strokeWidth="13"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        />
        {[0, 25, 50, 75, 100].map((tick) => {
          const angle = Math.PI * (1 - tick / 100);
          const x = size / 2 + Math.cos(angle) * (radius + 12);
          const y = size / 2 - Math.sin(angle) * (radius + 12);
          return (
            <text
              key={tick}
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="middle"
              className="fill-ink-subtle text-[9px]"
            >
              {tick}
            </text>
          );
        })}
      </svg>
      <div className="-mt-8 text-center">
        <div className="tnum text-4xl font-semibold tracking-tight" style={{ color: meta.hex }}>
          {Math.round(score)}
        </div>
        <div className="text-2xs font-medium uppercase tracking-[0.12em] text-ink-subtle">
          {label ?? `${meta.label} risk · out of 100`}
        </div>
      </div>
    </div>
  );
}

export function StatTile({
  label,
  value,
  hint,
  tone = "neutral",
  icon,
  onClick,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "neutral" | "verified" | "warn" | "danger" | "info";
  icon?: React.ReactNode;
  onClick?: () => void;
}) {
  const tones = {
    neutral: "text-ink",
    verified: "text-status-verified",
    warn: "text-risk-moderate",
    danger: "text-risk-critical",
    info: "text-status-info",
  }[tone];
  const Comp: any = onClick ? "button" : "div";
  return (
    <Comp
      onClick={onClick}
      className={cn(
        "card px-4 py-3.5 text-left transition",
        onClick && "hover:shadow-raised hover:-translate-y-px",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="section-label">{label}</span>
        {icon ? <span className="text-ink-subtle">{icon}</span> : null}
      </div>
      <div className={cn("tnum mt-2 text-2xl font-semibold tracking-tight", tones)}>{value}</div>
      {hint ? <p className="mt-1 text-2xs leading-snug text-ink-subtle">{hint}</p> : null}
    </Comp>
  );
}

/* ------------------------------------------------------------- disclaimers */

export function PrototypeBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full bg-status-partialBg px-2.5 py-1 text-2xs font-semibold uppercase tracking-[0.1em] text-status-partial ring-1 ring-status-partial/20",
        className,
      )}
    >
      <span className="relative flex h-1.5 w-1.5">
        <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-status-partial" />
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-status-partial" />
      </span>
      Research prototype
    </span>
  );
}

export function DemoDataBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-status-infoBg px-2.5 py-1 text-2xs font-semibold uppercase tracking-[0.1em] text-status-info ring-1 ring-status-info/20">
      Synthetic data
    </span>
  );
}

export function Disclaimer({ className, text }: { className?: string; text?: string }) {
  return (
    <p
      className={cn(
        "flex items-start gap-2 rounded-xl bg-canvas-sunken px-3.5 py-2.5 text-2xs leading-relaxed text-ink-muted",
        className,
      )}
    >
      <Info className="mt-px h-3.5 w-3.5 shrink-0 text-ink-subtle" />
      <span>{text ?? DISCLAIMER}</span>
    </p>
  );
}

export function MaskedValue({ value, reason }: { value: string; reason?: string }) {
  return (
    <Tooltip content={reason}>
      <span className="inline-flex items-center gap-1.5 rounded-md bg-canvas-sunken px-2 py-0.5 font-mono text-[13px] text-ink-muted ring-1 ring-canvas-border">
        <Lock className="h-3 w-3 text-ink-subtle" />
        {value}
      </span>
    </Tooltip>
  );
}

export function KeyValue({
  label,
  value,
  mono,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div>
      <div className="section-label">{label}</div>
      <div className={cn("mt-1 text-sm text-ink", mono && "font-mono text-[13px]")}>{value}</div>
    </div>
  );
}

export function InlineList({ items }: { items: React.ReactNode[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2 text-[13px] leading-relaxed text-ink-muted">
          <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-subtle" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function CheckList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2 text-[13px] leading-relaxed text-ink-muted">
          <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-status-verified" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}
