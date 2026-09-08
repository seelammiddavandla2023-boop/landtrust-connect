import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Indian-format currency, abbreviated where the exact rupee is not the point. */
export function inr(value?: number | null, opts: { compact?: boolean } = {}): string {
  if (value === null || value === undefined) return "—";
  if (opts.compact) {
    if (value >= 1_00_00_000) return `₹${(value / 1_00_00_000).toFixed(2)} Cr`;
    if (value >= 1_00_000) return `₹${(value / 1_00_000).toFixed(2)} L`;
  }
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export function sqft(value?: number | null): string {
  if (value === null || value === undefined) return "—";
  return `${value.toLocaleString("en-IN")} sq.ft`;
}

export function pct(value?: number | null, digits = 0): string {
  if (value === null || value === undefined) return "—";
  const n = value <= 1 ? value * 100 : value;
  return `${n.toFixed(digits)}%`;
}

export function shortDate(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function dateTime(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relative(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value).getTime();
  if (Number.isNaN(d)) return value;
  const diff = Date.now() - d;
  const mins = Math.round(diff / 60000);
  if (Math.abs(mins) < 1) return "just now";
  if (Math.abs(mins) < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (Math.abs(hours) < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (Math.abs(days) < 30) return `${days}d ago`;
  return shortDate(value);
}

/** "OWNER_NAME" / "owner_name" → "Owner Name" */
export function titleise(value?: string | null): string {
  if (!value) return "—";
  return value
    .replace(/[_-]+/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function truncate(value: string, max = 120): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

export function signed(value: number): string {
  return value > 0 ? `+${value}` : `${value}`;
}
