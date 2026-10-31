"use client";

import { useEffect, useRef, useState } from "react";
import type { Repository } from "@/lib/types";
import { InvestigationController, safeCitation, safeIssueUrl } from "@/lib/investigation-client";
import type { Citation, Evidence, InvestigationView, IssueContext, Job, ReportEnvelope } from "@/lib/investigation-client";

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

export function IssueContextView({ issue, repository }: { issue: IssueContext; repository: Repository }) {
  const truncated = Object.values(issue.truncation).some(Boolean);
  return <section aria-label="Issue context" className="rounded-xl border border-slate-200 bg-slate-50 p-4 sm:p-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-semibold text-emerald-700">ISSUE #{issue.number} · {issue.state.toUpperCase()}</p>
      <h3 className="mt-1 text-lg font-semibold text-slate-900">{issue.title}</h3></div>
      {safeIssueUrl(issue.url, repository, issue.number) && <a href={issue.url} target="_blank" rel="noopener noreferrer" className="text-sm font-semibold text-emerald-700 hover:underline">Open on GitHub ↗</a>}</div>
    {issue.labels.length > 0 && <p className="mt-3 text-xs text-slate-600">Labels: {issue.labels.join(", ")}</p>}
    <p className="mt-4 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{issue.body || "No issue description provided."}</p>
    {issue.comments.length > 0 && <details className="mt-4 text-sm text-slate-700"><summary className="cursor-pointer font-semibold">Comments ({issue.comments.length})</summary>
      {issue.comments.map(comment => <div key={comment.id} className="mt-3 rounded-lg bg-white p-3"><p className="whitespace-pre-wrap break-words">{comment.body}</p><p className="mt-2 text-xs text-slate-500">Updated {date(comment.updated_at)}{comment.truncated ? " · Truncated" : ""}</p></div>)}</details>}
    {truncated && <p role="status" className="mt-3 text-xs font-semibold text-amber-800">Issue context was truncated; some content is not shown.</p>}
    <p className="mt-4 text-xs text-slate-500">Created {date(issue.created_at)} · Updated {date(issue.updated_at)} · Retrieved {date(issue.retrieved_at)}</p>
  </section>;
}

export function InvestigationStatus({ job }: { job: Job }) {
  return <section aria-label="Investigation status" className="rounded-xl border border-slate-200 p-4 sm:p-5">
    <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">Investigation status</h3>
      <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">{label[job.status]}</span></div>
    <p className="mt-2 break-all font-mono text-xs text-slate-500">Job {job.job_id}</p>
    <p className="mt-2 text-sm text-slate-600">Worker attempts: {job.attempts} · Evidence: {job.evidence_count}</p>
    {job.operation === "mock_orchestration" && <p className="mt-2 text-sm text-slate-600">This mock orchestration does not retrieve source evidence or produce an investigation report.</p>}
    {job.snapshot_id && <p className="mt-2 break-all text-xs text-slate-500">Snapshot {job.snapshot_id}</p>}
    {job.commit_sha && <p className="mt-1 break-all font-mono text-xs text-slate-500">Commit {job.commit_sha}</p>}
    {job.snapshot_partial && <p className="mt-2 text-xs text-amber-800">The snapshot is partial; some source files were skipped.</p>}
    {job.retrieval_status === "snapshot_unavailable" && <p role="alert" className="mt-2 text-sm text-amber-800">The selected snapshot is no longer available. Evidence cannot be shown.</p>}
    {(job.status === "failed" || job.status === "cancelled") && <p role="alert" className="mt-2 text-sm text-red-700">The investigation did not complete. Check repository access and try again.</p>}
    {safeError(job.error_code) && <p className="mt-2 text-xs text-slate-600">{safeError(job.error_code)}</p>}
  </section>;
}

export function EvidenceView({ evidence, repository }: { evidence: Evidence; repository: Repository }) {
  return <section aria-label="Retrieved code evidence"><div className="mb-3 flex flex-wrap items-center justify-between gap-2"><div><h3 className="font-semibold">Retrieved code evidence</h3><p className="mt-1 text-xs text-slate-500">Candidates from the selected snapshot, not verified causes.</p></div><span className="text-xs text-slate-500">{evidence.items.length} results</span></div>
    {!evidence.items.length ? <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">No code evidence was retrieved. The issue may need more detail or a different snapshot.</p> :
      <div className="space-y-3">{evidence.items.map(item => <article key={item.chunk_id} className="overflow-hidden rounded-xl border border-slate-200">
        <div className="flex flex-wrap justify-between gap-3 p-4"><div className="min-w-0"><p className="text-xs font-semibold text-emerald-700">Rank {item.rank} · {item.method} · {item.query_id} (query rank {item.query_rank})</p>
          <p className="mt-1 break-all text-sm font-semibold">{item.path}</p><p className="mt-1 text-xs text-slate-500">{item.symbol ?? "Module"} · lines {item.start_line}–{item.end_line}</p>
          <p className="mt-1 break-all font-mono text-xs text-slate-500">{item.commit_sha}</p></div>
          {safeCitation(item, repository) && <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-sm font-semibold text-emerald-700 hover:underline">View source ↗</a>}</div>
        {item.snippet === null ? <p className="border-t border-slate-100 p-4 text-xs text-amber-800">Source excerpt withheld by the safety screen.</p> :
          <pre className="overflow-x-auto bg-slate-950 p-4 text-xs leading-6 text-slate-100"><code>{item.snippet}</code></pre>}
        {item.snippet_truncated && <p className="px-4 py-2 text-xs text-amber-800">Source excerpt truncated; the citation covers the full chunk.</p>}
      </article>)}</div>}
  </section>;
}

function Citations({ items, repository }: { items: Citation[]; repository: Repository }) {
  if (!items.length) return <p className="mt-1 text-xs text-slate-500">None cited.</p>;
  return <ul className="mt-2 space-y-1">{items.map(item => <li key={item.chunk_id} className="break-all text-sm">
    {safeCitation(item, repository) ? <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-emerald-700 hover:underline">{item.path} · lines {item.start_line}–{item.end_line} ↗</a> : <span>Citation unavailable</span>}
  </li>)}</ul>;
}

function TextList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return <div className="mt-4"><h5 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h5>
    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">{items.map((item, index) => <li key={index}>{item}</li>)}</ul></div>;
}

export function InvestigationReport({ envelope, repository }: { envelope: ReportEnvelope; repository: Repository }) {
  if (envelope.status !== "completed" || !envelope.report) return <section aria-label="Report status" className="rounded-xl border border-slate-200 p-4">
    <h3 className="font-semibold">Report {label[envelope.status]}</h3>
    {(envelope.status === "failed" || envelope.status === "cancelled") && <p role="alert" className="mt-2 text-sm text-red-700">The report could not be completed.</p>}
    {safeError(envelope.error_code) && <p className="mt-2 text-xs text-slate-600">{safeError(envelope.error_code)}</p>}
  </section>;
  const report = envelope.report;
  return <section aria-label="Investigation report" className="rounded-xl border border-amber-200 bg-amber-50/50 p-4 sm:p-5">
    <p className="text-xs font-bold tracking-wide text-amber-900">{report.provider === "mock"
      ? "MOCK REPORT — DEMONSTRATION ONLY" : "MODEL-GENERATED REPORT — HUMAN REVIEW REQUIRED"}</p>
    <h3 className="mt-2 text-lg font-semibold">Investigation report</h3>
    <p className="mt-1 text-xs text-slate-600">{report.provider} · {report.model} · {date(report.created_at)}</p>
    <p className="mt-3 text-sm text-slate-700">{report.disclaimer}</p>
    <h4 className="mt-5 text-sm font-semibold">Issue summary</h4><p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{report.summary}</p>
    {!report.hypotheses.length && <p className="mt-4 rounded-lg bg-white p-3 text-sm text-slate-600">No supported hypotheses were produced. More evidence is needed.</p>}
    <div className="mt-4 space-y-3">{report.hypotheses.map((h, index) => <article key={index} className="rounded-lg border border-amber-100 bg-white p-4">
      <h4 className="font-semibold">{index + 1}. {h.title}</h4><p className="mt-1 text-xs font-semibold text-amber-800">{h.support_status} · uncertainty: {h.uncertainty}</p>
      <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{h.explanation}</p>
      <TextList title="Observations" items={h.observations} /><TextList title="Missing or contradictory information" items={h.missing_or_contradictory} />
      <h5 className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Supporting evidence</h5><Citations items={h.evidence} repository={repository} />
      <h5 className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Contradictory evidence</h5><Citations items={h.contradictory_evidence} repository={repository} />
    </article>)}</div>
    <TextList title="Missing evidence" items={report.missing_evidence} /><TextList title="Next diagnostic steps" items={report.next_steps} />
    <TextList title="Warnings and limitations" items={report.warnings} />
    {(report.input_truncated || report.snapshot_partial) && <p className="mt-3 text-xs text-amber-800">The input or source snapshot was incomplete.</p>}
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
      <p className="mt-2 text-sm text-slate-500">Explore an authorized issue in {repository.full_name}. Reports identify their provider and are not diagnoses.</p></div>
    <form className="mt-5 flex flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); void controller.current?.loadIssue(issue); }}>
      <label className="text-sm font-medium">GitHub issue number<input value={issue} onChange={event => { setIssue(event.target.value); controller.current?.clear(); }} disabled={view.busy === "submit" || view.busy === "report"} inputMode="numeric" maxLength={10}
        className="mt-1 block w-48 rounded-lg border border-slate-300 px-3 py-2.5" placeholder="e.g. 1" /></label>
      <button className="button" disabled={view.busy === "issue"}>{view.busy === "issue" ? "Loading…" : "Load issue"}</button>
    </form>
    {view.error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{view.error}</p>}
    {view.acceptedJobId && !view.job && <p className="mt-3 break-all text-xs text-slate-600">Investigation job ID: <code>{view.acceptedJobId}</code>. Load the issue and open this ID to check its status.</p>}
    {view.notice && <p role="status" className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{view.notice}</p>}
    {view.busy === "job" && <p role="status" className="mt-4 text-sm text-slate-500">Loading investigation status…</p>}
    {view.context && <div className="mt-5 space-y-5"><IssueContextView issue={view.context} repository={repository} />
      <div className="flex flex-wrap items-center gap-3"><button className="button button-primary" disabled={!!view.busy || !!view.job} onClick={() => { void controller.current?.submit(); }}>
        {view.busy === "submit" ? "Submitting…" : "Investigate issue"}</button>
        <span className="text-xs text-slate-500">Starts a job only when you click.</span></div>
      <details className="rounded-lg border border-slate-200 p-4"><summary className="cursor-pointer text-sm font-semibold">Open an existing investigation</summary>
        <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); void controller.current?.openJob(jobId.trim()); }}>
          <label className="text-sm">Investigation job ID<input value={jobId} onChange={event => setJobId(event.target.value)} maxLength={36}
            className="mt-1 block w-80 max-w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-xs" placeholder="Job UUID" /></label>
          <button className="button" disabled={!!view.busy}>Open job</button></form></details>
      {view.job && <><InvestigationStatus job={view.job} />
        {(view.job.status !== "completed" || view.job.operation === "mock_orchestration") && <button className="button" onClick={() => { void controller.current?.refreshJob(); }}>Refresh status</button>}
        {(view.job.status === "failed" || view.job.status === "cancelled") && <button className="button" onClick={() => { void controller.current?.loadIssue(issue); }}>Prepare retry</button>}
        {view.job.status === "completed" && view.job.operation === "code_evidence" && view.job.retrieval_status !== "snapshot_unavailable" && <>
          {view.evidence ? <EvidenceView evidence={view.evidence} repository={repository} /> : <button className="button" onClick={() => { void controller.current?.refreshResults(); }}>Refresh evidence and report</button>}
          {view.report && <InvestigationReport envelope={view.report} repository={repository} />}
          {view.reportMissing && <div className="rounded-xl border border-slate-200 p-4"><p className="text-sm text-slate-600">No report exists for this investigation.</p>
            <button className="button mt-3" disabled={!!view.busy} onClick={() => { void controller.current?.generateReport(); }}>{view.busy === "report" ? "Submitting…" : "Generate report"}</button></div>}
        </>}
      </>}
    </div>}
  </section>;
}
