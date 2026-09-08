"use client";

/**
 * Temporal ownership graph and timeline.
 *
 * The layout is deliberately deterministic rather than force-directed: a chain of
 * title has a natural reading order (earliest party on the left, the parcel in the
 * centre, instruments and charges around it), and a force simulation would rearrange
 * it differently on every load — which is the last thing you want when the same
 * diagram has to be explained twice in a review.
 *
 * Columns are assigned by node type and ordered by date, so the graph reads
 * left-to-right as time passing.
 */

import { AnimatePresence, motion } from "framer-motion";
import {
  Building2,
  CalendarClock,
  FileText,
  GitBranch,
  Landmark,
  Maximize2,
  Minus,
  Plus,
  Receipt,
  RotateCcw,
  ScrollText,
  ShieldAlert,
  Stamp,
  User,
} from "lucide-react";
import React from "react";

import { useApi } from "@/components/hooks";
import {
  Button,
  Card,
  CardHeader,
  Chip,
  EmptyState,
  ErrorState,
  EvidenceChip,
  LoadingCard,
  Tooltip,
} from "@/components/ui";
import { endpoints } from "@/lib/api";
import { cn, shortDate, titleise } from "@/lib/format";

type GNode = {
  id: string;
  type: string;
  label: string;
  sublabel?: string;
  date?: string | null;
  status: string;
  evidence?: any[];
  meta?: any;
};
type GEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  label?: string;
  valid_from?: string | null;
  valid_to?: string | null;
  status: string;
  evidence?: any[];
};

const NODE_ICON: Record<string, any> = {
  PERSON: User,
  PROPERTY: Building2,
  DEED: ScrollText,
  MORTGAGE: Landmark,
  POWER_OF_ATTORNEY: Stamp,
  TAX_RECORD: Receipt,
  SURVEY_RECORD: FileText,
  TRANSACTION: FileText,
};

const STATUS_STYLE: Record<string, { stroke: string; fill: string; text: string; chip: string }> = {
  VERIFIED: { stroke: "#0f8a5f", fill: "#e7f7ef", text: "#0f4637", chip: "verified" },
  CURRENT: { stroke: "#0f1c38", fill: "#e3e9f4", text: "#0f1c38", chip: "current" },
  CONFLICTING: { stroke: "#c62828", fill: "#fdecec", text: "#7d1a1a", chip: "conflicting" },
  EXPIRED: { stroke: "#8a5a1f", fill: "#f9efe2", text: "#5c3c14", chip: "expired" },
  NEUTRAL: { stroke: "#c3d0e2", fill: "#ffffff", text: "#0f1c38", chip: "neutral" },
};

const EDGE_STYLE: Record<string, { stroke: string; dash?: string }> = {
  CONTRADICTS: { stroke: "#c62828", dash: "5 4" },
  MORTGAGED_TO: { stroke: "#d2691e" },
  AUTHORIZED: { stroke: "#5b4bb8", dash: "4 3" },
  TRANSFERRED_TO: { stroke: "#48649d" },
  OWNS: { stroke: "#0f8a5f" },
  OWNED: { stroke: "#9aaed2", dash: "3 3" },
  RECORDED_IN: { stroke: "#c3d0e2", dash: "2 4" },
  SUPPORTED_BY: { stroke: "#aeead1" },
  RELEASED: { stroke: "#0f8a5f", dash: "4 3" },
};

const NODE_W = 168;
const NODE_H = 60;
const COL_GAP = 236;
const ROW_GAP = 92;

export function GraphTab({ propertyId }: { propertyId: string }) {
  const { data, error, loading, refetch } = useApi<any>(
    () => endpoints.graph(propertyId),
    [propertyId],
  );
  const [selected, setSelected] = React.useState<GNode | null>(null);
  const [mode, setMode] = React.useState<"graph" | "timeline">("graph");

  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (loading || !data) return <LoadingCard rows={10} title="Ownership graph" />;

  const nodes: GNode[] = data.nodes ?? [];
  const edges: GEdge[] = data.edges ?? [];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Temporal ownership graph"
          subtitle={
            data.chain_complete
              ? `The chain of title as the evidence supports it. Current owner on the evidence: ${data.current_owner ?? "not established"}.`
              : data.chain_note
          }
          icon={<GitBranch className="h-4 w-4" />}
          action={
            <div className="flex items-center gap-1 rounded-lg bg-canvas-sunken p-0.5">
              {(["graph", "timeline"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={cn(
                    "rounded-md px-2.5 py-1 text-2xs font-semibold uppercase tracking-wide transition",
                    mode === m ? "bg-canvas-raised text-ink shadow-card" : "text-ink-muted",
                  )}
                >
                  {m}
                </button>
              ))}
            </div>
          }
        />
        {!data.chain_complete && data.chain_note ? (
          <div className="border-b border-canvas-border bg-status-conflictingBg/50 px-5 py-3">
            <div className="flex items-start gap-2">
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-status-conflicting" />
              <p className="text-[13px] leading-relaxed text-ink-muted">{data.chain_note}</p>
            </div>
          </div>
        ) : null}

        {mode === "graph" ? (
          <GraphCanvas nodes={nodes} edges={edges} onSelect={setSelected} selected={selected} />
        ) : (
          <Timeline entries={data.timeline ?? []} />
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Legend />
        <NodeInspector node={selected} edges={edges} nodes={nodes} onClear={() => setSelected(null)} />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ graph canvas */

function layout(nodes: GNode[], edges: GEdge[]) {
  // Column by role in the story: parties, then the parcel, then the instruments and
  // charges that bear on it. Within a column, order by date so time reads downward.
  const columnFor = (n: GNode) => {
    if (n.type === "PERSON") return 0;
    if (n.type === "PROPERTY") return 1;
    if (n.type === "MORTGAGE" || n.type === "POWER_OF_ATTORNEY") return 2;
    return 3;
  };

  const byColumn: Record<number, GNode[]> = { 0: [], 1: [], 2: [], 3: [] };
  for (const n of nodes) byColumn[columnFor(n)].push(n);

  const positions: Record<string, { x: number; y: number }> = {};
  let maxRows = 1;
  for (const col of [0, 1, 2, 3]) {
    const group = byColumn[col].sort((a, b) => {
      const da = a.date ?? "";
      const db = b.date ?? "";
      if (da && db) return da.localeCompare(db);
      return a.label.localeCompare(b.label);
    });
    maxRows = Math.max(maxRows, group.length);
    group.forEach((n, i) => {
      positions[n.id] = {
        x: 24 + col * COL_GAP,
        // Centre shorter columns against the tallest one so the diagram is balanced.
        y: 24 + i * ROW_GAP,
      };
    });
  }
  // Vertical centring pass.
  for (const col of [0, 1, 2, 3]) {
    const group = byColumn[col];
    if (!group.length) continue;
    const offset = ((maxRows - group.length) * ROW_GAP) / 2;
    for (const n of group) positions[n.id].y += offset;
  }

  const width = 24 + 4 * COL_GAP;
  const height = 48 + maxRows * ROW_GAP;
  return { positions, width, height };
}

function GraphCanvas({
  nodes,
  edges,
  onSelect,
  selected,
}: {
  nodes: GNode[];
  edges: GEdge[];
  onSelect: (n: GNode | null) => void;
  selected: GNode | null;
}) {
  const [zoom, setZoom] = React.useState(1);
  const [hover, setHover] = React.useState<string | null>(null);
  const { positions, width, height } = React.useMemo(() => layout(nodes, edges), [nodes, edges]);

  if (nodes.length === 0) {
    return (
      <div className="p-5">
        <EmptyState
          title="No ownership graph"
          description="No ownership events could be derived from the documents on file, so no chain of title can be drawn."
        />
      </div>
    );
  }

  const focus = selected?.id ?? hover;
  const connected = new Set<string>();
  if (focus) {
    connected.add(focus);
    for (const e of edges) {
      if (e.source === focus) connected.add(e.target);
      if (e.target === focus) connected.add(e.source);
    }
  }

  return (
    <div className="relative">
      <div className="absolute right-4 top-4 z-10 flex items-center gap-1 rounded-lg border border-canvas-border bg-canvas-raised/95 p-1 shadow-card backdrop-blur">
        <button
          onClick={() => setZoom((z) => Math.max(0.5, z - 0.15))}
          className="rounded p-1.5 text-ink-muted transition hover:bg-canvas-sunken"
          aria-label="Zoom out"
        >
          <Minus className="h-3.5 w-3.5" />
        </button>
        <span className="tnum w-10 text-center text-2xs text-ink-muted">
          {Math.round(zoom * 100)}%
        </span>
        <button
          onClick={() => setZoom((z) => Math.min(1.8, z + 0.15))}
          className="rounded p-1.5 text-ink-muted transition hover:bg-canvas-sunken"
          aria-label="Zoom in"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={() => {
            setZoom(1);
            onSelect(null);
          }}
          className="rounded p-1.5 text-ink-muted transition hover:bg-canvas-sunken"
          aria-label="Reset"
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="scroll-x max-h-[620px] overflow-y-auto p-5">
        <svg
          width={width * zoom}
          height={height * zoom}
          viewBox={`0 0 ${width} ${height}`}
          className="select-none"
          style={{ minWidth: "100%" }}
        >
          <defs>
            {Object.entries(EDGE_STYLE).map(([type, s]) => (
              <marker
                key={type}
                id={`arrow-${type}`}
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill={s.stroke} />
              </marker>
            ))}
          </defs>

          {/* edges first so nodes sit above them */}
          {edges.map((e) => {
            const a = positions[e.source];
            const b = positions[e.target];
            if (!a || !b) return null;
            const style = EDGE_STYLE[e.type] ?? EDGE_STYLE.RECORDED_IN;
            const dim = Boolean(focus) && !(connected.has(e.source) && connected.has(e.target));
            const x1 = a.x + NODE_W;
            const y1 = a.y + NODE_H / 2;
            const x2 = b.x;
            const y2 = b.y + NODE_H / 2;
            const backwards = x2 < x1;
            const mx = (x1 + x2) / 2;
            const path = backwards
              ? `M ${a.x} ${y1} C ${a.x - 60} ${y1}, ${b.x + NODE_W + 60} ${y2}, ${b.x + NODE_W} ${y2}`
              : `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
            return (
              <g key={e.id} opacity={dim ? 0.14 : 1} className="transition-opacity">
                <path
                  d={path}
                  fill="none"
                  stroke={style.stroke}
                  strokeWidth={e.status === "CONFLICTING" ? 2 : 1.4}
                  strokeDasharray={style.dash}
                  markerEnd={`url(#arrow-${e.type})`}
                />
                {e.label ? (
                  <text
                    x={(x1 + x2) / 2}
                    y={(y1 + y2) / 2 - 6}
                    textAnchor="middle"
                    className="fill-current text-[9px]"
                    style={{ color: style.stroke }}
                  >
                    {e.label}
                  </text>
                ) : null}
              </g>
            );
          })}

          {nodes.map((n, i) => {
            const p = positions[n.id];
            if (!p) return null;
            const style = STATUS_STYLE[n.status] ?? STATUS_STYLE.NEUTRAL;
            const dim = Boolean(focus) && !connected.has(n.id);
            const isSelected = selected?.id === n.id;
            const Icon = NODE_ICON[n.type] ?? FileText;
            return (
              <motion.g
                key={n.id}
                initial={{ opacity: 0, scale: 0.94 }}
                animate={{ opacity: dim ? 0.25 : 1, scale: 1 }}
                transition={{ duration: 0.3, delay: Math.min(i * 0.02, 0.3) }}
                onMouseEnter={() => setHover(n.id)}
                onMouseLeave={() => setHover(null)}
                onClick={() => onSelect(isSelected ? null : n)}
                className="cursor-pointer"
              >
                <rect
                  x={p.x}
                  y={p.y}
                  width={NODE_W}
                  height={NODE_H}
                  rx={10}
                  fill={style.fill}
                  stroke={style.stroke}
                  strokeWidth={isSelected ? 2.4 : 1.3}
                />
                <foreignObject x={p.x} y={p.y} width={NODE_W} height={NODE_H}>
                  <div className="flex h-full items-center gap-2 px-2.5">
                    <span
                      className="grid h-6 w-6 shrink-0 place-items-center rounded-md"
                      style={{ background: style.stroke, color: "#fff" }}
                    >
                      <Icon className="h-3.5 w-3.5" />
                    </span>
                    <span className="min-w-0">
                      <span
                        className="block truncate text-[11px] font-semibold leading-tight"
                        style={{ color: style.text }}
                      >
                        {n.label}
                      </span>
                      <span className="block truncate text-[9px] leading-tight text-ink-subtle">
                        {n.sublabel || titleise(n.type)}
                        {n.date ? ` · ${new Date(n.date).getFullYear()}` : ""}
                      </span>
                    </span>
                  </div>
                </foreignObject>
              </motion.g>
            );
          })}
        </svg>
      </div>
      <p className="border-t border-canvas-border px-5 py-2.5 text-2xs text-ink-subtle">
        Click a node to see the evidence behind it. Columns read left to right: parties → parcel →
        charges and authorisations → instruments.
      </p>
    </div>
  );
}

/* --------------------------------------------------------------- timeline */

function Timeline({ entries }: { entries: any[] }) {
  if (!entries.length) {
    return (
      <div className="p-5">
        <EmptyState
          title="No dated events"
          description="No ownership events could be derived from the documents on file."
        />
      </div>
    );
  }
  return (
    <div className="p-5">
      <ol className="relative space-y-5 border-l-2 border-canvas-border pl-6">
        {entries.map((e, i) => {
          const tone =
            e.status === "CONFLICTING"
              ? "bg-status-conflicting"
              : e.status === "EXPIRED"
                ? "bg-status-expired"
                : "bg-navy-700";
          return (
            <motion.li
              key={`${e.date}-${i}`}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3, delay: i * 0.05 }}
              className="relative"
            >
              <span
                className={cn(
                  "absolute -left-[31px] top-1 grid h-4 w-4 place-items-center rounded-full ring-4 ring-canvas-raised",
                  tone,
                )}
              >
                <span className="h-1.5 w-1.5 rounded-full bg-white" />
              </span>
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="tnum text-sm font-semibold text-ink">{e.year}</span>
                <span className="text-2xs text-ink-subtle">{shortDate(e.date)}</span>
                {e.status === "CONFLICTING" ? <Chip tone="red">disputed</Chip> : null}
                {e.status === "EXPIRED" ? <Chip tone="amber">expired</Chip> : null}
              </div>
              <div className="mt-0.5 text-[13px] font-medium text-ink">{e.title}</div>
              {e.description ? (
                <p className="mt-0.5 text-2xs leading-relaxed text-ink-muted">{e.description}</p>
              ) : null}
              {e.evidence?.length ? (
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {e.evidence.map((ev: any, j: number) => (
                    <EvidenceChip key={j} document={ev.filename} page={ev.page} />
                  ))}
                </div>
              ) : null}
            </motion.li>
          );
        })}
      </ol>
    </div>
  );
}

/* -------------------------------------------------------------- inspector */

function NodeInspector({
  node,
  edges,
  nodes,
  onClear,
}: {
  node: GNode | null;
  edges: GEdge[];
  nodes: GNode[];
  onClear: () => void;
}) {
  if (!node) {
    return (
      <Card className="p-5">
        <div className="section-label mb-2">Node inspector</div>
        <p className="text-[13px] leading-relaxed text-ink-muted">
          Select a node in the graph to see what it is, when it became true, and which documents
          support it.
        </p>
      </Card>
    );
  }

  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const related = edges.filter((e) => e.source === node.id || e.target === node.id);

  return (
    <Card>
      <CardHeader
        title={node.label}
        subtitle={node.sublabel || titleise(node.type)}
        action={
          <Button variant="ghost" size="sm" onClick={onClear}>
            Clear
          </Button>
        }
      />
      <div className="space-y-3 p-5">
        <div className="flex flex-wrap gap-1.5">
          <Chip tone="navy">{titleise(node.type)}</Chip>
          {node.status !== "NEUTRAL" ? (
            <Chip
              tone={
                node.status === "CONFLICTING" ? "red" : node.status === "EXPIRED" ? "amber" : "emerald"
              }
            >
              {titleise(node.status)}
            </Chip>
          ) : null}
          {node.date ? <Chip tone="neutral">{shortDate(node.date)}</Chip> : null}
        </div>

        {node.evidence?.length ? (
          <div>
            <div className="section-label mb-1.5">Supporting evidence</div>
            <div className="flex flex-wrap gap-1.5">
              {node.evidence.map((ev: any, i: number) => (
                <EvidenceChip key={i} document={ev.filename ?? ev.document_id} page={ev.page} />
              ))}
            </div>
          </div>
        ) : null}

        {related.length ? (
          <div>
            <div className="section-label mb-1.5">Relationships</div>
            <ul className="space-y-1.5">
              {related.map((e) => {
                const other = byId[e.source === node.id ? e.target : e.source];
                const outgoing = e.source === node.id;
                return (
                  <li key={e.id} className="text-2xs leading-relaxed text-ink-muted">
                    <span
                      className="font-medium"
                      style={{ color: (EDGE_STYLE[e.type] ?? EDGE_STYLE.RECORDED_IN).stroke }}
                    >
                      {outgoing ? "" : "← "}
                      {titleise(e.type)}
                      {outgoing ? " →" : ""}
                    </span>{" "}
                    <span className="text-ink">{other?.label ?? "unknown"}</span>
                    {e.valid_from ? (
                      <span className="text-ink-subtle">
                        {" "}
                        · from {shortDate(e.valid_from)}
                        {e.valid_to ? ` to ${shortDate(e.valid_to)}` : ""}
                      </span>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

function Legend() {
  return (
    <Card className="p-5">
      <div className="section-label mb-3">Reading the graph</div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <div className="mb-2 text-2xs font-semibold text-ink">Node status</div>
          <ul className="space-y-1.5">
            {Object.entries(STATUS_STYLE)
              .filter(([k]) => k !== "VERIFIED")
              .map(([status, s]) => (
                <li key={status} className="flex items-center gap-2 text-2xs text-ink-muted">
                  <span
                    className="h-3 w-5 rounded"
                    style={{ background: s.fill, border: `1.5px solid ${s.stroke}` }}
                  />
                  {titleise(status)}
                  {status === "CONFLICTING" ? " — evidence disagrees" : ""}
                  {status === "EXPIRED" ? " — no longer in force" : ""}
                  {status === "CURRENT" ? " — the parcel itself" : ""}
                </li>
              ))}
          </ul>
        </div>
        <div>
          <div className="mb-2 text-2xs font-semibold text-ink">Relationship</div>
          <ul className="space-y-1.5">
            {["TRANSFERRED_TO", "OWNS", "MORTGAGED_TO", "AUTHORIZED", "CONTRADICTS"].map((type) => {
              const s = EDGE_STYLE[type];
              return (
                <li key={type} className="flex items-center gap-2 text-2xs text-ink-muted">
                  <svg width="22" height="8">
                    <line
                      x1="0"
                      y1="4"
                      x2="22"
                      y2="4"
                      stroke={s.stroke}
                      strokeWidth="1.6"
                      strokeDasharray={s.dash}
                    />
                  </svg>
                  {titleise(type)}
                </li>
              );
            })}
          </ul>
        </div>
      </div>
      <p className="mt-4 text-2xs leading-relaxed text-ink-subtle">
        Edges carry validity intervals, which is what lets the platform tell a discharged mortgage
        apart from a subsisting one, and a chain of title apart from a set of contradictions.
      </p>
    </Card>
  );
}
