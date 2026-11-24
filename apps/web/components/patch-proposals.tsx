"use client";

import { useEffect, useRef, useState } from "react";

type Summary = { id: string; status: string; snapshot_id: string; commit_sha: string; review_state: string; error_code: string | null; dispatch_status: string | null };
type TestPhase = { status: "passed" | "failed"; exit_code: number; duration_ms: number; diagnostic: string };
type TestReport = { status: string; sandbox_used: boolean; test_executed?: boolean; tests_run?: string[];
  outcome?: string; baseline?: TestPhase | null; patched?: TestPhase | null; reason?: string | null };
type Detail = Summary & { diff?: string; rationale?: string; provider?: string; model?: string;
  evidence?: { id: string; path: string; start_line: number; end_line: number }[];
  changed_files?: { path: string }[]; static_result?: { status: string }; test_result?: TestReport;
  patch_sha256?: string | null; export_available?: boolean; source_stale?: boolean;
  export_reason?: "source_identity_unverified" | "patch_digest_missing" | "source_stale" | "rejected" | "proposal_not_validated" | null;
  source_coverage?: { evidence_id: string; path: string; start_line: number; end_line: number;
    classification: "COMPLETE_FILE" | "BOUNDED_EXCERPT" | "UNKNOWN_COVERAGE" }[] };
type Listing = { available: boolean; reason: string | null; items: Summary[] };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const statuses = new Set(["queued", "generating", "static_validated", "validation_pending", "validating", "tests_passed", "tests_failed", "stale", "failed"]);
const reviews = new Set(["unreviewed", "approved_for_review", "rejected"]);
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const phase = (value: unknown): value is TestPhase => object(value) &&
  ((value.status === "passed" && value.exit_code === 0 && value.diagnostic === "pass_marker") ||
   (value.status === "failed" && value.exit_code === 1 && value.diagnostic === "assertion_failed")) &&
  Number.isSafeInteger(value.duration_ms) && (value.duration_ms as number) >= 0 && (value.duration_ms as number) <= 10000;

function completed(report: unknown, status: string): boolean {
  if (!object(report) || report.status !== "COMPLETED" || report.sandbox_used !== true || report.test_executed !== true ||
      !Array.isArray(report.tests_run) || report.tests_run.length !== 1 || typeof report.tests_run[0] !== "string" ||
      !phase(report.baseline) || !phase(report.patched)) return false;
  const expected = report.baseline.status === "failed" ?
    (report.patched.status === "passed" ? "BASELINE_FAILED_PATCH_PASSED" : "BOTH_FAILED") :
    (report.patched.status === "passed" ? "BOTH_PASSED" : "BASELINE_PASSED_PATCH_FAILED");
  return report.outcome === expected && status === (report.patched.status === "passed" ? "tests_passed" : "tests_failed");
}

function summary(value: unknown, snapshot: string, commit: string): Summary {
  if (!object(value) || typeof value.id !== "string" || !uuid.test(value.id) ||
      typeof value.status !== "string" || !statuses.has(value.status) || value.snapshot_id !== snapshot ||
      value.commit_sha !== commit || typeof value.review_state !== "string" || !reviews.has(value.review_state) ||
      !(value.dispatch_status === null || ["pending", "processed", "failed"].includes(String(value.dispatch_status))) ||
      !(value.error_code === null || (typeof value.error_code === "string" && value.error_code.length <= 80))) throw new Error();
  return value as Summary;
}

function listing(value: unknown, snapshot: string, commit: string): Listing {
  if (!object(value) || typeof value.available !== "boolean" ||
      !(value.reason === null || (typeof value.reason === "string" && value.reason.length <= 200)) ||
      !Array.isArray(value.items) || value.items.length > 50) throw new Error();
  return { available: value.available, reason: value.reason, items: value.items.map(item => summary(item, snapshot, commit)) };
}

function detail(value: unknown, snapshot: string, commit: string): Detail {
  const item = summary(value, snapshot, commit);
  if (!object(value) || value.diff === undefined) return item;
  if (typeof value.diff !== "string" || value.diff.length > 262144 || typeof value.rationale !== "string" || value.rationale.length > 2000 ||
      typeof value.provider !== "string" || value.provider.length > 40 || typeof value.model !== "string" || value.model.length > 100 ||
      !Array.isArray(value.changed_files) || value.changed_files.length > 5 ||
      !value.changed_files.every(file => object(file) && typeof file.path === "string" && file.path.length <= 512) ||
      !Array.isArray(value.evidence) || value.evidence.length > 30 ||
      !value.evidence.every(e => object(e) && typeof e.id === "string" && uuid.test(e.id) && typeof e.path === "string" &&
        e.path.length <= 512 && Number.isSafeInteger(e.start_line) && Number.isSafeInteger(e.end_line) &&
        (e.start_line as number) > 0 && (e.end_line as number) >= (e.start_line as number)) ||
      !object(value.static_result) || typeof value.static_result.status !== "string" ||
      !object(value.test_result) || typeof value.test_result.status !== "string" || typeof value.test_result.sandbox_used !== "boolean") throw new Error();
  if (!(value.patch_sha256 === undefined || value.patch_sha256 === null ||
        (typeof value.patch_sha256 === "string" && /^[a-f0-9]{64}$/.test(value.patch_sha256))) ||
      !(value.export_available === undefined || typeof value.export_available === "boolean") ||
      !(value.source_stale === undefined || typeof value.source_stale === "boolean") ||
      !(value.export_reason === undefined || value.export_reason === null ||
        ["source_identity_unverified", "patch_digest_missing", "source_stale", "rejected", "proposal_not_validated"].includes(String(value.export_reason))) ||
      (value.export_available === true && (value.source_stale === true || typeof value.patch_sha256 !== "string" || value.static_result.status !== "passed" ||
        !["static_validated", "tests_passed", "tests_failed"].includes(item.status) || item.review_state === "rejected")) ||
      !(value.source_coverage === undefined || (Array.isArray(value.source_coverage) && value.source_coverage.length <= 30 &&
        new Set(value.source_coverage.map(entry => object(entry) ? entry.evidence_id : null)).size === value.source_coverage.length &&
        value.source_coverage.every(entry => object(entry) && typeof entry.evidence_id === "string" && uuid.test(entry.evidence_id) &&
          typeof entry.path === "string" && entry.path.length <= 512 && Number.isSafeInteger(entry.start_line) &&
          Number.isSafeInteger(entry.end_line) && ["COMPLETE_FILE", "BOUNDED_EXCERPT", "UNKNOWN_COVERAGE"].includes(String(entry.classification)) &&
          (value.evidence as unknown[]).some(ref => object(ref) && ref.id === entry.evidence_id && ref.path === entry.path &&
            ref.start_line === entry.start_line && ref.end_line === entry.end_line))))) throw new Error();
  const report = value.test_result;
  if (!(report.reason === undefined || report.reason === null || (typeof report.reason === "string" && report.reason.length <= 80))) throw new Error();
  if (report.status === "COMPLETED" && !completed(report, item.status)) throw new Error();
  if (["tests_passed", "tests_failed"].includes(item.status) && report.status !== "COMPLETED") throw new Error();
  return value as Detail;
}

export function ProposalView({ proposal }: { proposal: Detail }) {
  const complete = completed(proposal.test_result, proposal.status);
  const unsafeStatus = ["tests_passed", "tests_failed"].includes(proposal.status) && !complete;
  return <div className="mt-4 space-y-3 rounded-lg border border-edge p-4">
    <p className="text-sm font-semibold">{unsafeStatus ? "Unverified validation result" : proposal.status === "static_validated" ? "Statically validated proposal" : `Proposal: ${proposal.status}`}</p>
    <p className="text-xs text-muted">Review: {proposal.review_state.replaceAll("_", " ")} · Snapshot commit {proposal.commit_sha}</p>
    <p className="text-xs text-muted">Source snapshot: {proposal.snapshot_id}</p>
    {proposal.patch_sha256 && <p className="break-all text-xs text-muted">Candidate patch SHA-256: {proposal.patch_sha256}</p>}
    {proposal.status === "failed" && <p role="alert" className="text-sm text-red-300">{proposal.error_code === "reviewer_cancelled"
      ? "The proposal was cancelled." : proposal.error_code === "local_model_insufficient_evidence"
        ? "The provider needs more evidence before proposing a change. No patch was created."
        : proposal.error_code === "provider_timeout"
          ? "Patch generation timed out. No patch was created. Try again."
          : ["provider_unavailable", "local_provider_unreachable", "local_provider_runtime_unavailable"].includes(proposal.error_code || "")
            ? "The patch provider is unavailable. No patch was created. Try again when it is ready."
            : "Patch generation failed. No partial patch was accepted."}</p>}
    {proposal.dispatch_status === "failed" && <p role="alert" className="text-sm text-red-300">Job dispatch exhausted its retry limit; no result is available.</p>}
    {(proposal.status === "stale" || proposal.source_stale) && <p role="alert" className="text-sm text-red-300">The issue or source changed; this proposal is stale. Generate a new proposal from the current snapshot.</p>}
    {proposal.diff && <><p className="text-sm text-muted">{proposal.provider} · {proposal.model}</p>
      <p className="text-sm">{proposal.rationale}</p>
      <p className="text-xs text-muted">Changed files: {proposal.changed_files?.map(file => file.path).join(", ")}</p>
      <ul aria-label="Patch evidence" className="space-y-1 text-xs text-muted">{proposal.evidence?.map(ref => {
        const coverage = proposal.source_coverage?.find(entry => entry.evidence_id === ref.id);
        return <li key={ref.id}>
          Evidence <span className="break-all">{ref.id}</span>: <a className="text-ice underline" href={`#proposal-diff-${proposal.id}`}>{ref.path}:{ref.start_line}–{ref.end_line} · View candidate diff</a>
          {coverage && <> · {coverage.classification === "COMPLETE_FILE" ? "Complete file verified" : coverage.classification === "BOUNDED_EXCERPT" ? "Bounded excerpt" : "Source coverage unknown"}</>}
        </li>;
      })}</ul>
      <pre id={`proposal-diff-${proposal.id}`} tabIndex={0} aria-label="Candidate patch diff" className="max-h-96 overflow-auto whitespace-pre bg-evidence p-4 font-mono text-xs"><code>{proposal.diff}</code></pre>
      <p className="text-sm text-muted">Static checks: {proposal.static_result?.status}. Test validation: {proposal.test_result?.status}.</p>
      {proposal.test_result?.status === "VALIDATION_UNAVAILABLE" && <p className="text-sm text-amber-200">Automated tests were not run. This is a proposed patch, not a verified fix.</p>}
      {proposal.test_result?.status === "EXECUTION_BLOCKED" && <p className="text-sm text-amber-200">{proposal.test_result.reason === "fixture_not_allowlisted"
        ? "Tests were blocked: only pinned synthetic fixtures are allowed." : "Tests were blocked by a sandbox policy check; no fixture test ran."}</p>}
      {proposal.test_result && ["INFRASTRUCTURE_FAILURE", "TIMEOUT", "RESOURCE_LIMIT", "CANCELLED", "CLEANUP_FAILURE"].includes(proposal.test_result.status) &&
        <p className="text-sm text-amber-200">Validation did not complete ({proposal.test_result.status.replaceAll("_", " ")}). {proposal.test_result.reason || "No successful result was recorded."}</p>}
      {complete && proposal.test_result?.baseline && proposal.test_result.patched &&
        <div className="space-y-1 text-sm text-muted">
          <p>Sandbox used: yes. Test: {proposal.test_result.tests_run?.join(", ")}.</p>
          <p>Baseline: {proposal.test_result.baseline.status} (exit {proposal.test_result.baseline.exit_code}, {proposal.test_result.baseline.duration_ms} ms).</p>
          <p>Patched: {proposal.test_result.patched.status} (exit {proposal.test_result.patched.exit_code}, {proposal.test_result.patched.duration_ms} ms).</p>
          <p>Comparison: {proposal.test_result.outcome?.replaceAll("_", " ")}.</p>
          <p>Synthetic fixture only; this result does not prove a real issue was fixed.</p>
          {proposal.test_result.outcome === "BOTH_PASSED" && <p>Both versions passed, so the test does not establish a fix.</p>}
        </div>}
      <p className="text-xs text-muted">Review approval is for further consideration. Apply and test the candidate manually; this decision does not apply this patch or publish a pull request.</p></>}
  </div>;
}

export function ProposalAvailability({ state, reason }: { state: "loading" | "error" | "available" | "unavailable"; reason?: string | null }) {
  if (state === "loading") return <p role="status" className="mt-3 text-sm text-muted">Loading patch availability…</p>;
  if (state === "error") return <p role="alert" className="mt-3 text-sm text-red-300">{reason || "Patch proposals are unavailable."}</p>;
  return <p className="mt-3 text-sm text-muted">{state === "available" ? "Patch generation is available." : reason || "Patch generation is unavailable."}</p>;
}

export function ProposalChoices({ items, onSelect, disabled = false }: { items: Summary[]; onSelect: (id: string) => void; disabled?: boolean }) {
  if (!items.length) return <p className="mt-3 text-sm text-muted">No proposals yet.</p>;
  return <ul className="mt-3 space-y-2">{items.map(item => <li key={item.id}>
    <button className="text-sm text-ice hover:underline" disabled={disabled} onClick={() => onSelect(item.id)}>{item.status} · {item.id}</button>
  </li>)}</ul>;
}

export function PatchProposals({ repositoryId, jobId, snapshotId, commit }: {
  repositoryId: string; jobId: string; snapshotId: string; commit: string;
}) {
  const [data, setData] = useState<Listing | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [proposal, setProposal] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [listError, setListError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportMessage, setExportMessage] = useState("");
  const [exportError, setExportError] = useState("");
  const exportRequest = useRef<AbortController | null>(null);
  const requestId = useRef<string | null>(null);
  const base = `/api/investigations/${repositoryId}/jobs/${jobId}/patch-proposals`;

  useEffect(() => () => { exportRequest.current?.abort(); }, [base]);

  useEffect(() => {
    const controller = new AbortController();
    void fetch(base, { cache: "no-store", signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error();
      const parsed = listing(await response.json(), snapshotId, commit);
      if (!controller.signal.aborted) { setData(parsed); setListError(""); }
    }).catch(() => { if (!controller.signal.aborted) { setData(null); setProposal(null); setListError("Patch proposals are unavailable."); } });
    return () => controller.abort();
  }, [base, snapshotId, commit, revision]);

  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    void fetch(`${base}/${selected}`, { cache: "no-store", signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error();
      const parsed = detail(await response.json(), snapshotId, commit);
      if (parsed.id !== selected) throw new Error();
      if (!controller.signal.aborted) { setProposal(parsed); setDetailError(""); }
    }).catch(() => { if (!controller.signal.aborted) { setProposal(null); setDetailError("Proposal source or access could not be verified."); } });
    return () => controller.abort();
  }, [base, selected, snapshotId, commit, revision]);

  async function action(path: string, value?: unknown) {
    setBusy(true); setError("");
    try {
      const response = await fetch(`${base}${path}`, { method: "POST", cache: "no-store",
        ...(value === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(value) }) });
      if (!response.ok) throw new Error();
      const result = await response.json() as unknown;
      if (!path) { setSelected(summary(result, snapshotId, commit).id); requestId.current = null; }
      setProposal(null); setExportMessage(""); setExportError("");
      setRevision(current => current + 1);
    } catch { setData(null); setProposal(null); setError("The request could not be completed. Check access and try again."); }
    finally { setBusy(false); }
  }

  async function exportPatch(kind: "copy" | "download") {
    if (!proposal?.export_available || !proposal.patch_sha256 || exportBusy) return;
    const selectedProposal = proposal;
    const expectedHash = selectedProposal.patch_sha256;
    const controller = new AbortController();
    exportRequest.current?.abort(); exportRequest.current = controller;
    setExportBusy(true); setExportMessage(""); setExportError("");
    try {
      const verified = (async () => {
        const response = await fetch(`${base}/${selectedProposal.id}/export?sha256=${expectedHash}`, { cache: "no-store", signal: controller.signal });
        if (!response.ok || response.headers.get("x-patch-sha256") !== expectedHash ||
            response.headers.get("x-source-commit") !== selectedProposal.commit_sha ||
            response.headers.get("x-source-snapshot") !== selectedProposal.snapshot_id) throw new Error();
        const bytes = await response.arrayBuffer();
        if (!bytes.byteLength || bytes.byteLength > 262144) throw new Error();
        const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))).map(n => n.toString(16).padStart(2, "0")).join("");
        if (digest !== expectedHash || controller.signal.aborted) throw new Error();
        return { bytes, text: new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(bytes) };
      })();
      // Safari requires clipboard.write to begin within the user gesture; its payload may resolve later.
      if (kind === "copy" && typeof ClipboardItem !== "undefined" && navigator.clipboard?.write) {
        void verified.catch(() => {});
        const item = new ClipboardItem({ "text/plain": verified.then(value => new Blob([value.text], { type: "text/plain" })) });
        await navigator.clipboard.write([item]);
      } else if (kind === "copy") {
        const value = await verified;
        await navigator.clipboard.writeText(value.text);
      } else {
        const { bytes } = await verified;
        const url = URL.createObjectURL(new Blob([bytes], { type: "text/x-diff;charset=utf-8" }));
        try {
          const link = document.createElement("a"); link.href = url; link.download = `repopilot-${selectedProposal.id}.patch`; link.click();
        } finally { setTimeout(() => URL.revokeObjectURL(url), 1000); }
      }
      if (!controller.signal.aborted) setExportMessage(kind === "copy" ? "Candidate patch copied." : "Candidate patch download started.");
    } catch {
      if (!controller.signal.aborted) setExportError("Patch export could not be verified. Refresh the proposal and try again.");
    } finally {
      if (exportRequest.current === controller) { exportRequest.current = null; setExportBusy(false); }
    }
  }

  const visibleError = error || listError || detailError;

  return <section aria-label="Proposed fixes" className="rounded-xl border border-edge p-4">
    <h3 className="font-semibold">Proposed fixes</h3>
    <p className="mt-1 text-sm text-muted">AI suggests a candidate; static checks and human review come before manual application and external testing.</p>
    <p className="mt-1 text-xs text-muted">Investigation: {jobId} · Repository ID: {repositoryId}. Proposals never change the repository automatically.</p>
    <ProposalAvailability state={visibleError ? "error" : !data ? "loading" : data.available ? "available" : "unavailable"} reason={visibleError || data?.reason} />
    {visibleError && <button className="button mt-3" disabled={busy || exportBusy} onClick={() => { setError(""); setDetailError(""); setRevision(current => current + 1); }}>Retry</button>}
    {data && <>
      <button className="button mt-3" disabled={!data.available || busy || exportBusy} onClick={() => {
        requestId.current ??= crypto.randomUUID();
        void action("", { request_id: requestId.current });
      }}>Generate proposed fix</button>
      <ProposalChoices items={data.items} disabled={busy || exportBusy} onSelect={id => { exportRequest.current?.abort(); setProposal(null); setExportMessage(""); setExportError(""); setDetailError(""); setSelected(id); }} />
      {proposal && <><ProposalView proposal={proposal} />
        {proposal.export_available && proposal.patch_sha256 && <div className="mt-3 flex flex-wrap gap-2" aria-label="Candidate patch export">
          <button className="button" disabled={busy || exportBusy} onClick={() => { void exportPatch("copy"); }}>Copy candidate patch</button>
          <button className="button" disabled={busy || exportBusy} onClick={() => { void exportPatch("download"); }}>Download candidate .patch</button>
        </div>}
        {proposal.diff && proposal.export_reason === "source_identity_unverified" &&
          <p className="mt-2 text-sm text-muted">Export requires verified complete source identity. Reindex the repository and generate a proposal from the new snapshot.</p>}
        {proposal.diff && proposal.export_reason === "patch_digest_missing" &&
          <p className="mt-2 text-sm text-muted">Recheck static validation to prepare this candidate for export.</p>}
        {proposal.diff && proposal.export_reason === "patch_digest_missing" && proposal.review_state === "approved_for_review" && ["static_validated", "tests_passed", "tests_failed"].includes(proposal.status) && !proposal.source_stale &&
          <button className="button mt-3" disabled={busy || exportBusy} onClick={() => { void action(`/${proposal.id}/static-validation`); }}>Recheck static validation</button>}
        {exportMessage && <p role="status" className="mt-2 text-sm text-muted">{exportMessage}</p>}
        {exportError && <p role="alert" className="mt-2 text-sm text-red-300">{exportError}</p>}
        {["queued", "generating", "validation_pending", "validating"].includes(proposal.status) && proposal.review_state === "unreviewed" &&
          <button className="button mt-3" disabled={busy || exportBusy} onClick={() => { void action(`/${proposal.id}/review`, { decision: "rejected" }); }}>Cancel proposal</button>}
        {["static_validated", "tests_passed", "tests_failed"].includes(proposal.status) && proposal.review_state === "unreviewed" && !proposal.source_stale && <div className="mt-3 flex flex-wrap gap-2">
          {(proposal.status === "static_validated" || proposal.export_reason === "patch_digest_missing") && <button className="button" disabled={busy || exportBusy} onClick={() => { void action(`/${proposal.id}/static-validation`); }}>Recheck static validation</button>}
          <button className="button" disabled={busy || exportBusy} onClick={() => { void action(`/${proposal.id}/test-validation`); }}>Request isolated tests</button>
          <button className="button" disabled={busy || exportBusy} onClick={() => { void action(`/${proposal.id}/review`, { decision: "approved_for_review" }); }}>Approve for review</button>
          <button className="button" disabled={busy || exportBusy} onClick={() => { void action(`/${proposal.id}/review`, { decision: "rejected" }); }}>Reject proposal</button>
        </div>}
        <button className="button mt-3" disabled={busy || exportBusy} onClick={() => { setProposal(null); setExportMessage(""); setExportError(""); setRevision(current => current + 1); }}>Refresh proposal</button>
      </>}
    </>}
  </section>;
}
