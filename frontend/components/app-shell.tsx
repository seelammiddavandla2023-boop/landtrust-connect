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
  Menu,
  MessagesSquare,
  Presentation,
  ShieldCheck,
  Sparkles,
  UserCog,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import React from "react";
import { createPortal } from "react-dom";

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

/**
 * Where each role's own controls live.
 *
 * Choosing a role changes what the server returns, but it changes nothing on
 * the page you happen to be standing on — so a user who switches to Land Owner
 * and stays on the dashboard sees no difference and reasonably concludes the
 * switch did nothing. This map is what the sidebar and the role switcher use to
 * say, in the interface, where that role's work actually happens.
 */
const ROLE_TOOLS: Record<Role, { note: string; items: NavItem[] }> = {
  BUYER: {
    note: "You see the evidence-gated profile. Masked values need the owner's consent.",
    items: [
      { href: "/buyer", label: "Browse listings", icon: Users },
      { href: "/assistant", label: "Ask about a property", icon: Sparkles },
    ],
  },
  OWNER: {
    note: "Decide access requests, add evidence, and clear what is holding a sale.",
    items: [
      { href: "/owner", label: "Access requests", icon: UserCog },
      { href: "/documents", label: "Upload evidence", icon: FileSearch },
      { href: "/properties", label: "My properties", icon: Building2 },
    ],
  },
  VERIFIER: {
    note: "Unmasked claims, contradictions and integrity indicators.",
    items: [
      { href: "/properties", label: "Examine a file", icon: Building2 },
      { href: "/documents", label: "Document intelligence", icon: FileSearch },
    ],
  },
  LEGAL_REVIEWER: {
    note: "Escalated cases and the complete audit trail.",
    items: [
      { href: "/properties", label: "Escalated files", icon: Building2 },
      { href: "/dashboard", label: "Platform overview", icon: LayoutDashboard },
    ],
  },
  ADMIN: {
    note: "Demo control and the research dashboards.",
    items: [
      { href: "/presentation", label: "Presentation mode", icon: Presentation },
      { href: "/research", label: "Research results", icon: FlaskConical },
      { href: "/dashboard", label: "Platform overview", icon: LayoutDashboard },
    ],
  },
};

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
            LandTrust Connect — research prototype. Statuses describe agreement
            between the documents uploaded to this platform. They are not a
            certification of legal title and do not replace official records,
            registrar verification or professional advice. All data shown is
            synthetic.
          </p>
        </footer>
      </div>
    </div>
  );
}

function Wordmark() {
  return (
    <>
      <div className="grid h-9 w-9 place-items-center rounded-xl bg-navy-fade text-white shadow-card">
        <ShieldCheck className="h-4.5 w-4.5" strokeWidth={2.2} />
      </div>
      <div className="leading-tight">
        <div className="text-[15px] font-semibold tracking-tight text-ink">
          LandTrust
        </div>
        <div className="text-2xs font-medium uppercase tracking-[0.16em] text-ink-subtle">
          Connect
        </div>
      </div>
    </>
  );
}

/**
 * The navigation itself, shared by the docked sidebar and the drawer.
 *
 * `animateActive` is off in the drawer: the active-item indicator is a shared
 * layout animation, and running two of them under the same layoutId while both
 * are mounted makes the marker fly between them.
 */
function NavList({
  pathname,
  onNavigate,
  animateActive = true,
}: {
  pathname: string;
  onNavigate?: () => void;
  animateActive?: boolean;
}) {
  const [role] = useRole();
  const mine = ROLE_TOOLS[role];
  const roleLabel = ROLES.find((r) => r.role === role)?.label ?? role;

  return (
    <>
      {/*
        The current role's own destinations, first and named after the task
        rather than the module. Everything below is still reachable — this is a
        shortcut, not a restriction, because the platform's point is that a
        reviewer can move between roles and compare what each one sees.
      */}
      <div className="mb-5">
        <div className="section-label px-2.5 pb-1.5">{roleLabel} · your tools</div>
        <ul className="space-y-0.5">
          {mine.items.map((item) => {
            const active =
              pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <li key={`mine-${item.href}`}>
                <Link
                  href={item.href}
                  onClick={onNavigate}
                  className={cn(
                    "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition",
                    active
                      ? "bg-emerald-50 text-emerald-800"
                      : "text-ink-muted hover:bg-canvas-sunken hover:text-ink",
                  )}
                >
                  <Icon
                    className="h-4 w-4 shrink-0 text-emerald-700"
                    strokeWidth={active ? 2.2 : 1.9}
                  />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
        <p className="px-2.5 pt-2 text-2xs leading-relaxed text-ink-subtle">{mine.note}</p>
      </div>

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
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition",
                      active
                        ? "bg-navy-50 text-navy-900"
                        : "text-ink-muted hover:bg-canvas-sunken hover:text-ink",
                    )}
                  >
                    {active ? (
                      animateActive ? (
                        <motion.span
                          layoutId="nav-active"
                          className="absolute inset-y-1 left-0 w-0.5 rounded-full bg-navy-900"
                        />
                      ) : (
                        <span className="absolute inset-y-1 left-0 w-0.5 rounded-full bg-navy-900" />
                      )
                    ) : null}
                    <Icon
                      className="h-4 w-4 shrink-0"
                      strokeWidth={active ? 2.2 : 1.9}
                    />
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </>
  );
}

function BuildFootnote() {
  return (
    <div className="border-t border-canvas-border px-4 py-4">
      <PrototypeBadge />
      <p className="mt-2.5 text-2xs leading-relaxed text-ink-subtle">
        Review-2 build · synthetic corpus · no official records
      </p>
    </div>
  );
}

function Sidebar({ pathname }: { pathname: string }) {
  return (
    <aside className="sticky top-0 hidden h-screen w-[248px] shrink-0 flex-col border-r border-canvas-border bg-canvas-raised lg:flex">
      <Link href="/" className="flex items-center gap-2.5 px-5 py-5">
        <Wordmark />
      </Link>
      <nav className="flex-1 overflow-y-auto px-3 pb-4">
        <NavList pathname={pathname} />
      </nav>
      <BuildFootnote />
    </aside>
  );
}

/**
 * Navigation below the sidebar's breakpoint.
 *
 * Without this, a window narrower than 1024px has no navigation at all — the
 * sidebar is display:none and the only link in the header is the logo, so the
 * owner portal, document upload and the research pages become unreachable
 * except by typing a URL. A projector or a half-width browser is exactly where
 * that would be discovered.
 */
/**
 * Role selection inside the drawer.
 *
 * The switcher lives in the header, which the drawer covers — so from the drawer
 * there was no way back to it, and changing role meant closing the navigation to
 * reach the control that decides what the navigation shows.
 *
 * Choosing here deliberately does not close the drawer: the role's own tools,
 * listed immediately below, rewrite themselves as you pick. That is the clearest
 * demonstration in the product that a role is a position with different work
 * rather than a display setting.
 */
function DrawerRolePicker() {
  const [role, setRole] = useRole();

  return (
    <div className="border-b border-canvas-border px-3 pb-4 pt-1">
      <div className="section-label px-2.5 pb-1.5">Viewing as</div>
      <ul className="space-y-0.5">
        {ROLES.map((r) => {
          const active = r.role === role;
          return (
            <li key={r.role}>
              <button
                type="button"
                onClick={() => setRole(r.role as Role)}
                aria-pressed={active}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-[13px] font-medium transition",
                  active
                    ? "bg-navy-50 text-navy-900"
                    : "text-ink-muted hover:bg-canvas-sunken hover:text-ink",
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 shrink-0 rounded-full",
                    active ? "bg-navy-900" : "bg-canvas-borderStrong",
                  )}
                />
                {r.label}
              </button>
            </li>
          );
        })}
      </ul>
      <p className="px-2.5 pt-2 text-2xs leading-relaxed text-ink-subtle">
        Masking, consent and every action are enforced on the server, so this is a change of
        position — not a change of view.
      </p>
    </div>
  );
}

function MobileNav({ pathname }: { pathname: string }) {
  const [open, setOpen] = React.useState(false);
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => setMounted(true), []);

  // Close on navigation, so following a link does not leave the drawer over the
  // page it just opened.
  React.useEffect(() => setOpen(false), [pathname]);

  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open navigation"
        aria-expanded={open}
        className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-ink-muted transition hover:bg-canvas-sunken hover:text-ink lg:hidden"
      >
        <Menu className="h-5 w-5" strokeWidth={1.9} />
      </button>

      {/*
        Rendered into document.body rather than in place. The header carries
        backdrop-blur, and a backdrop-filter establishes a containing block for
        fixed-position descendants — so an overlay left here is clipped to the
        56px height of the header instead of covering the viewport.
      */}
      {mounted
        ? createPortal(
            <AnimatePresence>
              {open ? (
                <div className="fixed inset-0 z-50 lg:hidden">
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15 }}
                    onClick={() => setOpen(false)}
                    className="absolute inset-0 bg-navy-900/40 backdrop-blur-[2px]"
                  />
                  <motion.div
                    role="dialog"
                    aria-modal="true"
                    aria-label="Navigation"
                    initial={{ x: -280 }}
                    animate={{ x: 0 }}
                    exit={{ x: -280 }}
                    transition={{ type: "spring", stiffness: 420, damping: 38 }}
                    className="absolute inset-y-0 left-0 flex w-[272px] max-w-[85vw] flex-col border-r border-canvas-border bg-canvas-raised shadow-raised"
                  >
                    <div className="flex items-center justify-between px-5 py-4">
                      <Link
                        href="/"
                        onClick={() => setOpen(false)}
                        className="flex items-center gap-2.5"
                      >
                        <Wordmark />
                      </Link>
                      <button
                        type="button"
                        onClick={() => setOpen(false)}
                        aria-label="Close navigation"
                        className="grid h-8 w-8 place-items-center rounded-lg text-ink-subtle transition hover:bg-canvas-sunken hover:text-ink"
                      >
                        <X className="h-4.5 w-4.5" strokeWidth={2} />
                      </button>
                    </div>
                    <div className="flex-1 overflow-y-auto">
                      <DrawerRolePicker />
                      <nav className="px-3 pb-4 pt-4">
                        <NavList
                          pathname={pathname}
                          onNavigate={() => setOpen(false)}
                          animateActive={false}
                        />
                      </nav>
                    </div>
                    <BuildFootnote />
                  </motion.div>
                </div>
              ) : null}
            </AnimatePresence>,
            document.body,
          )
        : null}
    </>
  );
}

function TopBar() {
  const pathname = usePathname();
  const crumbs = pathname.split("/").filter(Boolean);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-4 border-b border-canvas-border bg-canvas-raised/85 px-6 backdrop-blur lg:px-8">
      <div className="flex min-w-0 items-center gap-2">
        <MobileNav pathname={pathname} />
        <nav className="flex min-w-0 items-center gap-1.5 text-[13px]">
          {crumbs.map((crumb, i) => (
            <React.Fragment key={`${crumb}-${i}`}>
              {i > 0 ? <span className="text-ink-subtle">/</span> : null}
              <span
                className={cn(
                  "truncate",
                  i === crumbs.length - 1
                    ? "font-medium text-ink"
                    : "text-ink-muted",
                )}
              >
                {crumb
                  .replace(/-/g, " ")
                  .replace(/^\w/, (c) => c.toUpperCase())}
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
      if (ref.current && !ref.current.contains(e.target as Node))
        setOpen(false);
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
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 text-ink-subtle transition",
            open && "rotate-180",
          )}
        />
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
                Sent as <code className="font-mono">X-Demo-Role</code> on every
                request. Masking and consent are enforced server-side, so this
                is not a client-side preview.
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
                          r.role === role
                            ? "bg-navy-900"
                            : "bg-canvas-borderStrong",
                        )}
                      />
                      <span className="text-[13px] font-medium text-ink">
                        {r.label}
                      </span>
                    </div>
                    <p className="ml-3.5 mt-0.5 text-2xs leading-relaxed text-ink-muted">
                      {r.blurb}
                    </p>
                    {r.role === role ? (
                      <p className="ml-3.5 mt-1 text-2xs leading-relaxed text-emerald-800">
                        {ROLE_TOOLS[r.role as Role].note}
                      </p>
                    ) : null}
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
