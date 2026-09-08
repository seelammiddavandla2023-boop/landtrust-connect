"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  Building2,
  ChevronDown,
  FileSearch,
  FlaskConical,
  GitCompareArrows,
  LayoutDashboard,
  Layers3,
  type LucideIcon,
  MessagesSquare,
  Presentation,
  ShieldCheck,
  Sparkles,
  UserCog,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import React from "react";

import { useRole } from "@/components/hooks";
import { PrototypeBadge } from "@/components/ui";
import { ROLES, type Role } from "@/lib/domain";
import { cn } from "@/lib/format";

type NavItem = { href: string; label: string; icon: LucideIcon; hint?: string };
type NavGroup = { label: string; items: NavItem[] };

const NAV: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/properties", label: "Properties", icon: Building2 },
      { href: "/documents", label: "Document Intelligence", icon: FileSearch },
      { href: "/assistant", label: "Evidence Assistant", icon: Sparkles },
    ],
  },
  {
    label: "Portals",
    items: [
      { href: "/buyer", label: "Buyer Portal", icon: Users },
      { href: "/owner", label: "Owner Portal", icon: UserCog },
    ],
  },
  {
    label: "Research",
    items: [
      { href: "/research", label: "Results", icon: FlaskConical },
      { href: "/research-gap", label: "Research Gap", icon: GitCompareArrows },
      { href: "/architecture", label: "System Architecture", icon: Layers3 },
      { href: "/presentation", label: "Presentation Mode", icon: Presentation },
    ],
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // The landing page is its own full-bleed composition.
  if (pathname === "/") return <>{children}</>;

  return (
    <div className="flex min-h-screen bg-canvas">
      <Sidebar pathname={pathname} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex-1 px-6 py-6 lg:px-8">
          <div className="mx-auto w-full max-w-[1500px]">{children}</div>
        </main>
        <footer className="border-t border-canvas-border px-6 py-4 lg:px-8">
          <p className="mx-auto max-w-[1500px] text-2xs leading-relaxed text-ink-subtle">
            LandTrust Connect — research prototype. Statuses describe agreement between the
            documents uploaded to this platform. They are not a certification of legal title and
            do not replace official records, registrar verification or professional advice. All
            data shown is synthetic.
          </p>
        </footer>
      </div>
    </div>
  );
}

function Sidebar({ pathname }: { pathname: string }) {
  return (
    <aside className="sticky top-0 hidden h-screen w-[248px] shrink-0 flex-col border-r border-canvas-border bg-canvas-raised lg:flex">
      <Link href="/" className="flex items-center gap-2.5 px-5 py-5">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-navy-fade text-white shadow-card">
          <ShieldCheck className="h-4.5 w-4.5" strokeWidth={2.2} />
        </div>
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-tight text-ink">LandTrust</div>
          <div className="text-2xs font-medium uppercase tracking-[0.16em] text-ink-subtle">
            Connect
          </div>
        </div>
      </Link>

      <nav className="flex-1 overflow-y-auto px-3 pb-4">
        {NAV.map((group) => (
          <div key={group.label} className="mb-5">
            <div className="section-label px-2.5 pb-1.5">{group.label}</div>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const active =
                  pathname === item.href || pathname.startsWith(`${item.href}/`);
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition",
                        active
                          ? "bg-navy-50 text-navy-900"
                          : "text-ink-muted hover:bg-canvas-sunken hover:text-ink",
                      )}
                    >
                      {active ? (
                        <motion.span
                          layoutId="nav-active"
                          className="absolute inset-y-1 left-0 w-0.5 rounded-full bg-navy-900"
                        />
                      ) : null}
                      <Icon className="h-4 w-4 shrink-0" strokeWidth={active ? 2.2 : 1.9} />
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-canvas-border px-4 py-4">
        <PrototypeBadge />
        <p className="mt-2.5 text-2xs leading-relaxed text-ink-subtle">
          Review-2 build · synthetic corpus · no official records
        </p>
      </div>
    </aside>
  );
}

function TopBar() {
  const pathname = usePathname();
  const crumbs = pathname.split("/").filter(Boolean);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-4 border-b border-canvas-border bg-canvas-raised/85 px-6 backdrop-blur lg:px-8">
      <div className="flex min-w-0 items-center gap-2">
        <Link href="/" className="lg:hidden">
          <ShieldCheck className="h-5 w-5 text-navy-900" />
        </Link>
        <nav className="flex min-w-0 items-center gap-1.5 text-[13px]">
          {crumbs.map((crumb, i) => (
            <React.Fragment key={`${crumb}-${i}`}>
              {i > 0 ? <span className="text-ink-subtle">/</span> : null}
              <span
                className={cn(
                  "truncate",
                  i === crumbs.length - 1 ? "font-medium text-ink" : "text-ink-muted",
                )}
              >
                {crumb.replace(/-/g, " ").replace(/^\w/, (c) => c.toUpperCase())}
              </span>
            </React.Fragment>
          ))}
        </nav>
      </div>
      <RoleSwitcher />
    </header>
  );
}

/**
 * Role switching is not cosmetic: the selected role is sent with every request and
 * the server decides what to return. Switching to Buyer genuinely removes access.
 */
export function RoleSwitcher({ compact }: { compact?: boolean }) {
  const [role, setRole] = useRole();
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);
  const current = ROLES.find((r) => r.role === role) ?? ROLES[0];

  React.useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-lg border border-canvas-borderStrong bg-canvas-raised px-3 py-1.5 text-[13px] font-medium text-ink transition hover:bg-canvas-sunken"
      >
        <span className="grid h-5 w-5 place-items-center rounded-md bg-navy-900 text-2xs font-bold text-white">
          {current.label[0]}
        </span>
        {compact ? null : <span>{current.label}</span>}
        <ChevronDown className={cn("h-3.5 w-3.5 text-ink-subtle transition", open && "rotate-180")} />
      </button>

      <AnimatePresence>
        {open ? (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.14 }}
            className="absolute right-0 z-50 mt-2 w-[330px] overflow-hidden rounded-xl border border-canvas-border bg-canvas-raised shadow-raised"
          >
            <div className="border-b border-canvas-border px-3.5 py-2.5">
              <div className="section-label">Demo role</div>
              <p className="mt-1 text-2xs leading-relaxed text-ink-muted">
                Sent as <code className="font-mono">X-Demo-Role</code> on every request. Masking
                and consent are enforced server-side, so this is not a client-side preview.
              </p>
            </div>
            <ul className="p-1.5">
              {ROLES.map((r) => (
                <li key={r.role}>
                  <button
                    onClick={() => {
                      setRole(r.role as Role);
                      setOpen(false);
                    }}
                    className={cn(
                      "w-full rounded-lg px-2.5 py-2 text-left transition",
                      r.role === role ? "bg-navy-50" : "hover:bg-canvas-sunken",
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          "h-1.5 w-1.5 rounded-full",
                          r.role === role ? "bg-navy-900" : "bg-canvas-borderStrong",
                        )}
                      />
                      <span className="text-[13px] font-medium text-ink">{r.label}</span>
                    </div>
                    <p className="ml-3.5 mt-0.5 text-2xs leading-relaxed text-ink-muted">
                      {r.blurb}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
