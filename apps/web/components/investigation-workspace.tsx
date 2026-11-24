"use client";

import { useEffect, useRef, useState } from "react";
import type { Repository } from "@/lib/types";
import { PatchProposals } from "@/components/patch-proposals";
import { InvestigationController, safeCitation, safeIssueUrl, validIssueOrigin } from "@/lib/investigation-client";
import type { Citation, Evidence, InvestigationView, IssueContext, IssueOrigin, Job, ReportEnvelope } from "@/lib/investigation-client";

const blank: InvestigationView = { context: null, job: null, evidence: null, report: null,
  reportMissing: false, acceptedJobId: null, busy: "", error: "", notice: "" };
const label: Record<string, string> = { queued: "Queued", running: "Running", completed: "Completed",
  failed: "Failed", cancelled: "Cancelled or access denied" };
const safeErrors: Record<string, string> = { repository_unavailable: "Repository access is unavailable.",
  session_unavailable: "The session is no longer available.", invalid_session: "The session is no longer available.",
  snapshot_unavailable: "The selected snapshot is unavailable.", issue_unavailable: "The issue is unavailable.",
  issue_changed: "The issue changed during processing.", attempts_exhausted: "The retry limit was reached.",
  worker_timeout: "The worker timed out and may retry.", database_temporarily_unavailable: "Storage is temporarily unavailable.",
  github_verification_unavailable: "GitHub access could not be verified.", invalid_evidence: "The evidence could not be verified.",
  model_output_invalid: "The report response was invalid.", model_output_too_large: "The report response was too large.",
  model_not_enabled: "The selected report provider is disabled.",
  budget_exhausted: "The report experiment budget is exhausted.",
  budget_unavailable: "The report experiment is unavailable.",
  model_billing_unknown: "The request outcome is uncertain and will not be retried automatically." };
const safeError = (code: string | null) => code && Object.hasOwn(safeErrors, code) ? safeErrors[code] : null;

function date(value: string) {
  const result = new Date(value);
  return Number.isNaN(result.valueOf()) ? "Unavailable" : result.toLocaleString();
}

export function IssueContextView({ issue, repository, origin }: { issue: IssueContext; repository: Repository; origin?: IssueOrigin | null }) {
  const issueRepository = origin ? { id: origin.repository_id, full_name: origin.repository, enabled: true } : repository;
  const truncated = Object.values(issue.truncation).some(Boolean);
  return <section aria-label="Issue context" className="rounded-xl border border-edge bg-card/40 p-4 sm:p-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-semibold text-ice">ISSUE #{issue.number} · {issue.state.toUpperCase()}</p>
      <h3 className="mt-1 text-lg font-semibold text-heading">{issue.title}</h3></div>
      {safeIssueUrl(issue.url, issueRepository, issue.number) && <a href={issue.url} target="_blank" rel="noopener noreferrer" className="text-sm font-semibold text-ice hover:underline">Open on GitHub ↗</a>}</div>
    {issue.labels.length > 0 && <p className="mt-3 text-xs text-muted">Labels: {issue.labels.join(", ")}</p>}
    <p className="mt-4 max-w-prose whitespace-pre-wrap break-words text-sm leading-6 text-body">{issue.body || "No issue description provided."}</p>
    {issue.comments.length > 0 && <details className="mt-4 text-sm text-body"><summary className="cursor-pointer font-semibold">Comments ({issue.comments.length})</summary>
      {issue.comments.map(comment => <div key={comment.id} className="mt-3 rounded-lg bg-card/45 p-3"><p className="max-w-prose whitespace-pre-wrap break-words">{comment.body}</p><p className="mt-2 text-xs text-muted">Updated {date(comment.updated_at)}{comment.truncated ? " · Truncated" : ""}</p></div>)}</details>}
    {truncated && <p role="status" className="mt-3 text-xs font-semibold text-amber-200">Issue context was truncated; some content is not shown.</p>}
    <p className="mt-4 text-xs text-muted">Created {date(issue.created_at)} · Updated {date(issue.updated_at)} · Retrieved {date(issue.retrieved_at)}</p>
  </section>;
}

export function InvestigationStatus({ job, repository }: { job: Job; repository?: Repository }) {
  return <section aria-label="Investigation status" className="rounded-xl border border-edge p-4 sm:p-5">
    <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">Investigation status</h3>
      <span role="status" aria-live="polite" data-status={job.status} className="status-pill rounded-full px-3 py-1 text-xs font-semibold">{label[job.status]}</span></div>
    <p className="mt-2 text-sm text-muted">{{ queued: "Waiting for a worker.", running: "The worker is processing this investigation.", completed: "The investigation has completed.", failed: "The investigation could not be completed.", cancelled: "The investigation was cancelled or access changed." }[job.status]}</p>
    <p className="mt-2 break-all font-mono text-xs text-muted">Job {job.job_id}</p>
    <p className="mt-2 text-sm text-muted">Worker attempts: {job.attempts} · Evidence: {job.evidence_count}</p>
    {job.operation === "mock_orchestration" && <p className="mt-2 text-sm text-muted">This mock orchestration does not retrieve source evidence or produce an investigation report.</p>}
    {job.snapshot_id && <p className="mt-2 break-all text-xs text-muted">Snapshot {job.snapshot_id}</p>}
    {job.commit_sha && <p className="mt-1 break-all font-mono text-xs text-muted">Commit {job.commit_sha}</p>}
    {job.issue_origin && <p className="mt-2 text-sm text-muted">Upstream issue: <a className="text-ice underline" href={job.issue_origin.url} target="_blank" rel="noopener noreferrer">{job.issue_origin.repository}#{job.issue_origin.issue_number}</a> · Verified direct public parent.</p>}
    {job.issue_origin && repository && <p className="mt-1 text-sm text-muted">Investigating fork: {repository.full_name}</p>}
    {job.snapshot_inventory?.classification === "PARTIAL_INVENTORY" && <div className="mt-2 text-xs text-muted">
      <p>Pinned partial snapshot · {job.snapshot_inventory.files.length} source {job.snapshot_inventory.files.length === 1 ? "file" : "files"} included</p>
      <p className="mt-1 break-all font-mono">Manifest SHA-256: {job.snapshot_inventory.manifest_sha256}</p>
      <ul className="mt-1 space-y-1">{job.snapshot_inventory.files.map(file => <li key={file.path} className="break-all">{file.path} · Complete file identity verified · {file.byte_length} bytes · SHA-256 {file.sha256}</li>)}</ul>
    </div>}
    {job.snapshot_partial && <p role="status" className="mt-2 text-sm font-semibold text-amber-200">PARTIAL REPOSITORY SNAPSHOT — SOME FILES WERE NOT INDEXED. Analysis covers only indexed evidence and may have missed relevant code.</p>}
    {job.retrieval_status === "snapshot_unavailable" && <p role="alert" className="mt-2 text-sm text-amber-200">The selected snapshot is no longer available. Evidence cannot be shown.</p>}
    {(job.status === "failed" || job.status === "cancelled") && <p role="alert" className="mt-2 text-sm text-red-300">The investigation did not complete. Check repository access and try again.</p>}
    {safeError(job.error_code) && <p className="mt-2 text-xs text-muted">{safeError(job.error_code)}</p>}
  </section>;
}

export function EvidenceView({ evidence, repository }: { evidence: Evidence; repository: Repository }) {
  const [copyNotice, setCopyNotice] = useState("");
  async function copy(value: string, description: string) {
    try { await navigator.clipboard.writeText(value); setCopyNotice(`${description} copied.`); }
    catch { setCopyNotice(`Could not copy ${description.toLowerCase()}.`); }
  }
  return <section aria-label="Retrieved code evidence"><div className="mb-3 flex flex-wrap items-center justify-between gap-2"><div><h3 className="font-semibold">Retrieved code evidence</h3><p className="mt-1 text-xs text-muted">Candidates from the selected snapshot, not verified causes.</p></div><span className="text-xs text-muted">{evidence.items.length} results</span></div>
    {copyNotice && <p role="status" className="mb-3 text-sm text-muted">{copyNotice}</p>}
    {evidence.items.length > 1 && <nav aria-label="Evidence results" className="mb-4 flex flex-wrap gap-2">{evidence.items.map(item => <a key={item.chunk_id} href={`#evidence-${item.chunk_id}`} className="rounded border border-edge-strong px-2 py-1 text-xs text-body focus-visible:outline-2 focus-visible:outline-amethyst" aria-label={`Go to evidence rank ${item.rank}`}>{item.rank}</a>)}</nav>}
    {!evidence.items.length ? <p className="rounded-lg bg-card/40 p-4 text-sm text-muted">No code evidence was retrieved. The issue may need more detail or a different snapshot.</p> :
      <div className="space-y-3">{evidence.items.map(item => <article id={`evidence-${item.chunk_id}`} key={item.chunk_id} className="overflow-hidden rounded-xl border border-edge">
        <div className="flex flex-wrap justify-between gap-3 p-4"><div className="min-w-0"><p className="text-xs font-semibold text-ice">Rank {item.rank} · {item.method} · {item.query_id} (query rank {item.query_rank})</p>
          <p className="mt-1 break-all text-sm font-semibold">{item.path}</p><p className="mt-1 text-xs text-muted">{item.symbol ?? "Module"} · lines {item.start_line}–{item.end_line}</p>
          <p className="mt-1 break-all font-mono text-xs text-muted">{item.commit_sha}</p></div>
          <div className="flex flex-wrap items-start gap-3 text-sm"><button type="button" className="font-semibold text-ice hover:underline" onClick={() => { void copy(item.path, "File path"); }}>Copy path</button>
          {safeCitation(item, repository) && <><button type="button" className="font-semibold text-ice hover:underline" onClick={() => { void copy(item.url, "Citation"); }}>Copy citation</button><a href={item.url} target="_blank" rel="noopener noreferrer" className="font-semibold text-ice hover:underline">View source ↗</a></>}</div></div>
        {item.snippet === null ? <p className="border-t border-edge p-4 text-xs text-amber-200">Source excerpt withheld by the safety screen.</p> :
          <pre className="overflow-x-auto bg-evidence p-4 text-xs leading-6 text-heading"><code>{item.snippet}</code></pre>}
        {item.snippet_truncated && <p className="px-4 py-2 text-xs text-amber-200">Source excerpt truncated; the citation covers the full chunk.</p>}
      </article>)}</div>}
  </section>;
}

function Citations({ items, repository }: { items: Citation[]; repository: Repository }) {
  if (!items.length) return <p className="mt-1 text-xs text-muted">None cited.</p>;
  return <ul className="mt-2 space-y-1">{items.map(item => <li key={item.chunk_id} className="break-all text-sm">
    {safeCitation(item, repository) ? <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-ice hover:underline">{item.path} · lines {item.start_line}–{item.end_line} ↗</a> : <span>Citation unavailable</span>}
  </li>)}</ul>;
}

function TextList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return <div className="mt-4"><h5 className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</h5>
    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-body">{items.map((item, index) => <li key={index}>{item}</li>)}</ul></div>;
}

export function InvestigationReport({ envelope, repository }: { envelope: ReportEnvelope; repository: Repository }) {
  if (envelope.status !== "completed" || !envelope.report) return <section aria-label="Report status" className="rounded-xl border border-edge p-4">
    <h3 className="font-semibold">Report {label[envelope.status]}</h3>
    {(envelope.status === "failed" || envelope.status === "cancelled") && <p role="alert" className="mt-2 text-sm text-red-300">The report could not be completed.</p>}
    {safeError(envelope.error_code) && <p className="mt-2 text-xs text-muted">{safeError(envelope.error_code)}</p>}
  </section>;
  const report = envelope.report;
  return <section aria-label="Investigation report" className="rounded-xl border border-amber-400/30 bg-amber-950/30 p-4 sm:p-5">
    <p className="text-xs font-bold tracking-wide text-amber-200">{report.provider === "mock"
      ? "MOCK REPORT — DEMONSTRATION ONLY" : "MODEL-GENERATED REPORT — HUMAN REVIEW REQUIRED"}</p>
    <h3 className="mt-2 text-lg font-semibold">Investigation report</h3>
    <p className="mt-1 text-xs text-muted">{report.provider} · {report.model} · {date(report.created_at)}</p>
    <p className="mt-3 text-sm text-body">{report.disclaimer}</p>
    {report.provider === "mock" && <p className="mt-2 text-sm text-amber-200">This deterministic demonstration does not establish real AI diagnosis quality.</p>}
    <h4 className="mt-5 text-sm font-semibold">Issue summary</h4><p className="mt-1 max-w-prose whitespace-pre-wrap text-sm text-body">{report.summary}</p>
    {!report.hypotheses.length && <p className="mt-4 rounded-lg bg-card/45 p-3 text-sm text-muted">No supported hypotheses were produced. More evidence is needed.</p>}
    <div className="mt-4 space-y-3">{report.hypotheses.map((h, index) => <article key={index} className="rounded-lg border border-amber-400/25 bg-card/45 p-4">
      <h4 className="font-semibold">{index + 1}. {h.title}</h4><p className="mt-1 text-xs font-semibold text-amber-200">{h.support_status} · uncertainty: {h.uncertainty}</p>
      <p className="mt-2 max-w-prose whitespace-pre-wrap text-sm text-body">{h.explanation}</p>
      <TextList title="Observations" items={h.observations} /><TextList title="Missing or contradictory information" items={h.missing_or_contradictory} />
      <h5 className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted">Supporting evidence</h5><Citations items={h.evidence} repository={repository} />
      <h5 className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted">Contradictory evidence</h5><Citations items={h.contradictory_evidence} repository={repository} />
    </article>)}</div>
    <TextList title="Missing evidence" items={report.missing_evidence} /><TextList title="Next diagnostic steps" items={report.next_steps} />
    <TextList title="Warnings and limitations" items={report.warnings} />
    {(report.input_truncated || report.snapshot_partial) && <p className="mt-3 text-xs text-amber-200">The input or source snapshot was incomplete.</p>}
  </section>;
}

type RuleFinding = { rule_id: string; explanation: string; uncertainty: string; next_steps: string[];
  signals: { kind: string; value: string; origin: string; line: number; source_line?: number | null; symbol?: string | null }[]; citation: Citation };
type RuleAnalysis = { job_id: string; repository_id: string; snapshot_id: string; commit_sha: string; abstained: boolean;
  findings: RuleFinding[]; limitations: string[] };

export function validateRuleAnalysis(value: unknown, job: Job, evidence: Evidence, repository: Repository): RuleAnalysis {
  if (!value || typeof value !== "object") throw new Error("Invalid analysis");
  const result = value as RuleAnalysis & { version: string };
  const safeText = (text: unknown, max: number): text is string => typeof text === "string" && text.length <= max;
  if (result.version !== "cie-v1" || result.job_id !== job.job_id || result.repository_id !== repository.id || result.snapshot_id !== job.snapshot_id ||
      result.commit_sha !== job.commit_sha || typeof result.abstained !== "boolean" ||
      !Array.isArray(result.findings) || result.findings.length > 10 ||
      !Array.isArray(result.limitations) || result.limitations.length > 16 || !result.limitations.every(x => safeText(x, 300))) throw new Error("Invalid analysis");
  for (const finding of result.findings) {
    const citation = finding?.citation;
    const match = evidence.items.find(item => item.chunk_id === citation?.chunk_id);
    if (!match || !citation || citation.snapshot_id !== job.snapshot_id || citation.commit_sha !== match.commit_sha ||
        citation.path !== match.path || citation.start_line !== match.start_line || citation.end_line !== match.end_line ||
        citation.url !== match.url || !safeCitation(citation, repository) ||
        !["traceback_location", "explicit_source_match", "exception_alignment", "import_alignment"].includes(finding.rule_id) ||
        !safeText(finding.explanation, 500) || finding.uncertainty !== "high" ||
        !Array.isArray(finding.next_steps) || finding.next_steps.length > 4 || !finding.next_steps.every(x => safeText(x, 500)) ||
        !Array.isArray(finding.signals) || finding.signals.length > 4 ||
        !finding.signals.every(x => x && safeText(x.kind, 40) && safeText(x.value, 300) &&
          ["title", "body"].includes(x.origin) && Number.isInteger(x.line) && x.line >= 1 && x.line <= 200 &&
          (x.source_line == null || (Number.isInteger(x.source_line) && x.source_line > 0 && x.source_line <= 1000000)) &&
          (x.symbol == null || safeText(x.symbol, 64)))) throw new Error("Invalid analysis");
  }
  if (result.abstained !== (result.findings.length === 0)) throw new Error("Invalid analysis");
  return result;
}

export function CodeIntelligence({ job, evidence, repository }: { job: Job; evidence: Evidence; repository: Repository }) {
  const [result, setResult] = useState<RuleAnalysis | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const inFlight = useRef<AbortController | null>(null);
  useEffect(() => () => { const pending = inFlight.current; inFlight.current = null; pending?.abort(); }, []);
  async function run() {
    if (inFlight.current) return;
    const controller = new AbortController(); inFlight.current = controller;
    const timer = setTimeout(() => controller.abort(), 20000);
    setBusy(true); setError(""); setResult(null);
    try {
      const response = await fetch(`/api/investigations/${repository.id}/jobs/${job.job_id}/code-intelligence`,
        { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error(response.status === 401 ? "Your session has expired." :
        response.status === 404 ? "Repository or investigation is unavailable." :
        response.status === 409 ? "The issue, snapshot or evidence changed; analysis is unavailable." : "Analysis is unavailable. Try again.");
      const data = validateRuleAnalysis(await response.json(), job, evidence, repository);
      if (!controller.signal.aborted) setResult(data);
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure instanceof Error && ["Your session has expired.",
        "Repository or investigation is unavailable.", "The issue, snapshot or evidence changed; analysis is unavailable."].includes(failure.message)
        ? failure.message : "Analysis is unavailable. Try again.");
      else if (inFlight.current === controller) setError("Analysis timed out or was cancelled.");
    } finally { clearTimeout(timer); if (inFlight.current === controller) { inFlight.current = null; setBusy(false); } }
  }
  return <section aria-label="Code Intelligence rule-based analysis" className="rounded-xl border border-edge p-4 sm:p-5">
    <h3 className="font-semibold">Code Intelligence — Rule-Based Analysis</h3>
    <p className="mt-2 text-xs font-bold text-amber-200">RULE-BASED ANALYSIS — POSSIBLE CAUSES, NOT VERIFIED</p>
    <p className="mt-2 text-sm text-muted">Inspect existing evidence with bounded Python static analysis. This does not run repository code or establish a diagnosis.</p>
    <button type="button" className="button mt-3" disabled={busy} onClick={() => { void run(); }}>{busy ? "Analyzing…" : "Analyze existing evidence"}</button>
    {busy && <p role="status" className="mt-2 text-sm">Analyzing evidence…</p>}{error && <p role="alert" className="mt-2 text-sm text-red-300">{error}</p>}
    {result && <div className="mt-4 space-y-3">{result.abstained && <p className="text-sm text-muted">Insufficient matching evidence; no candidate finding was produced.</p>}
      {result.findings.map(finding => <article key={`${finding.rule_id}-${finding.citation.chunk_id}`} className="rounded-lg bg-card/40 p-3">
        <p className="text-sm font-semibold">{finding.explanation}</p><p className="mt-1 text-xs text-muted">Uncertainty: {finding.uncertainty}</p>
        <p className="mt-2 break-all text-sm"><a href={finding.citation.url} target="_blank" rel="noopener noreferrer" className="text-ice underline">{finding.citation.path} · lines {finding.citation.start_line}–{finding.citation.end_line}</a></p>
        <p className="mt-2 break-words text-xs text-muted">Observed: {finding.signals.map(signal => `${signal.kind}: ${signal.value}${signal.source_line ? `, source line ${signal.source_line}` : ""}${signal.symbol ? `, ${signal.symbol}` : ""} (${signal.origin} line ${signal.line})`).join("; ")}</p>
        <TextList title="Diagnostic checks" items={finding.next_steps} /></article>)}
      <TextList title="Analysis limitations" items={result.limitations} /></div>}
  </section>;
}

type HistoryItem = { job_id: string; issue_number: number; issue_title: string | null; status: string;
  created_at: string; updated_at: string; attempts: number; evidence_count: number; report_status: string | null;
  operation: string; issue_origin?: IssueOrigin | null };
type HistoryPage = { items: HistoryItem[]; next_offset: number | null };

export function parseHistory(value: unknown): HistoryPage {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid history");
  const page = value as HistoryPage;
  const states = ["queued", "running", "completed", "failed", "cancelled"];
  if (!Array.isArray(page.items) || page.items.length > 20 ||
      !(page.next_offset === null || (Number.isInteger(page.next_offset) && page.next_offset >= 0 && page.next_offset <= 10000)) ||
      !page.items.every(item => item && typeof item.job_id === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(item.job_id) &&
        Number.isInteger(item.issue_number) && item.issue_number > 0 && item.issue_number < 2147483648 &&
        (item.issue_title === null || (typeof item.issue_title === "string" && item.issue_title.length <= 1024)) &&
        states.includes(item.status) && typeof item.created_at === "string" && item.created_at.length <= 64 &&
        typeof item.updated_at === "string" && item.updated_at.length <= 64 && Number.isInteger(item.attempts) && item.attempts >= 0 &&
        Number.isInteger(item.evidence_count) && item.evidence_count >= 0 && item.evidence_count <= 30 &&
        (item.report_status === null || states.includes(item.report_status)) &&
        ["code_evidence", "mock_orchestration"].includes(item.operation) &&
        (item.issue_origin === undefined || item.issue_origin === null || validIssueOrigin(item.issue_origin, item.issue_number)))) throw new Error("Invalid history");
  return page;
}

export function InvestigationHistory({ repository, onOpen, disabled = false }: { repository: Repository; onOpen: (item: HistoryItem) => void; disabled?: boolean }) {
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [page, setPage] = useState<HistoryPage | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const change = () => setVisible(document.visibilityState !== "hidden");
    change(); document.addEventListener("visibilitychange", change);
    return () => document.removeEventListener("visibilitychange", change);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let recheck: ReturnType<typeof setTimeout> | undefined;
    if (!visible) { queueMicrotask(() => { if (active) { setPage(null); setLoading(false); } }); return () => { active = false; controller.abort(); }; }
    const timer = setTimeout(() => controller.abort(), 20000);
    queueMicrotask(() => { if (active) { setPage(null); setError(""); setLoading(true); } });
    const params = new URLSearchParams({ limit: "20", offset: String(offset) });
    if (status) params.set("status", status);
    void (async () => {
      try {
        const response = await fetch(`/api/investigations/${repository.id}/history?${params}`, { cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error(response.status === 401 ? "Your session has expired. Sign in again." :
          response.status === 404 ? "Repository access is unavailable." : "Investigation history is unavailable. Try again.");
        const result = parseHistory(await response.json());
        if (active) { setPage(result); recheck = setTimeout(() => setRevision(value => value + 1), 30000); }
      } catch (failure) {
        if (active) setError(failure instanceof Error && failure.name === "AbortError" ? "History request timed out. Try again." :
          failure instanceof Error && ["Your session has expired. Sign in again.", "Repository access is unavailable."].includes(failure.message) ? failure.message : "Investigation history is unavailable. Try again.");
      } finally { clearTimeout(timer); if (active) setLoading(false); }
    })();
    return () => { active = false; clearTimeout(timer); clearTimeout(recheck); controller.abort(); };
  }, [repository.id, status, offset, revision, visible]);
  return <section aria-label="Investigation history" className="mt-6 rounded-xl border border-edge p-4 sm:p-5">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><h3 className="font-semibold">Investigation history</h3><p className="mt-1 text-xs text-muted">Your investigations for this repository.</p></div>
      <label className="text-sm">Status <select value={status} onChange={event => { setOffset(0); setStatus(event.target.value); }} className="ml-2 rounded border border-edge-strong bg-card/45 p-2">
        <option value="">All statuses</option>{Object.entries(label).map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label></div>
    {loading && <p role="status" className="mt-4 text-sm text-muted">Loading investigation history…</p>}
    {error && <div role="alert" className="mt-4 text-sm text-red-300">{error} <button type="button" className="font-semibold underline" onClick={() => setRevision(value => value + 1)}>Retry history</button></div>}
    {page && (page.items.length === 0 ? <p className="mt-4 text-sm text-muted">No investigations found for this selection.</p> :
      <ul className="mt-4 space-y-3">{page.items.map(item => <li key={item.job_id} className="rounded-lg border border-edge p-3">
        <div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><p className="break-words text-sm font-semibold">{item.issue_origin ? `Upstream issue ${item.issue_origin.repository}#${item.issue_number}` : `Issue #${item.issue_number}`}{item.issue_title ? ` · ${item.issue_title}` : ""}</p>
          <p className="mt-1 text-xs text-muted">{label[item.status]} · {item.evidence_count} evidence · {item.attempts} attempts · Report: {item.report_status ? label[item.report_status] : "Not generated"}</p></div>
          <button type="button" className="button" disabled={disabled} onClick={() => onOpen(item)} aria-label={`Open investigation for issue ${item.issue_number}, job ${item.job_id}`}>Open investigation</button></div>
        <p className="mt-2 break-all font-mono text-xs text-muted">{item.job_id}</p><p className="mt-1 text-xs text-muted">Created {date(item.created_at)} · Updated {date(item.updated_at)}</p>
      </li>)}</ul>)}
    <div className="mt-4 flex flex-wrap gap-2"><button type="button" className="button" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</button>
      <button type="button" className="button" disabled={!page?.next_offset || loading} onClick={() => setOffset(page?.next_offset ?? offset)}>Next</button>
      <button type="button" className="button" disabled={loading} onClick={() => setRevision(value => value + 1)}>Refresh history</button></div>
  </section>;
}

export function InvestigationWorkspace({ repository, selectedIssue }: { repository: Repository; selectedIssue?: { number: number } }) {
  const controller = useRef<InvestigationController | null>(null);
  const [view, setView] = useState<InvestigationView>(blank);
  const [issue, setIssue] = useState("");
  const [jobId, setJobId] = useState("");
  useEffect(() => {
    const instance = new InvestigationController({ id: repository.id, full_name: repository.full_name, enabled: repository.enabled });
    controller.current = instance;
    const unsubscribe = instance.subscribe(setView);
    return () => { unsubscribe(); instance.dispose(); controller.current = null; };
  }, [repository.id, repository.full_name, repository.enabled]);
  useEffect(() => {
    let active = true;
    if (selectedIssue) queueMicrotask(() => { if (active) { setIssue(String(selectedIssue.number)); void controller.current?.loadIssue(String(selectedIssue.number)); } });
    return () => { active = false; };
  }, [selectedIssue, repository.id]);
  useEffect(() => {
    const visibility = () => { if (document.visibilityState === "hidden") controller.current?.hideResults();
      else controller.current?.showResults(); };
    document.addEventListener("visibilitychange", visibility);
    visibility();
    return () => document.removeEventListener("visibilitychange", visibility);
  }, []);
  return <section id="issue-investigation" className="panel mt-8 p-5 sm:p-6">
    <div><p className="eyebrow">ISSUE INVESTIGATION</p><h2 className="mt-2 text-xl font-semibold">From issue to code evidence</h2>
      <p className="mt-2 text-sm text-muted">Explore an authorized issue in {repository.full_name}. Reports identify their provider and are not diagnoses.</p></div>
    <InvestigationHistory repository={repository} disabled={!!view.busy} onOpen={item => { setIssue(String(item.issue_number)); void controller.current?.openHistory(item.issue_number, item.job_id, item.issue_origin); }} />
    <form className="mt-5 flex flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); void controller.current?.loadIssue(issue); }}>
      <label className="text-sm font-medium">GitHub issue number<input value={issue} onChange={event => { setIssue(event.target.value); controller.current?.clear(); }} disabled={view.busy === "submit" || view.busy === "report"} inputMode="numeric" maxLength={10}
        className="mt-1 block w-48 rounded-lg border border-edge-strong px-3 py-2.5" placeholder="e.g. 1" /></label>
      <button className="button" disabled={view.busy === "issue"}>{view.busy === "issue" ? "Loading…" : "Load issue"}</button>
    </form>
    {view.error && <p role="alert" className="mt-4 rounded-lg bg-red-950/45 p-3 text-sm text-red-300">{view.error}</p>}
    {view.acceptedJobId && !view.job && <p className="mt-3 break-all text-xs text-muted">Investigation job ID: <code>{view.acceptedJobId}</code>. Load the issue and open this ID to check its status.</p>}
    {view.notice && <p role="status" className="mt-4 rounded-lg bg-amber-950/45 p-3 text-sm text-amber-200">{view.notice}</p>}
    {view.busy === "job" && <p role="status" className="mt-4 text-sm text-muted">Loading investigation status…</p>}
    {view.busy === "results" && <p role="status" className="mt-4 text-sm text-muted">Loading evidence and report…</p>}
    {!view.context && !view.busy && !view.error && <p className="mt-4 text-sm text-muted">Select an issue above or open an investigation from history.</p>}
    {view.context && <div className="mt-5 space-y-5"><IssueContextView issue={view.context} repository={repository} origin={view.job?.issue_origin} />
      <div className="flex flex-wrap items-center gap-3"><button className="button button-primary" disabled={!!view.busy || !!view.job} onClick={() => { void controller.current?.submit(); }}>
        {view.busy === "submit" ? "Submitting…" : "Investigate issue"}</button>
        <span className="text-xs text-muted">Starts a job only when you click.</span></div>
      <details className="rounded-lg border border-edge p-4"><summary className="cursor-pointer text-sm font-semibold">Open an existing investigation</summary>
        <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); void controller.current?.openJob(jobId.trim()); }}>
          <label className="text-sm">Investigation job ID<input value={jobId} onChange={event => setJobId(event.target.value)} maxLength={36}
            className="mt-1 block w-80 max-w-full rounded-lg border border-edge-strong px-3 py-2 font-mono text-xs" placeholder="Job UUID" /></label>
          <button className="button" disabled={!!view.busy}>Open job</button></form></details>
      {view.job && <><InvestigationStatus job={view.job} repository={repository} />
        {(view.job.status !== "completed" || view.job.operation === "mock_orchestration") && <button className="button" onClick={() => { void controller.current?.refreshJob(); }}>Refresh status</button>}
        {view.job.status === "completed" && view.job.operation === "code_evidence" && view.job.retrieval_status !== "snapshot_unavailable" && <>
          {view.evidence ? <EvidenceView evidence={view.evidence} repository={repository} /> : <button className="button" onClick={() => { void controller.current?.refreshResults(); }}>Refresh evidence and report</button>}
          {view.evidence && <CodeIntelligence key={`${view.job.job_id}:${view.job.snapshot_id}`} job={view.job} evidence={view.evidence} repository={repository} />}
          {view.report && <InvestigationReport envelope={view.report} repository={repository} />}
          {view.evidence && view.job.snapshot_id && view.job.commit_sha && <PatchProposals
            key={view.job.job_id} repositoryId={repository.id} jobId={view.job.job_id}
            snapshotId={view.job.snapshot_id} commit={view.job.commit_sha} />}
          {view.reportMissing && !view.job.issue_origin && <div className="rounded-xl border border-edge p-4"><p className="text-sm text-muted">No report has been generated for this investigation.</p>
            <button className="button mt-3" disabled={!!view.busy} onClick={() => { void controller.current?.generateReport(); }}>{view.busy === "report" ? "Submitting…" : "Generate report"}</button></div>}
        </>}
      </>}
    </div>}
  </section>;
}
