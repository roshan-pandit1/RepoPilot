"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type ReviewSummary = { id: string; status: string; number: number; title: string | null; base_sha: string | null; head_sha: string | null; head_repository_name?: string | null; head_repository_id?: string | null; coverage: string | null; stale?: boolean; error_code?: string | null; next_retry_at?: string | null };
type FileItem = { path: string; status: string; previous_path?: string | null; additions: number | null; deletions: number | null; patch?: string | null; coverage: string; reason?: string | null };
type Finding = { id: string; rule_id: string; category: string; severity: string; confidence: string; path: string; start_line: number; end_line: number; explanation: string; recommendation: string; evidence?: unknown; feedback_state?: string | null; feedback_reason?: string | null };
type Review = ReviewSummary & { repository_id: string; limitations: string[]; files: FileItem[]; findings: Finding[] };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const sha = /^[0-9a-f]{40}$/;
const item = (x: unknown): x is Record<string, unknown> => !!x && typeof x === "object" && !Array.isArray(x);
const text = (x: unknown, max: number): x is string => typeof x === "string" && x.length <= max;
export function parsePRSummary(value: unknown): ReviewSummary {
  if (!item(value) || !text(value.id, 36) || !uuid.test(value.id) || !text(value.status, 32) ||
      !Number.isSafeInteger(value.number) || (value.number as number) <= 0 || !(value.title === null || text(value.title, 1024)) ||
      !(value.base_sha === null || (text(value.base_sha, 40) && sha.test(value.base_sha))) ||
      !(value.head_sha === null || (text(value.head_sha, 40) && sha.test(value.head_sha))) ||
      !(value.head_repository_name == null || text(value.head_repository_name, 250)) ||
      !(value.head_repository_id == null || (text(value.head_repository_id, 20) && /^[1-9][0-9]*$/.test(value.head_repository_id))) ||
      !(value.coverage === null || ["complete", "partial", "unavailable"].includes(String(value.coverage))) ||
      !(value.stale === undefined || typeof value.stale === "boolean") ||
      !(value.error_code == null || text(value.error_code, 80)) ||
      !(value.next_retry_at == null || (text(value.next_retry_at, 80) && Number.isFinite(Date.parse(value.next_retry_at))))) throw new Error("invalid review");
  return value as ReviewSummary;
}
export function parsePRDetail(value: unknown, repositoryId: string): Review {
  const summary = parsePRSummary(value);
  if (!item(value) || String(value.repository_id) !== repositoryId || !Array.isArray(value.limitations) || value.limitations.length > 100 ||
      !value.limitations.every(v => text(v, 500)) || !Array.isArray(value.files) || value.files.length > 300 ||
      !value.files.every(f => item(f) && text(f.path, 512) && text(f.status, 32) && (f.additions === null || Number.isSafeInteger(f.additions)) &&
        (f.deletions === null || Number.isSafeInteger(f.deletions)) && text(f.coverage, 32) && (f.patch == null || text(f.patch, 262144)) &&
        (f.previous_path == null || text(f.previous_path, 512)) && (f.reason == null || text(f.reason, 500))) ||
      !Array.isArray(value.findings) || value.findings.length > 500 || !value.findings.every(f => item(f) && text(f.id, 36) && uuid.test(f.id) &&
        text(f.path, 512) && text(f.rule_id, 100) && text(f.category, 50) && text(f.severity, 32) && text(f.confidence, 32) &&
        Number.isSafeInteger(f.start_line) && Number.isSafeInteger(f.end_line) && (f.start_line as number) > 0 &&
        (f.end_line as number) >= (f.start_line as number) && text(f.explanation, 3000) && text(f.recommendation, 3000) &&
        (f.feedback_state == null || text(f.feedback_state, 32)) && (f.feedback_reason == null || text(f.feedback_reason, 500)))) throw new Error("invalid review");
  return { ...value, ...summary } as Review;
}
// A denial invalidates responses that began before access was revoked.
export function createReviewAccessGuard() {
  let epoch = 0;
  return { snapshot: () => epoch, valid: (snapshot: number) => snapshot === epoch, revoke: () => { epoch++; } };
}
function label(value: string) { return value.replaceAll("_", " "); }
function limitation(value: string) {
  return value === "typescript_analysis_unavailable"
    ? "TypeScript analysis was unavailable for this file; no conclusion can be drawn."
    : label(value);
}
function verifiedEvidence(finding: Finding, head: string | null) {
  const value = finding.evidence;
  if (!item(value) || !head || value.commit_sha !== head || value.line !== finding.start_line ||
      value.changed_line !== true || !text(value.file_sha256, 64) || !/^[a-f0-9]{64}$/.test(value.file_sha256) ||
      !text(value.git_blob_sha1, 40) || !sha.test(value.git_blob_sha1)) return null;
  return value as { commit_sha: string; file_sha256: string; git_blob_sha1: string };
}
export function PRReviewDetail({ review, onFeedback, busy }: { review: Review; onFeedback: (id: string, state: string, reason: string) => void; busy: boolean }) {
  const [category, setCategory] = useState("all"), [file, setFile] = useState("all"), [severity, setSeverity] = useState("all");
  const [reason, setReason] = useState<Record<string, string>>({});
  const categories = Array.from(new Set(review.findings.map(f => f.category))).sort();
  const severities = Array.from(new Set(review.findings.map(f => f.severity))).sort();
  const filtered = review.findings.filter(f => (category === "all" || f.category === category) && (file === "all" || f.path === file) && (severity === "all" || f.severity === severity));
  return <div className="mt-4 space-y-4">
    <div><h3 className="font-semibold">{review.title ?? "Pull request"} · #{review.number}</h3><p className="break-all text-xs text-muted">Base {review.base_sha ?? "pending"} · Head {review.head_sha ?? "pending"}</p>
      {review.head_repository_name && <p className="break-all text-xs text-muted">Head repository: {review.head_repository_name}</p>}
      <p className="text-sm">{review.stale ? "This review is stale because the pull request changed." : `Review: ${label(review.status)} · Coverage: ${review.coverage ? label(review.coverage) : "pending"}`}</p>
      {review.status === "queued" && review.error_code === "github_temporarily_unavailable" && <p role="status" className="text-sm">GitHub is temporarily unavailable. This pinned review will retry automatically, up to three attempts.</p>}
      {review.status === "queued" && ["github_rate_limited", "github_secondary_rate_limited"].includes(review.error_code ?? "") && review.next_retry_at && <p role="status" className="text-sm">GitHub rate limit reached. This pinned review is eligible to retry after {review.next_retry_at}.</p>}
      {review.status === "failed" && review.error_code && <p role="alert" className="text-sm">This review could not be completed. Check GitHub access and submit a new review when ready.</p>}
      <p className="text-sm text-muted">Read-only deterministic review. No repository code or proposed fix was executed.</p></div>
    {review.limitations.length > 0 && <div role="status"><p className="font-semibold">Review limitations</p><ul className="list-disc pl-5 text-sm">{review.limitations.map((v, i) => <li key={`${i}:${v}`}>{limitation(v)}</li>)}</ul></div>}
    {review.status === "completed" && <p className="text-sm text-muted">Recorded files checked by enabled rules: {review.files.filter(f => f.coverage === "complete").length} · Recorded files not fully checked: {review.files.filter(f => f.coverage !== "complete").length}</p>}
    <div><h4 className="font-semibold">Changed files</h4>{review.files.length === 0 ? <p className="text-sm text-muted">No file details available.</p> : <ul className="space-y-2">{review.files.map((f, i) => <li key={`${i}:${f.path}`} className="rounded border border-edge p-3"><p className="break-all text-sm">{f.path} · {label(f.status)} · +{f.additions ?? "unknown"} / −{f.deletions ?? "unknown"}</p>{f.previous_path && <p className="text-xs text-muted">Previous path: {f.previous_path}</p>}<p className="text-xs text-muted">Coverage: {label(f.coverage)}{f.reason ? ` · ${limitation(f.reason)}` : ""}</p>{f.patch && <details><summary className="cursor-pointer text-sm">View diff</summary><pre className="overflow-x-auto whitespace-pre text-xs"><code>{f.patch}</code></pre></details>}</li>)}</ul>}</div>
    <div><h4 className="font-semibold">Findings ({review.findings.length})</h4><div className="flex flex-wrap gap-3 text-sm">
      <label>Severity <select aria-label="Filter findings by severity" value={severity} onChange={e => setSeverity(e.target.value)}><option value="all">All</option>{severities.map(v => <option key={v}>{v}</option>)}</select></label>
      <label>Category <select aria-label="Filter findings by category" value={category} onChange={e => setCategory(e.target.value)}><option value="all">All</option>{categories.map(v => <option key={v}>{v}</option>)}</select></label>
      <label>File <select aria-label="Filter findings by file" value={file} onChange={e => setFile(e.target.value)}><option value="all">All</option>{Array.from(new Set(review.findings.map(f => f.path))).map(v => <option key={v}>{v}</option>)}</select></label>
    </div>{filtered.length === 0 ? <p className="mt-2 text-sm text-muted">{review.findings.length ? "No findings match these filters." : (review.status === "queued" || review.status === "running" ? "Review in progress; findings are not available yet." : review.status === "failed" ? "Review failed; findings are not available." : "No findings were emitted by the supported rules. This is not a complete security assessment.")}</p> : <ul className="mt-3 space-y-3">{filtered.map(f => <li key={f.id} className="rounded border border-edge p-3"><p className="break-all text-sm font-semibold">{f.severity} · {label(f.category)} · {f.path}:{f.start_line}–{f.end_line}</p><p className="text-xs text-muted">Rule {f.rule_id} · Confidence {f.confidence}</p>{verifiedEvidence(f, review.head_sha) ? <p className="break-all text-xs text-muted">Changed-line evidence · Commit {review.head_sha} · Source SHA-256 {verifiedEvidence(f, review.head_sha)?.file_sha256}</p> : <p className="text-xs text-muted">Source identity unavailable.</p>}<p className="mt-2 text-sm">{f.explanation}</p><p className="mt-1 text-sm">{f.recommendation}</p><p className="text-xs text-muted">Feedback: {f.feedback_state ? label(f.feedback_state) : "Not recorded"}</p><label className="block text-sm">Feedback reason <input className="block w-full" maxLength={500} value={reason[f.id] ?? ""} onChange={e => setReason(v => ({ ...v, [f.id]: e.target.value }))} /></label><div className="mt-2 flex flex-wrap gap-2">{["useful", "false_positive", "acknowledged"].map(state => <button key={state} className="button" disabled={busy || review.stale} onClick={() => onFeedback(f.id, state, reason[f.id] ?? "")}>{label(state)}</button>)}</div></li>)}</ul>}</div>
  </div>;
}
export function PRReviews({ repositoryId, repositoryName }: { repositoryId: string; repositoryName: string }) {
  const [url, setUrl] = useState(""), [reviews, setReviews] = useState<ReviewSummary[] | null>(null), [selected, setSelected] = useState("");
  const [review, setReview] = useState<Review | null>(null), [listError, setListError] = useState(""), [detailError, setDetailError] = useState(""), [actionError, setActionError] = useState(""), [busy, setBusy] = useState(false), [revision, setRevision] = useState(0);
  const root = `/api/repositories/${repositoryId}/pr-reviews`;
  const access = useRef(createReviewAccessGuard());
  const deny = useCallback(() => { access.current.revoke(); setReviews([]); setReview(null); setSelected("");
    setListError("Reviews could not be loaded. Check access and try again."); }, []);
  const refresh = useCallback(() => setRevision(v => v + 1), []);
  useEffect(() => { const c = new AbortController();
    const load = async () => { const epoch = access.current.snapshot(); try { const response = await fetch(root, { cache: "no-store", signal: c.signal });
      if (!access.current.valid(epoch) || c.signal.aborted) return;
      if (response.status === 401 || response.status === 403 || response.status === 404) { deny(); return; } if (!response.ok) throw new Error();
      const value: unknown = await response.json(); if (!item(value) || !Array.isArray(value.items) || value.items.length > 100) throw new Error();
      const data = value.items.map(parsePRSummary); if (!c.signal.aborted && access.current.valid(epoch)) { setReviews(data); setListError(""); }
    } catch { if (!c.signal.aborted && access.current.valid(epoch)) setListError("Reviews could not be loaded. Check access and try again."); } };
    void load(); const timer = setInterval(() => { void load(); }, 10000); return () => { c.abort(); clearInterval(timer); };
  }, [root, revision, deny]);
  useEffect(() => { if (!selected) return; const c = new AbortController();
    const load = async () => { const epoch = access.current.snapshot(); try { const response = await fetch(`${root}/${selected}`, { cache: "no-store", signal: c.signal });
      if (!access.current.valid(epoch) || c.signal.aborted) return;
      if (response.status === 401 || response.status === 403 || response.status === 404) { deny(); return; } if (!response.ok) throw new Error();
      const data = parsePRDetail(await response.json(), repositoryId); if (data.id !== selected) throw new Error();
      if (!c.signal.aborted && access.current.valid(epoch)) { setReview(data); setDetailError(""); }
    } catch { if (!c.signal.aborted && access.current.valid(epoch)) { setReview(null); setDetailError("Review details could not be verified. Check access and try again."); } } };
    void load(); const timer = setInterval(() => { void load(); }, 10000); return () => { c.abort(); clearInterval(timer); };
  }, [root, repositoryId, selected, revision, deny]);
  async function submit(path: string, body: object) { const epoch = access.current.snapshot(); setBusy(true); setActionError(""); try {
    const response = await fetch(`${root}${path}`, { method: "POST", cache: "no-store", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
    if (!access.current.valid(epoch)) return; if (response.status === 401 || response.status === 403 || response.status === 404) { deny(); return; }
    if (!response.ok) throw new Error(); const value: unknown = await response.json();
    if (!access.current.valid(epoch)) return;
    if (!path) { if (!item(value) || !text(value.id, 36) || !uuid.test(value.id)) throw new Error(); setSelected(value.id); setUrl(""); }
    refresh();
  } catch { if (access.current.valid(epoch)) setActionError("The request could not be completed. Check access and try again."); } finally { setBusy(false); } }
  return <section id="pull-request-reviews" className="panel inbox-panel reveal-panel mt-6" aria-label="Pull request reviews"><div className="p-4 sm:p-6">
    <h2 className="font-semibold">Pull request reviews</h2><p className="text-sm text-muted">Read-only review for {repositoryName}. Findings are suggestions, not proof of a defect.</p>
    <form className="mt-3 flex flex-wrap gap-2" onSubmit={e => { e.preventDefault(); void submit("", { url }); }}><label className="sr-only" htmlFor="pr-review-url">GitHub pull request URL</label><input id="pr-review-url" className="min-w-0 flex-1" type="url" required maxLength={1024} value={url} onChange={e => setUrl(e.target.value)} placeholder="https://github.com/owner/repository/pull/123" /><button className="button" disabled={busy}>Review pull request</button></form>
    {[listError, detailError, actionError].filter(Boolean).map((message, i) => <p key={i} role="alert" className="mt-3 text-sm text-red-300">{message}</p>)}
    {(listError || detailError || actionError) && <button className="button mt-2" onClick={refresh}>Retry</button>}
    {reviews === null ? <p role="status" className="mt-3 text-sm">Loading reviews…</p> : reviews.length === 0 ? <p className="mt-3 text-sm text-muted">No reviews yet.</p> : <ul className="mt-3 space-y-2">{reviews.map(r => <li key={r.id}><button className="button" disabled={busy} onClick={() => { setReview(null); setDetailError(""); setSelected(r.id); }}>{r.title ?? "Pull request"} · #{r.number} · {label(r.status)}</button></li>)}</ul>}
    {selected && !review && !detailError && <p role="status" className="mt-3 text-sm">Loading review…</p>}
    {review && <PRReviewDetail review={review} busy={busy} onFeedback={(id, state, reason) => { void submit(`/${review.id}/findings/${id}/feedback`, { state, ...(reason ? { reason } : {}) }); }} />}
  </div></section>;
}
