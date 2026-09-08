"use client";

/**
 * Document Intelligence.
 *
 * Three things happen on this page, in the order a reviewer needs them:
 *   1. a real file goes through the real pipeline, and the visualisation ends up
 *      showing the stages the server actually reported — not a canned animation;
 *   2. every document already on the property is listed with what the pipeline made
 *      of it, and its stored telemetry can be replayed over SSE;
 *   3. any row opens the claim-level provenance viewer.
 */

import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  CheckCircle2,
  CircleDashed,
  Clock,
  Cpu,
  FileSearch,
  FileText,
  FolderOpen,
  Info,
  Layers3,
  Loader2,
  RotateCcw,
  ShieldAlert,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import React from "react";

import { DocumentViewer } from "@/components/document-viewer";
import { useApi, useQueryParam, useRole } from "@/components/hooks";
import {
  BandBadge,
  Button,
  Card,
  CardHeader,
  Chip,
  ConfidenceBar,
  DemoDataBadge,
  Disclaimer,
  Drawer,
  EmptyState,
  ErrorState,
  LoadingCard,
  SectionHeading,
  SeverityBadge,
  Skeleton,
  StateBadge,
  StatTile,
  StatusBadge,
  Tooltip,
} from "@/components/ui";
import { ApiError, endpoints } from "@/lib/api";
import {
  PIPELINE_STAGES,
  type RiskBand,
  type Severity,
  type TransactionState,
  type VerificationStatus,
} from "@/lib/domain";
import { cn, shortDate, titleise } from "@/lib/format";

/* ------------------------------------------------------------------- types */

type Stage = {
  stage: string;
  status: string;
  detail: string;
  duration_ms?: number | null;
  index?: number;
  total?: number;
};

type IntegrityFlag = {
  code: string;
  label: string;
  detail: string;
  severity: Severity;
  page?: number | null;
};

type DocumentRow = {
  id: string;
  filename: string;
  doc_type: string;
  doc_type_label: string;
  classification_confidence: number;
  classification_signals: Record<string, number>;
  status: string;
  extraction_mode: string;
  ocr_engine: string;
  page_count: number;
  size_bytes: number;
  processing_ms: number;
  reference_number: string | null;
  issued_on: string | null;
  valid_until: string | null;
  is_expired: boolean;
  integrity_flags: IntegrityFlag[];
  quality_score: number | null;
  created_at: string;
};

type UploadClaim = {
  id: string;
  label: string;
  claim_type: string;
  value: string;
  source_page: number | null;
  confidence: number;
  verification_status: VerificationStatus;
  masked?: boolean;
};

type Assessment = {
  overall_score: number;
  band: RiskBand;
  state: TransactionState;
  state_reason: string;
  factors?: { rule_id: string; title: string; severity: Severity; weight: number }[];
};

type UploadResult = {
  document: DocumentRow;
  claims: UploadClaim[];
  stages: Stage[];
  assessment: Assessment;
};

type ModeInfo = { engine: string; available: boolean; description: string };

type ModesPayload = {
  modes: Record<string, ModeInfo>;
  pipeline_stages: string[];
  accepted_extensions: string[];
  max_bytes: number;
  supported_categories: { value: string; label: string }[];
};

const STAGE_LABEL: Record<string, string> = Object.fromEntries(
  PIPELINE_STAGES.map((s) => [s.key, s.label]),
);

/* -------------------------------------------------------------------- page */

export default function DocumentIntelligencePage() {
  const [propertyRef, setPropertyRef] = useQueryParam("property", "LTC-PR-0002");
  const [role] = useRole();

  const properties = useApi<{ items: any[] }>(() => endpoints.properties(), []);
  const modes = useApi<ModesPayload>(() => endpoints.documentModes(), []);
  const documents = useApi<{ count: number; items: DocumentRow[] }>(
    () => endpoints.documents(propertyRef),
    [propertyRef, role],
  );
  const risk = useApi<Assessment>(() => endpoints.risk(propertyRef), [propertyRef]);
  // The document list carries no claim count, so the real one is derived by grouping
  // this property's claims by document rather than guessed at.
  const claims = useApi<{ items: { document_id: string }[] }>(
    () => endpoints.claims(propertyRef),
    [propertyRef, role],
  );

  const claimCounts = React.useMemo(() => {
    const counts: Record<string, number> = {};
    for (const claim of claims.data?.items ?? []) {
      if (!claim.document_id) continue;
      counts[claim.document_id] = (counts[claim.document_id] ?? 0) + 1;
    }
    return counts;
  }, [claims.data]);

  const [mode, setMode] = React.useState("DEMO");
  const [uploading, setUploading] = React.useState(false);
  const [uploadError, setUploadError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<UploadResult | null>(null);
  const [liveStages, setLiveStages] = React.useState<Stage[]>([]);
  const [beforeRisk, setBeforeRisk] = React.useState<Assessment | null>(null);
  const [openDocId, setOpenDocId] = React.useState<string | null>(null);

  const modeEntries = React.useMemo(
    () => Object.entries(modes.data?.modes ?? {}),
    [modes.data],
  );

  // If the configured default is unavailable in this deployment, fall back honestly.
  React.useEffect(() => {
    if (!modeEntries.length) return;
    const current = modeEntries.find(([key]) => key === mode);
    if (!current || !current[1].available) {
      const firstAvailable = modeEntries.find(([, m]) => m.available);
      if (firstAvailable) setMode(firstAvailable[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modeEntries]);

  /* --------------------------------------------------------- upload flow */

  const timerRef = React.useRef<ReturnType<typeof setInterval> | null>(null);
  React.useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
    },
    [],
  );

  const runUpload = React.useCallback(
    async (file: File) => {
      const cfg = modes.data;
      setUploadError(null);
      setResult(null);

      if (cfg) {
        const ext = `.${(file.name.split(".").pop() ?? "").toLowerCase()}`;
        if (!cfg.accepted_extensions.includes(ext)) {
          setUploadError(
            `"${ext}" is not an accepted format. Accepted: ${cfg.accepted_extensions.join(", ")}.`,
          );
          return;
        }
        if (file.size > cfg.max_bytes) {
          setUploadError(
            `${(file.size / 1024 / 1024).toFixed(1)} MB exceeds the ${Math.round(
              cfg.max_bytes / 1024 / 1024,
            )} MB limit for a single document.`,
          );
          return;
        }
      }

      setBeforeRisk(risk.data ?? null);
      setUploading(true);

      // Optimistic stage animation. It is replaced wholesale by the server's own
      // telemetry the moment the response lands, so nothing invented survives.
      const provisional = PIPELINE_STAGES.slice(0, PIPELINE_STAGES.length - 1);
      setLiveStages([
        { stage: provisional[0].key, status: "RUNNING", detail: provisional[0].detail },
      ]);
      let step = 0;
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = setInterval(() => {
        step = Math.min(step + 1, provisional.length - 1);
        setLiveStages(
          provisional.slice(0, step + 1).map((s, i) => ({
            stage: s.key,
            status: i === step ? "RUNNING" : "OK",
            detail: s.detail,
          })),
        );
      }, 320);

      const form = new FormData();
      form.append("property_id", propertyRef);
      form.append("file", file);
      form.append("mode", mode);

      try {
        const response = (await endpoints.uploadDocument(form)) as UploadResult;
        if (timerRef.current) clearInterval(timerRef.current);
        setResult(response);
        setLiveStages(response.stages); // the real thing, replacing the animation
        documents.refetch();
        risk.refetch();
        claims.refetch();
      } catch (err) {
        if (timerRef.current) clearInterval(timerRef.current);
        setLiveStages([]);
        setUploadError(
          err instanceof ApiError ? err.detail : (err as Error)?.message || "Upload failed.",
        );
      } finally {
        setUploading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [modes.data, propertyRef, mode, risk.data],
  );

  const currentProperty = (properties.data?.items ?? []).find(
    (p: any) => p.reference === propertyRef || p.id === propertyRef,
  );

  return (
    <div className="space-y-8">
      <SectionHeading
        eyebrow="Module 2"
        title="Document Intelligence"
        description="Upload a document and watch the pipeline that produces every claim on this platform: classification, text acquisition, layout analysis, claim extraction with page provenance, cross-document validation and a recomputed transaction risk. Every stage below is reported by the server."
        action={<DemoDataBadge />}
      />

      {/* ------------------------------------------------------ 1. upload */}
      <section className="space-y-4">
        <div className="grid gap-4 xl:grid-cols-[380px_minmax(0,1fr)]">
          <div className="space-y-4">
            <Card>
              <CardHeader
                title="Scope"
                subtitle="Everything uploaded here joins one property's evidence file."
                icon={<FolderOpen className="h-4 w-4" />}
              />
              <div className="space-y-4 p-5">
                <PropertyPicker
                  properties={properties.data?.items ?? []}
                  loading={properties.loading}
                  error={properties.error}
                  value={propertyRef}
                  onChange={(v) => {
                    setPropertyRef(v);
                    setResult(null);
                    setLiveStages([]);
                    setUploadError(null);
                  }}
                  onRetry={properties.refetch}
                />
                {currentProperty ? (
                  <div className="rounded-xl bg-canvas-sunken px-3.5 py-3">
                    <div className="text-[13px] font-medium text-ink">
                      {currentProperty.village}, {currentProperty.district}
                    </div>
                    <div className="mt-0.5 text-2xs text-ink-muted">
                      Survey {currentProperty.survey_number} · {currentProperty.scenario_label}
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <StateBadge state={currentProperty.transaction_state} size="sm" />
                      <BandBadge band={currentProperty.risk_band} />
                    </div>
                  </div>
                ) : null}
                <div>
                  <div className="section-label mb-1.5">Uploading as</div>
                  <p className="text-[13px] text-ink-muted">
                    <span className="font-medium text-ink">{titleise(role)}</span> — the role is
                    sent with the request, so masking on the extracted claims below is decided by
                    the server, not the browser.
                  </p>
                </div>
              </div>
            </Card>

            <Card>
              <CardHeader
                title="Extraction mode"
                subtitle="Which engine reads the file. Unavailable modes are shown, not hidden."
                icon={<Cpu className="h-4 w-4" />}
              />
              <div className="space-y-2 p-4">
                {modes.loading ? (
                  <>
                    <Skeleton className="h-16 w-full" />
                    <Skeleton className="h-16 w-full" />
                    <Skeleton className="h-16 w-full" />
                  </>
                ) : modes.error ? (
                  <ErrorState error={modes.error} onRetry={modes.refetch} />
                ) : (
                  modeEntries.map(([key, info]) => (
                    <button
                      key={key}
                      disabled={!info.available}
                      onClick={() => setMode(key)}
                      className={cn(
                        "w-full rounded-xl border px-3.5 py-3 text-left transition",
                        mode === key && info.available
                          ? "border-navy-500 bg-navy-50"
                          : "border-canvas-border hover:bg-canvas-sunken",
                        !info.available && "cursor-not-allowed opacity-60 hover:bg-transparent",
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[13px] font-semibold text-ink">{key}</span>
                        {info.available ? (
                          <Chip tone="emerald">available</Chip>
                        ) : (
                          <Chip tone="neutral">not configured</Chip>
                        )}
                      </div>
                      <div className="mt-1 font-mono text-2xs text-ink-muted">{info.engine}</div>
                      <p className="mt-1.5 text-2xs leading-relaxed text-ink-muted">
                        {info.description}
                      </p>
                    </button>
                  ))
                )}
              </div>
            </Card>
          </div>

          <div className="space-y-4">
            <Dropzone
              accepted={modes.data?.accepted_extensions ?? []}
              maxBytes={modes.data?.max_bytes ?? 0}
              busy={uploading}
              onFile={runUpload}
            />

            {uploadError ? (
              <Card className="border-status-conflicting/30 bg-status-conflictingBg p-4">
                <div className="flex items-start gap-2.5">
                  <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-status-conflicting" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-status-conflicting">
                      The file was not processed
                    </p>
                    <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
                      {uploadError}
                    </p>
                  </div>
                  <button
                    onClick={() => setUploadError(null)}
                    className="rounded p-1 text-ink-subtle hover:text-ink"
                    aria-label="Dismiss"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              </Card>
            ) : null}

            <TestDocumentHint propertyRef={propertyRef} />

            {liveStages.length ? (
              <PipelineTrack
                stages={liveStages}
                live={uploading}
                title={uploading ? "Pipeline running" : "Pipeline — as reported by the server"}
                subtitle={
                  uploading
                    ? "Provisional sequence; it is replaced by the server's own stage telemetry on completion."
                    : "Stage details and durations below are the ones the backend recorded for this file."
                }
              />
            ) : null}
          </div>
        </div>

        <AnimatePresence>
          {result ? (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
            >
              <UploadOutcome
                result={result}
                before={beforeRisk}
                onOpen={() => setOpenDocId(result.document.id)}
              />
            </motion.div>
          ) : null}
        </AnimatePresence>
      </section>

      {/* ----------------------------------------------------- 2. library */}
      <section className="space-y-4">
        <SectionHeading
          eyebrow="Evidence file"
          title="Document library"
          description="Everything the pipeline has processed for this property. A row opens the claim-level viewer; replay streams the stored stage telemetry back over server-sent events."
        />
        <DocumentLibrary
          documents={documents.data?.items ?? []}
          claimCounts={claimCounts}
          claimsLoading={claims.loading}
          loading={documents.loading}
          error={documents.error}
          onRetry={() => {
            documents.refetch();
            claims.refetch();
          }}
          onOpen={setOpenDocId}
        />
      </section>

      <Disclaimer />

      {/* ------------------------------------------------------ 3. viewer */}
      <Drawer
        open={Boolean(openDocId)}
        onClose={() => setOpenDocId(null)}
        title="Extraction & provenance"
        subtitle="Each claim points at the document, page and region it was read from."
        width="max-w-[1180px]"
      >
        {openDocId ? (
          <DocumentViewer propertyId={propertyRef} documentId={openDocId} />
        ) : null}
      </Drawer>
    </div>
  );
}

/* --------------------------------------------------------- property picker */

function PropertyPicker({
  properties,
  loading,
  error,
  value,
  onChange,
  onRetry,
}: {
  properties: any[];
  loading: boolean;
  error: any;
  value: string;
  onChange: (v: string) => void;
  onRetry: () => void;
}) {
  if (loading) return <Skeleton className="h-10 w-full" />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;
  if (!properties.length) {
    return <EmptyState title="No properties" description="The demo corpus has not been seeded." />;
  }
  return (
    <div>
      <label className="section-label mb-1.5 block" htmlFor="property-select">
        Property
      </label>
      <select
        id="property-select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-canvas-borderStrong bg-canvas-raised px-3 py-2 text-sm text-ink transition hover:bg-canvas-sunken"
      >
        {properties.map((p) => (
          <option key={p.id} value={p.reference}>
            {p.reference} — {p.village}, {p.district} ({p.scenario_label})
          </option>
        ))}
      </select>
    </div>
  );
}

/* ---------------------------------------------------------------- dropzone */

function Dropzone({
  accepted,
  maxBytes,
  busy,
  onFile,
}: {
  accepted: string[];
  maxBytes: number;
  busy: boolean;
  onFile: (file: File) => void;
}) {
  const [over, setOver] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0];
    if (file) onFile(file);
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!busy) setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        if (!busy) handleFiles(e.dataTransfer.files);
      }}
      className={cn(
        "rounded-2xl border-2 border-dashed px-6 py-10 text-center transition",
        over ? "border-navy-500 bg-navy-50" : "border-canvas-borderStrong bg-canvas-raised",
        busy && "opacity-80",
      )}
    >
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept={accepted.join(",")}
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-navy-50 text-navy-700">
        {busy ? (
          <Loader2 className="h-5 w-5 animate-spin" />
        ) : (
          <Upload className="h-5 w-5" />
        )}
      </div>
      <p className="mt-3 text-sm font-semibold text-ink">
        {busy ? "Processing through the live pipeline…" : "Drop a document here"}
      </p>
      <p className="mx-auto mt-1.5 max-w-md text-[13px] leading-relaxed text-ink-muted">
        The file is classified, read, and mined for claims by the same code path that produced
        every other document on this platform. Nothing about the result is pre-scripted.
      </p>
      <Button
        variant="secondary"
        size="sm"
        className="mt-4"
        disabled={busy}
        onClick={() => inputRef.current?.click()}
      >
        Choose a file
      </Button>
      <p className="mt-3 text-2xs text-ink-subtle">
        {accepted.length ? accepted.join(" · ") : "loading accepted formats…"}
        {maxBytes ? ` · up to ${Math.round(maxBytes / 1024 / 1024)} MB` : null}
      </p>
    </div>
  );
}

function TestDocumentHint({ propertyRef }: { propertyRef: string }) {
  return (
    <div className="rounded-2xl bg-status-infoBg px-4 py-3.5 ring-1 ring-status-info/15">
      <div className="flex items-start gap-2.5">
        <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-status-info" />
        <div className="min-w-0 text-[13px] leading-relaxed text-ink">
          <p className="font-semibold">Need a document to try this with?</p>
          <p className="mt-1 text-ink-muted">
            Ready-made synthetic PDFs ship with the repository at{" "}
            <code className="rounded bg-canvas-raised px-1.5 py-0.5 font-mono text-2xs text-ink">
              data/synthetic/{propertyRef}/
            </code>{" "}
            — drag any of them straight into the zone above. Files under{" "}
            <code className="rounded bg-canvas-raised px-1.5 py-0.5 font-mono text-2xs text-ink">
              data/synthetic/pending/
            </code>{" "}
            are held back from the seed specifically so they can be introduced live.
          </p>
          <p className="mt-1.5 text-ink-muted">
            Re-uploading a file that is already on this property demonstrates duplicate detection:
            the checksum matches an existing document, the copy is recorded as a duplicate rather
            than as a second independent witness, and risk rises instead of falling.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------- pipeline view */

function PipelineTrack({
  stages,
  live,
  title,
  subtitle,
}: {
  stages: Stage[];
  live: boolean;
  title: string;
  subtitle: string;
}) {
  const total = stages.length;
  return (
    <Card className="overflow-hidden">
      <CardHeader
        title={title}
        subtitle={subtitle}
        icon={live ? <Activity className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
        action={
          <span className="tnum text-2xs font-semibold text-ink-subtle">
            {total} stage{total === 1 ? "" : "s"}
          </span>
        }
      />
      <ol className="divide-y divide-canvas-border/70">
        {stages.map((s, i) => {
          const running = s.status === "RUNNING";
          const failed = s.status !== "OK" && !running;
          return (
            <motion.li
              key={`${s.stage}-${i}`}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.18 }}
              className="flex items-start gap-3 px-5 py-2.5"
            >
              <span className="mt-0.5 shrink-0">
                {running ? (
                  <Loader2 className="h-4 w-4 animate-spin text-navy-600" />
                ) : failed ? (
                  <ShieldAlert className="h-4 w-4 text-status-conflicting" />
                ) : (
                  <CheckCircle2 className="h-4 w-4 text-status-verified" />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <span className="text-[13px] font-semibold text-ink">
                    {STAGE_LABEL[s.stage] ?? titleise(s.stage)}
                  </span>
                  <span className="tnum text-2xs text-ink-subtle">
                    {s.duration_ms !== undefined && s.duration_ms !== null
                      ? `${s.duration_ms} ms`
                      : s.index !== undefined && s.total !== undefined
                        ? `${s.index + 1}/${s.total}`
                        : ""}
                  </span>
                </div>
                {s.detail ? (
                  <p className="mt-0.5 text-2xs leading-relaxed text-ink-muted">{s.detail}</p>
                ) : null}
              </div>
            </motion.li>
          );
        })}
        {live ? (
          <li className="flex items-center gap-3 px-5 py-2.5 text-2xs text-ink-subtle">
            <CircleDashed className="h-4 w-4 animate-pulse" />
            waiting for the server&apos;s stage telemetry…
          </li>
        ) : null}
      </ol>
    </Card>
  );
}

/* ------------------------------------------------------------ upload result */

function UploadOutcome({
  result,
  before,
  onOpen,
}: {
  result: UploadResult;
  before: Assessment | null;
  onOpen: () => void;
}) {
  const doc = result.document;
  const signals = Object.entries(doc.classification_signals ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
  const after = result.assessment;
  const delta = before ? Number((after.overall_score - before.overall_score).toFixed(1)) : null;
  const duplicate = (after.factors ?? []).find((f) => f.rule_id === "DUPLICATE_DOCUMENT");

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-4">
        <Card>
          <CardHeader
            title="Classified document"
            subtitle="What the classifier decided, and the signals that decided it."
            icon={<FileText className="h-4 w-4" />}
            action={
              <Button size="sm" variant="secondary" onClick={onOpen}>
                Open provenance viewer
              </Button>
            }
          />
          <div className="grid gap-4 p-5 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <div className="space-y-3">
              <div>
                <div className="section-label">File</div>
                <div className="mt-1 truncate text-sm font-medium text-ink">{doc.filename}</div>
              </div>
              <div>
                <div className="section-label">Type</div>
                <div className="mt-1 flex items-center gap-2">
                  <span className="text-sm font-medium text-ink">{doc.doc_type_label}</span>
                  <ConfidenceBar value={doc.classification_confidence} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="section-label">Pages</div>
                  <div className="tnum mt-1 text-sm text-ink">{doc.page_count}</div>
                </div>
                <div>
                  <div className="section-label">Processing</div>
                  <div className="tnum mt-1 text-sm text-ink">{doc.processing_ms} ms</div>
                </div>
                <div>
                  <div className="section-label">Mode</div>
                  <div className="mt-1 text-sm text-ink">{doc.extraction_mode}</div>
                </div>
                <div>
                  <div className="section-label">Engine</div>
                  <div className="mt-1 font-mono text-2xs text-ink-muted">{doc.ocr_engine}</div>
                </div>
              </div>
            </div>
            <div>
              <div className="section-label mb-2">Top classification signals</div>
              {signals.length ? (
                <ul className="space-y-1.5">
                  {signals.map(([signal, weight]) => {
                    const [type, pattern] = signal.split(":");
                    const max = signals[0][1] || 1;
                    return (
                      <li key={signal}>
                        <div className="flex items-baseline justify-between gap-2">
                          <code className="truncate font-mono text-2xs text-ink-muted">
                            {pattern}
                          </code>
                          <span className="tnum text-2xs font-semibold text-ink">
                            {weight.toFixed(2)}
                          </span>
                        </div>
                        <div className="mt-1 flex items-center gap-2">
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-canvas-sunken">
                            <div
                              className={cn(
                                "h-full rounded-full",
                                type === doc.doc_type ? "bg-navy-600" : "bg-canvas-borderStrong",
                              )}
                              style={{ width: `${Math.round((weight / max) * 100)}%` }}
                            />
                          </div>
                          <span className="text-2xs text-ink-subtle">{type}</span>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="text-2xs text-ink-muted">
                  No lexical signal fired — the document was left unclassified rather than guessed.
                </p>
              )}
            </div>
          </div>
        </Card>

        <Card className="overflow-hidden">
          <CardHeader
            title="Extracted claims"
            subtitle={`${result.claims.length} field${result.claims.length === 1 ? "" : "s"} bound to a page in this file, with the status derived across every document on the property.`}
            icon={<FileSearch className="h-4 w-4" />}
          />
          {result.claims.length ? (
            <div className="scroll-x">
              <table className="table-grid min-w-[720px]">
                <thead>
                  <tr>
                    <th>Claim</th>
                    <th>Value</th>
                    <th>Page</th>
                    <th>Confidence</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {result.claims.map((claim) => (
                    <tr key={claim.id}>
                      <td className="whitespace-nowrap text-[13px] font-medium text-ink">
                        {claim.label || titleise(claim.claim_type)}
                      </td>
                      <td
                        className={cn(
                          "text-[13px] text-ink",
                          claim.masked && "font-mono text-ink-muted",
                        )}
                      >
                        {claim.value}
                      </td>
                      <td className="tnum text-[13px] text-ink-muted">{claim.source_page ?? "—"}</td>
                      <td>
                        <ConfidenceBar value={claim.confidence} />
                      </td>
                      <td>
                        <StatusBadge status={claim.verification_status} size="sm" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-5">
              <EmptyState
                title="No claims extracted"
                description="The pipeline read the file but found no field it could bind to a page region."
              />
            </div>
          )}
        </Card>

        {doc.integrity_flags?.length ? (
          <Card>
            <CardHeader
              title="Integrity indicators"
              subtitle="Signals that the file itself warrants examination. An indicator is not a finding of forgery."
              icon={<ShieldAlert className="h-4 w-4" />}
            />
            <ul className="divide-y divide-canvas-border/70">
              {doc.integrity_flags.map((flag) => (
                <li key={flag.code} className="px-5 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <SeverityBadge severity={flag.severity} />
                    <span className="text-[13px] font-semibold text-ink">{flag.label}</span>
                    {flag.page ? (
                      <span className="text-2xs text-ink-subtle">page {flag.page}</span>
                    ) : null}
                    <code className="font-mono text-2xs text-ink-subtle">{flag.code}</code>
                  </div>
                  <p className="mt-1 text-2xs leading-relaxed text-ink-muted">{flag.detail}</p>
                </li>
              ))}
            </ul>
          </Card>
        ) : null}
      </div>

      <Card className="h-fit">
        <CardHeader
          title="Recomputed risk"
          subtitle="The composite score after this evidence was folded in."
          icon={<Activity className="h-4 w-4" />}
        />
        <div className="space-y-4 p-5">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-canvas-sunken px-3.5 py-3">
              <div className="section-label">Before</div>
              <div className="tnum mt-1 text-2xl font-semibold text-ink-muted">
                {before ? before.overall_score.toFixed(1) : "—"}
              </div>
              <div className="mt-1.5">
                {before ? <StateBadge state={before.state} size="sm" /> : null}
              </div>
            </div>
            <div className="rounded-xl bg-navy-50 px-3.5 py-3 ring-1 ring-navy-200">
              <div className="section-label">After</div>
              <div className="tnum mt-1 text-2xl font-semibold text-ink">
                {after.overall_score.toFixed(1)}
              </div>
              <div className="mt-1.5">
                <StateBadge state={after.state} size="sm" />
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <BandBadge band={after.band} />
            {delta !== null ? (
              <Chip tone={delta > 0 ? "red" : delta < 0 ? "emerald" : "neutral"}>
                {delta > 0 ? "+" : ""}
                {delta.toFixed(1)} points
              </Chip>
            ) : null}
          </div>

          <p className="text-[13px] leading-relaxed text-ink-muted">{after.state_reason}</p>

          {duplicate ? (
            <div className="rounded-xl bg-status-partialBg px-3.5 py-3 ring-1 ring-status-partial/20">
              <div className="flex items-center gap-2">
                <Layers3 className="h-3.5 w-3.5 text-status-partial" />
                <span className="text-[13px] font-semibold text-status-partial">
                  Duplicate detected
                </span>
              </div>
              <p className="mt-1 text-2xs leading-relaxed text-ink-muted">
                {duplicate.title} — a byte-identical copy adds no independent corroboration, so it
                is recorded as a duplicate and carries {duplicate.weight.toFixed(0)} risk points
                rather than strengthening the file.
              </p>
            </div>
          ) : null}

          {after.factors?.length ? (
            <div>
              <div className="section-label mb-2">Contributing factors</div>
              <ul className="space-y-1.5">
                {after.factors.slice(0, 6).map((f) => (
                  <li key={f.rule_id} className="flex items-start justify-between gap-2">
                    <span className="min-w-0 text-2xs leading-relaxed text-ink-muted">
                      {f.title}
                    </span>
                    <span className="tnum shrink-0 text-2xs font-semibold text-ink">
                      {f.weight > 0 ? "+" : ""}
                      {f.weight.toFixed(1)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </Card>
    </div>
  );
}

/* ----------------------------------------------------------------- library */

function DocumentLibrary({
  documents,
  claimCounts,
  claimsLoading,
  loading,
  error,
  onRetry,
  onOpen,
}: {
  documents: DocumentRow[];
  claimCounts: Record<string, number>;
  claimsLoading: boolean;
  loading: boolean;
  error: any;
  onRetry: () => void;
  onOpen: (id: string) => void;
}) {
  const [replay, setReplay] = React.useState<{
    docId: string;
    filename: string;
    frames: Stage[];
    done: boolean;
  } | null>(null);
  const sourceRef = React.useRef<EventSource | null>(null);

  const stopReplay = React.useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
  }, []);

  React.useEffect(() => () => stopReplay(), [stopReplay]);

  const startReplay = React.useCallback(
    (doc: DocumentRow) => {
      stopReplay();
      setReplay({ docId: doc.id, filename: doc.filename, frames: [], done: false });
      const es = new EventSource(`/api/documents/${doc.id}/pipeline`);
      sourceRef.current = es;
      es.onmessage = (event) => {
        try {
          const frame = JSON.parse(event.data) as Stage;
          setReplay((prev) =>
            prev && prev.docId === doc.id
              ? {
                  ...prev,
                  frames: [...prev.frames, frame],
                  done: frame.stage === "COMPLETE",
                }
              : prev,
          );
          if (frame.stage === "COMPLETE") {
            es.close();
            sourceRef.current = null;
          }
        } catch {
          /* a malformed frame is skipped rather than breaking the stream */
        }
      };
      es.onerror = () => {
        es.close();
        sourceRef.current = null;
        setReplay((prev) => (prev && prev.docId === doc.id ? { ...prev, done: true } : prev));
      };
    },
    [stopReplay],
  );

  if (loading) return <LoadingCard rows={8} title="Document library" />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;
  if (!documents.length) {
    return (
      <EmptyState
        title="No documents on this property yet"
        description="Upload one above, or pick a property from the seeded corpus."
        icon={<FolderOpen className="h-5 w-5" />}
      />
    );
  }

  const totalClaims = documents.reduce((n, d) => n + (claimCounts[d.id] ?? 0), 0);
  const flagged = documents.filter((d) => d.integrity_flags?.length).length;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Documents" value={documents.length} icon={<FileText className="h-4 w-4" />} />
        <StatTile
          label="Pages processed"
          value={documents.reduce((n, d) => n + d.page_count, 0)}
          icon={<Layers3 className="h-4 w-4" />}
        />
        <StatTile
          label="Median processing"
          value={`${median(documents.map((d) => d.processing_ms))} ms`}
          hint="Per document, end to end"
          icon={<Clock className="h-4 w-4" />}
        />
        <StatTile
          label="With integrity flags"
          value={flagged}
          tone={flagged ? "warn" : "neutral"}
          hint="Files that warrant examination"
          icon={<ShieldAlert className="h-4 w-4" />}
        />
      </div>

      <AnimatePresence>
        {replay ? (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <Card className="overflow-hidden">
              <CardHeader
                title={`Pipeline replay — ${replay.filename}`}
                subtitle="Streamed from the server as the stored stage telemetry for this document, one event per stage."
                icon={<RotateCcw className="h-4 w-4" />}
                action={
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      stopReplay();
                      setReplay(null);
                    }}
                  >
                    Close
                  </Button>
                }
              />
              <ol className="divide-y divide-canvas-border/70">
                {replay.frames.map((frame, i) => (
                  <motion.li
                    key={`${frame.stage}-${i}`}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="flex items-start gap-3 px-5 py-2"
                  >
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-status-verified" />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                        <span className="text-[13px] font-medium text-ink">
                          {STAGE_LABEL[frame.stage] ?? titleise(frame.stage)}
                        </span>
                        {frame.index !== undefined && frame.total !== undefined ? (
                          <span className="tnum text-2xs text-ink-subtle">
                            {frame.index + 1}/{frame.total}
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-0.5 text-2xs leading-relaxed text-ink-muted">
                        {frame.detail}
                      </p>
                    </div>
                  </motion.li>
                ))}
                {!replay.done ? (
                  <li className="flex items-center gap-3 px-5 py-2 text-2xs text-ink-subtle">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    streaming…
                  </li>
                ) : null}
              </ol>
            </Card>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <Card className="overflow-hidden">
        <div className="scroll-x">
          <table className="table-grid min-w-[1180px]">
            <thead>
              <tr>
                <th>Document</th>
                <th>Type</th>
                <th>Pages</th>
                <th>Extraction</th>
                <th>Quality</th>
                <th>Issued / valid</th>
                <th>Integrity</th>
                <th>Processing</th>
                <th>Claims</th>
                <th className="text-right">Replay</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr
                  key={doc.id}
                  className="clickable"
                  onClick={() => onOpen(doc.id)}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onOpen(doc.id);
                    }
                  }}
                >
                  <td>
                    <div className="text-[13px] font-medium text-ink">{doc.filename}</div>
                    <div className="mt-0.5 font-mono text-2xs text-ink-subtle">
                      {doc.reference_number ?? "no reference number"}
                    </div>
                  </td>
                  <td>
                    <div className="text-[13px] text-ink">{doc.doc_type_label}</div>
                    <div className="mt-1">
                      <ConfidenceBar value={doc.classification_confidence} />
                    </div>
                  </td>
                  <td className="tnum text-[13px] text-ink-muted">{doc.page_count}</td>
                  <td>
                    <div className="text-[13px] text-ink">{doc.extraction_mode}</div>
                    <div className="font-mono text-2xs text-ink-subtle">{doc.ocr_engine}</div>
                  </td>
                  <td>
                    {doc.quality_score === null ? (
                      <span className="text-[13px] text-ink-subtle">—</span>
                    ) : (
                      <ConfidenceBar value={doc.quality_score} />
                    )}
                  </td>
                  <td className="whitespace-nowrap text-[13px] text-ink-muted">
                    <div>{shortDate(doc.issued_on)}</div>
                    <div className="text-2xs text-ink-subtle">
                      {doc.valid_until ? `valid to ${shortDate(doc.valid_until)}` : "no stated expiry"}
                    </div>
                  </td>
                  <td>
                    <div className="flex flex-wrap items-center gap-1.5">
                      {doc.is_expired ? (
                        <Tooltip content="The document is past the validity it states. Claims resting solely on it are marked EXPIRED rather than verified.">
                          <span className="rounded px-1.5 py-0.5 text-2xs font-semibold uppercase tracking-wide text-status-expired bg-status-expiredBg">
                            Expired
                          </span>
                        </Tooltip>
                      ) : null}
                      {doc.integrity_flags?.length ? (
                        doc.integrity_flags.map((flag) => (
                          <Tooltip key={flag.code} content={flag.detail}>
                            <span className="inline-flex cursor-help items-center gap-1">
                              <SeverityBadge severity={flag.severity} />
                              <span className="text-2xs text-ink-muted">{flag.label}</span>
                            </span>
                          </Tooltip>
                        ))
                      ) : doc.is_expired ? null : (
                        <span className="text-2xs text-ink-subtle">none</span>
                      )}
                    </div>
                  </td>
                  <td className="tnum whitespace-nowrap text-[13px] text-ink-muted">
                    {doc.processing_ms} ms
                  </td>
                  <td className="tnum text-[13px] text-ink-muted">
                    {claimsLoading ? (
                      <Skeleton className="h-3.5 w-6" />
                    ) : (
                      (claimCounts[doc.id] ?? 0)
                    )}
                  </td>
                  <td className="text-right">
                    <Button
                      size="sm"
                      variant="subtle"
                      onClick={(e) => {
                        e.stopPropagation();
                        startReplay(doc);
                      }}
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                      Replay
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <p className="flex items-start gap-2 text-2xs leading-relaxed text-ink-subtle">
        <Info className="mt-px h-3.5 w-3.5 shrink-0" />
        <span>
          {documents.length} document{documents.length === 1 ? "" : "s"} · {totalClaims} extracted
          claims on this property. Claim counts are derived by grouping the property&apos;s claim
          records by document — the document list itself does not carry one. Open a row for the
          exact list with page regions.
        </span>
      </p>
    </div>
  );
}

/* --------------------------------------------------------------- utilities */

function median(values: number[]): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : Math.round((sorted[mid - 1] + sorted[mid]) / 2);
}
