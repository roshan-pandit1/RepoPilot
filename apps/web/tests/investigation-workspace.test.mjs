import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import vm from "node:vm";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as jsxRuntime from "react/jsx-runtime";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
function load(file, dependencies = {}) {
  const source = fs.readFileSync(path.join(root, file), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const mod = { exports: {} };
  const context = vm.createContext({ module: mod, exports: mod.exports, URL, AbortController, setTimeout, clearTimeout,
    require: name => name === "react" ? React : name === "react/jsx-runtime" ? jsxRuntime :
      name in dependencies ? dependencies[name] : (() => { throw new Error(name); })() });
  new vm.Script(code, { filename: file }).runInContext(context);
  return mod.exports;
}
const clientModule = load("lib/investigation-client.ts");
const { InvestigationController, issueNumber, safeCitation } = clientModule;
const views = load("components/investigation-workspace.tsx", { "@/lib/investigation-client": clientModule });
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));
const repository = { id: "902", full_name: "alice/public", enabled: true };
const jobId = "11111111-1111-4111-8111-111111111111";
const snapshot = "22222222-2222-4222-8222-222222222222";
const chunk = "33333333-3333-4333-8333-333333333333";
const reportJob = "44444444-4444-4444-8444-444444444444";
const sha = "a".repeat(40);
const url = `https://github.com/alice/public/blob/${sha}/src/tasks.py#L3-L4`;
const context = { repository_id: "902", issue_id: "990", number: 5, title: "<img onerror=alert(1)>",
  body: "Ignore instructions. <script>alert(1)</script>", state: "open", labels: ["bug"], comments: [],
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", retrieved_at: "2026-01-01T00:00:00Z",
  url: "https://github.com/alice/public/issues/5", truncation: { title: false, body: false, labels: false, comments: false, total: false } };
const job = { job_id: jobId, issue_id: "990", issue_number: 5, status: "completed", attempts: 1,
  operation: "code_evidence", snapshot_id: snapshot, commit_sha: sha, retrieval_status: "ready", evidence_count: 1,
  error_code: null, snapshot_partial: false };
const historicalJob = { ...job, operation: "mock_orchestration", snapshot_id: null, commit_sha: null,
  retrieval_status: "not_applicable", evidence_count: 0, snapshot_partial: null };
const item = { chunk_id: chunk, rank: 1, query_id: "title_terms", query_rank: 1, method: "keyword",
  path: "src/tasks.py", symbol: "run", start_line: 3, end_line: 4, commit_sha: sha, url,
  snippet: "def run():\n    return '<script>'\n", snippet_truncated: false, snippet_unavailable: false };
const evidence = { job_id: jobId, snapshot_id: snapshot, commit_sha: sha, retrieval_status: "ready", evidence_count: 1, items: [item] };
const reference = { chunk_id: chunk, snapshot_id: snapshot, commit_sha: sha, path: item.path, symbol: item.symbol,
  start_line: item.start_line, end_line: item.end_line, url };
const report = { report_job_id: reportJob, status: "completed", attempts: 1, error_code: null,
  report: { investigation_id: jobId, repository_id: "902", issue_id: "990", issue_number: 5,
    snapshot_id: snapshot, commit_sha: sha, provider: "mock", model: "deterministic-v1", status: "completed",
    summary: "Mock summary", disclaimer: "Deterministic mock output; not AI reasoning or a diagnosis.",
    hypotheses: [{ title: "Possible area", explanation: "Not a confirmed cause.", observations: ["A chunk was selected."],
      missing_or_contradictory: ["No causal proof."], evidence: [reference], contradictory_evidence: [],
      support_status: "speculative", uncertainty: "high" }], missing_evidence: ["More data needed."],
    next_steps: ["Reproduce the issue."], warnings: ["Mock only"], input_truncated: false, snapshot_partial: false,
    created_at: "2026-01-01T00:00:00Z" } };

class FakeClock {
  tasks = new Map(); nextId = 1;
  setTimeout = (callback, ms) => { const id = this.nextId++; this.tasks.set(id, { callback, ms }); return id; };
  clearTimeout = id => this.tasks.delete(id);
  async run(ms) {
    const entry = [...this.tasks].find(([, value]) => value.ms === ms);
    assert.ok(entry, `missing timer ${ms}`);
    this.tasks.delete(entry[0]); entry[1].callback();
    await new Promise(resolve => setImmediate(resolve));
  }
}

function backend({ statuses = ["completed"], reportValue = report, evidenceValue = evidence } = {}) {
  const calls = [];
  let statusIndex = 0;
  const fetch = async (url, options) => {
    calls.push({ url, ...options });
    if (url.includes("/context")) return Response.json(context);
    if (url.endsWith("/issues/5")) return Response.json({ job_id: jobId, status: "queued" }, { status: 202 });
    if (url.includes("/evidence")) return Response.json(evidenceValue);
    if (url.endsWith("/report")) return reportValue === null ? Response.json({}, { status: 404 }) : Response.json(reportValue);
    return Response.json({ ...job, status: statuses[Math.min(statusIndex++, statuses.length - 1)] });
  };
  return { calls, fetch };
}

test("issue numbers are strictly bounded and invalid inputs never fetch", async () => {
  for (const value of ["", "0", "-1", "1.5", "x", "2147483648", "123456789012"]) assert.equal(issueNumber(value), null);
  assert.equal(issueNumber("2147483647"), 2147483647);
  const api = backend(); const c = new InvestigationController(repository, api.fetch, new FakeClock());
  await c.loadIssue("0"); assert.match(c.state.error, /valid GitHub issue number/); assert.equal(api.calls.length, 0);
  await c.loadIssue("5"); assert.equal(c.state.context.number, 5); assert.equal(api.calls.length, 1); c.dispose();
});

test("the default browser fetch uses the global receiver for issue loading", async () => {
  const source = fs.readFileSync(path.join(root, "lib/investigation-client.ts"), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022 } }).outputText;
  const mod = { exports: {} };
  const sandbox = vm.createContext({ module: mod, exports: mod.exports, URL, AbortController, setTimeout, clearTimeout });
  const browserGlobal = vm.runInContext("globalThis", sandbox);
  let calls = 0;
  const issueOne = { ...context, repository_id: "1435878031", issue_id: "6098219743", number: 1,
    url: "https://github.com/roshan-pandit1/RepoPilot/issues/1" };
  sandbox.fetch = function (url, options) {
    if (this !== browserGlobal) throw new TypeError("Illegal invocation");
    calls++;
    assert.equal(url, "/api/repositories/1435878031/issues/1/context");
    assert.equal(options.method, "GET");
    return Promise.resolve(Response.json(issueOne));
  };
  new vm.Script(code).runInContext(sandbox);
  const c = new mod.exports.InvestigationController({ id: "1435878031", full_name: "roshan-pandit1/RepoPilot", enabled: true });
  await c.loadIssue("1");
  assert.equal(calls, 1);
  assert.equal(c.state.context?.number, 1);
  assert.equal(c.state.error, "");
  c.dispose();
});

test("submission is explicit, single-flight and polls only until terminal status", async () => {
  const api = backend({ statuses: ["queued", "running", "completed"] }); const timer = new FakeClock();
  let release; let posts = 0;
  const fetch = async (url, options) => {
    if (options.method === "POST") { posts++; assert.equal(options.headers, undefined);
      await new Promise(resolve => { release = resolve; }); }
    return api.fetch(url, options);
  };
  const c = new InvestigationController(repository, fetch, timer);
  await c.loadIssue("5"); assert.equal(posts, 0);
  const first = c.submit(); await Promise.resolve(); await c.submit(); assert.equal(posts, 1);
  release(); await first; assert.equal(c.state.job.status, "queued");
  await timer.run(3000); assert.equal(c.state.job.status, "running");
  await timer.run(3000); assert.equal(c.state.job.status, "completed");
  assert.equal(c.state.evidence.items.length, 1); assert.equal(c.state.report.report.provider, "mock");
  assert.equal([...timer.tasks.values()].some(t => t.ms === 3000), false);
  c.dispose(); assert.equal(timer.tasks.size, 0);
});

test("browser submission does not read or attach authentication cookies", async () => {
  const api = backend(); const c = new InvestigationController(repository, api.fetch, new FakeClock());
  await c.loadIssue("5"); await c.submit();
  const post = api.calls.find(call => call.method === "POST");
  assert.ok(post); assert.equal(post.headers, undefined);
  c.dispose();
});

test("missing report can be requested explicitly, and empty evidence is safe", async () => {
  const empty = { ...evidence, evidence_count: 0, retrieval_status: "no_matches", items: [] };
  const api = backend({ evidenceValue: empty, reportValue: null }); const timer = new FakeClock();
  const emptyReport = structuredClone(report); emptyReport.report.hypotheses = [];
  let reportPosts = 0, reportReads = 0, created = false;
  const fetch = async (url, options) => {
    if (url.endsWith("/report") && options.method === "POST") { reportPosts++; created = true; return Response.json({ report_job_id: reportJob, status: "queued", provider: "mock" }, { status: 202 }); }
    if (url.endsWith("/report") && created) {
      reportReads++;
      return Response.json(reportReads === 1 ? { report_job_id: reportJob, status: "running", attempts: 1, error_code: null, report: null } : emptyReport);
    }
    return api.fetch(url, options);
  };
  const c = new InvestigationController(repository, fetch, timer);
  await c.loadIssue("5"); await c.openJob(jobId);
  assert.equal(c.state.evidence.items.length, 0); assert.equal(c.state.reportMissing, true); assert.equal(reportPosts, 0);
  await c.generateReport(); assert.equal(reportPosts, 1); assert.equal(c.state.report.status, "running");
  await timer.run(3000); assert.equal(c.state.report.status, "completed");
  assert.equal(c.state.report.report.hypotheses.length, 0); c.dispose();
});

test("repeated report clicks make one request while the first is pending", async () => {
  const api = backend({ reportValue: null }); let release, posts = 0;
  const fetch = async (url, options) => {
    if (url.endsWith("/report") && options.method === "POST") { posts++;
      await new Promise(resolve => { release = resolve; });
      return Response.json({ report_job_id: reportJob, status: "queued", provider: "mock" }, { status: 202 }); }
    return api.fetch(url, options);
  };
  const c = new InvestigationController(repository, fetch, new FakeClock());
  await c.loadIssue("5"); await c.openJob(jobId);
  const first = c.generateReport(); await Promise.resolve(); await c.generateReport();
  assert.equal(posts, 1); release(); await first; c.dispose();
});

test("revoked access and expired sessions clear cached content", async () => {
  const api = backend(); const timer = new FakeClock(); let revoked = false;
  const fetch = async (url, options) => revoked && url.includes("/evidence") ? Response.json({}, { status: 404 }) : api.fetch(url, options);
  const c = new InvestigationController(repository, fetch, timer);
  await c.loadIssue("5"); await c.openJob(jobId); assert.ok(c.state.report);
  revoked = true; await timer.run(30000);
  assert.equal(c.state.report, null); assert.equal(c.state.evidence, null); assert.equal(c.state.context, null);
  assert.match(c.state.error, /unavailable/); c.dispose();
  const denied = new InvestigationController(repository, async () => Response.json({}, { status: 401 }), new FakeClock());
  await denied.loadIssue("5"); assert.match(denied.state.error, /session has expired/); denied.dispose();
});

test("hiding the view removes displayed source and cancels further refresh", async () => {
  const api = backend(); const timer = new FakeClock();
  const c = new InvestigationController(repository, api.fetch, timer);
  await c.loadIssue("5"); await c.openJob(jobId); assert.ok(c.state.report);
  c.hideResults(); assert.equal(c.state.evidence, null); assert.equal(c.state.report, null);
  assert.equal(timer.tasks.size, 0); assert.match(c.state.notice, /recheck access/); c.dispose();
});

test("hiding during an evidence request aborts it and ignores its late response", async () => {
  const api = backend(); const timer = new FakeClock(); let release, signal, delayed = false;
  const fetch = async (url, options) => {
    if (url.includes("/evidence") && !delayed) {
      delayed = true; signal = options.signal;
      await new Promise(resolve => { release = resolve; });
    }
    return api.fetch(url, options);
  };
  const c = new InvestigationController(repository, fetch, timer);
  await c.loadIssue("5"); const pending = c.openJob(jobId);
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(release); c.hideResults(); assert.equal(signal.aborted, true);
  release(); await pending;
  assert.equal(c.state.evidence, null); assert.equal(c.state.report, null);
  assert.equal(api.calls.some(call => call.url.endsWith("/report")), false);
  assert.match(c.state.notice, /recheck access/);
  c.showResults(); await c.refreshResults(); assert.ok(c.state.report); c.dispose();
});

test("a submission completed in a hidden tab does not display evidence", async () => {
  const api = backend(); const timer = new FakeClock(); let release;
  const fetch = async (url, options) => {
    if (options.method === "POST") await new Promise(resolve => { release = resolve; });
    return api.fetch(url, options);
  };
  const c = new InvestigationController(repository, fetch, timer);
  await c.loadIssue("5"); const pending = c.submit(); await Promise.resolve();
  c.hideResults(); release(); await pending;
  assert.equal(c.state.job.status, "completed"); assert.equal(c.state.evidence, null);
  assert.equal(api.calls.some(call => call.url.includes("/evidence")), false);
  c.showResults(); await c.refreshResults(); assert.ok(c.state.report); c.dispose();
});

test("hiding pauses job polling and a report POST cannot restore hidden evidence", async () => {
  const queued = backend({ statuses: ["queued"] }); const timer = new FakeClock();
  const c = new InvestigationController(repository, queued.fetch, timer);
  await c.loadIssue("5"); await c.openJob(jobId); c.hideResults();
  assert.equal(timer.tasks.size, 0); assert.match(c.state.notice, /polling paused/i);
  c.showResults(); await c.refreshJob(); assert.equal(c.state.job.status, "queued"); c.dispose();

  const missing = backend({ reportValue: null }); let release, posts = 0;
  const fetch = async (url, options) => {
    if (url.endsWith("/report") && options.method === "POST") {
      posts++; await new Promise(resolve => { release = resolve; });
      return Response.json({ report_job_id: reportJob, status: "queued", provider: "mock" }, { status: 202 });
    }
    return missing.fetch(url, options);
  };
  const other = new InvestigationController(repository, fetch, new FakeClock());
  await other.loadIssue("5"); await other.openJob(jobId);
  const pending = other.generateReport(); await Promise.resolve(); other.hideResults();
  assert.equal(other.state.evidence, null); release(); await pending;
  assert.equal(posts, 1); assert.equal(other.state.evidence, null); assert.equal(other.state.report, null);
  other.showResults(); await other.refreshResults(); assert.equal(other.state.reportMissing, true); other.dispose();
});

test("foreign report citations and mismatched issue or snapshot fail closed", async () => {
  const forged = structuredClone(report); forged.report.hypotheses[0].evidence[0].snapshot_id = "55555555-5555-4555-8555-555555555555";
  const api = backend({ reportValue: forged }); const c = new InvestigationController(repository, api.fetch, new FakeClock());
  await c.loadIssue("5"); await c.openJob(jobId);
  assert.equal(c.state.report, null); assert.equal(c.state.evidence, null); assert.match(c.state.error, /Invalid report citation/); c.dispose();
  const wrong = backend(); const fetch = async (url, opts) => url.endsWith(jobId) ? Response.json({ ...job, issue_number: 6 }) : wrong.fetch(url, opts);
  const other = new InvestigationController(repository, fetch, new FakeClock());
  await other.loadIssue("5"); await other.openJob(jobId); assert.match(other.state.error, /Invalid investigation status/); other.dispose();
});

test("invalid evidence citations and malformed reports fail closed", async () => {
  const badEvidence = { ...evidence, items: [{ ...item, url: "https://evil.invalid/source" }] };
  const api = backend({ evidenceValue: badEvidence }); const c = new InvestigationController(repository, api.fetch, new FakeClock());
  await c.loadIssue("5"); await c.openJob(jobId);
  assert.equal(c.state.evidence, null); assert.match(c.state.error, /Invalid evidence response/); c.dispose();
  const invalidReport = { ...report, report: { ...report.report, hypotheses: "bad" } };
  const otherApi = backend({ reportValue: invalidReport });
  const other = new InvestigationController(repository, otherApi.fetch, new FakeClock());
  await other.loadIssue("5"); await other.openJob(jobId);
  assert.equal(other.state.report, null); assert.match(other.state.error, /Invalid report response/); other.dispose();
});

test("superseded issue requests cannot restore stale content", async () => {
  let release, staleSignal; const api = backend();
  const fetch = async (url, opts) => {
    if (url.includes("/issues/4/context")) { staleSignal = opts.signal; await new Promise(resolve => { release = resolve; });
      return Response.json({ ...context, number: 4, url: "https://github.com/alice/public/issues/4" }); }
    return api.fetch(url, opts);
  };
  const c = new InvestigationController(repository, fetch, new FakeClock());
  const stale = c.loadIssue("4"); await Promise.resolve(); await c.loadIssue("5"); release(); await stale;
  assert.equal(staleSignal.aborted, true); assert.equal(c.state.context.number, 5); c.dispose();
});

test("unmount aborts an in-flight request and ignores its late response", async () => {
  let release, signal, updates = 0;
  const fetch = async (_url, options) => { signal = options.signal;
    await new Promise(resolve => { release = resolve; }); return Response.json(context); };
  const timer = new FakeClock(); const c = new InvestigationController(repository, fetch, timer);
  c.subscribe(() => { updates++; });
  const pending = c.loadIssue("5"); await Promise.resolve();
  const before = updates; c.dispose(); release(); await pending;
  assert.equal(signal.aborted, true); assert.equal(updates, before); assert.equal(timer.tasks.size, 0);
});

test("job polling stops at its bound and can be resumed explicitly", async () => {
  const api = backend({ statuses: ["queued"] }); const timer = new FakeClock();
  const c = new InvestigationController(repository, api.fetch, timer);
  await c.loadIssue("5"); await c.openJob(jobId);
  for (let i = 0; i < 40; i++) await timer.run(3000);
  assert.match(c.state.notice, /polling paused/i);
  assert.equal([...timer.tasks.values()].some(t => t.ms === 3000), false);
  await c.refreshJob(); assert.equal(c.state.job.status, "queued");
  assert.equal([...timer.tasks.values()].some(t => t.ms === 3000), true); c.dispose();
});

test("historical mock-orchestration jobs show status without fetching evidence or reports", async () => {
  const api = backend(); const calls = [];
  const fetch = async (url, options) => {
    calls.push({ url, method: options.method });
    return url.endsWith(jobId) ? Response.json(historicalJob) : api.fetch(url, options);
  };
  const timer = new FakeClock(); const c = new InvestigationController(repository, fetch, timer);
  await c.loadIssue("5"); await c.openJob(jobId); await c.refreshResults(); await c.generateReport();
  assert.equal(c.state.error, ""); assert.equal(c.state.job.operation, "mock_orchestration");
  assert.equal(c.state.job.status, "completed"); assert.equal(c.state.job.snapshot_id, null);
  assert.equal(c.state.job.commit_sha, null); assert.equal(c.state.evidence, null); assert.equal(c.state.report, null);
  assert.equal(calls.some(call => call.url.includes("/evidence") || call.url.endsWith("/report")), false);
  assert.equal(calls.some(call => call.method === "POST"), false);
  const html = render(views.InvestigationStatus, { job: c.state.job });
  assert.match(html, /mock orchestration/i); assert.match(html, /does not retrieve source evidence/i);
  assert.doesNotMatch(html, /Commit|Snapshot/); c.dispose();
});

test("historical and snapshot-backed status validation rejects inconsistent metadata", async () => {
  for (const invalid of [
    { ...historicalJob, snapshot_id: snapshot }, { ...historicalJob, commit_sha: sha },
    { ...historicalJob, evidence_count: 1 }, { ...historicalJob, retrieval_status: "ready" },
    { ...historicalJob, snapshot_partial: false }, { ...job, snapshot_id: null },
    { ...job, commit_sha: null }, { ...job, operation: "unknown" }
  ]) {
    const api = backend();
    const fetch = (url, options) => url.endsWith(jobId) ? Promise.resolve(Response.json(invalid)) : api.fetch(url, options);
    const c = new InvestigationController(repository, fetch, new FakeClock());
    await c.loadIssue("5"); await c.openJob(jobId);
    assert.equal(c.state.job, null); assert.match(c.state.error, /Invalid investigation status/); c.dispose();
  }
});

test("historical status rechecks access and clears on revocation", async () => {
  const api = backend(); const timer = new FakeClock(); let revoked = false;
  const fetch = (url, options) => url.endsWith(jobId) ?
    Promise.resolve(revoked ? Response.json({}, { status: 404 }) : Response.json(historicalJob)) : api.fetch(url, options);
  const c = new InvestigationController(repository, fetch, timer);
  await c.loadIssue("5"); await c.openJob(jobId);
  c.hideResults(); assert.match(c.state.notice, /Refresh status/); assert.equal(timer.tasks.size, 0);
  c.showResults(); await c.refreshJob(); assert.equal(c.state.job.operation, "mock_orchestration");
  revoked = true; await timer.run(30000);
  assert.equal(c.state.job, null); assert.equal(c.state.context, null); assert.match(c.state.error, /unavailable/);
  c.dispose();
});

test("opening a historical job followed by a snapshot-backed job preserves report access", async () => {
  const legacyId = "55555555-5555-4555-8555-555555555555";
  const api = backend(); const calls = [];
  const fetch = (url, options) => {
    calls.push({ url, method: options.method });
    return url.endsWith(legacyId) ? Promise.resolve(Response.json({ ...historicalJob, job_id: legacyId })) : api.fetch(url, options);
  };
  const c = new InvestigationController(repository, fetch, new FakeClock());
  await c.loadIssue("5"); await c.openJob(legacyId);
  assert.equal(c.state.job.operation, "mock_orchestration"); assert.equal(c.state.report, null);
  await c.openJob(jobId);
  assert.equal(c.state.job.operation, "code_evidence"); assert.equal(c.state.evidence.items.length, 1);
  assert.equal(c.state.report.report.provider, "mock");
  assert.match(render(views.InvestigationReport, { envelope: c.state.report, repository }), /MOCK REPORT — DEMONSTRATION ONLY/);
  assert.equal(calls.some(call => call.method === "POST"), false); c.dispose();
});

test("failed and cancelled jobs remain terminal and show a safe outcome", () => {
  for (const status of ["failed", "cancelled"]) {
    const html = render(views.InvestigationStatus, { job: { ...job, status, error_code: "repository_unavailable" } });
    assert.match(html, /did not complete/); assert.match(html, /Repository access is unavailable/);
  }
});

test("views escape untrusted issue and source text and show mock limitations", () => {
  const attackComment = { id: "99", body: "<svg onload=alert(1)>", created_at: context.created_at,
    updated_at: context.updated_at, truncated: true };
  const issueHtml = render(views.IssueContextView, { issue: { ...context, comments: [attackComment],
    truncation: { ...context.truncation, comments: true } }, repository });
  assert.match(issueHtml, /&lt;script&gt;/); assert.doesNotMatch(issueHtml, /<script>/);
  assert.match(issueHtml, /&lt;svg/); assert.match(issueHtml, /truncated/i);
  const badIssue = render(views.IssueContextView, { issue: { ...context, url: "javascript:alert(1)" }, repository });
  assert.doesNotMatch(badIssue, /href="javascript:/);
  const evidenceHtml = render(views.EvidenceView, { evidence, repository });
  assert.match(evidenceHtml, /&lt;script&gt;/); assert.match(evidenceHtml, /#L3-L4/);
  assert.match(render(views.EvidenceView, { evidence: { ...evidence, items: [] }, repository }), /No code evidence/);
  const reportHtml = render(views.InvestigationReport, { envelope: report, repository });
  assert.match(reportHtml, /MOCK REPORT — DEMONSTRATION ONLY/); assert.match(reportHtml, /speculative/);
  assert.match(reportHtml, /Missing evidence/); assert.match(reportHtml, /Next diagnostic steps/);
  assert.equal(safeCitation({ ...item, url: "javascript:alert(1)" }, repository), null);
});

test("real-provider reports retain grounding and are labeled for human review", async () => {
  const real = structuredClone(report);
  real.report.provider = "openai";
  real.report.model = "gpt-5.6-terra";
  real.report.disclaimer = "Model-generated possibilities require human review; they are not verified diagnoses.";
  const api = backend({ reportValue: real });
  const c = new InvestigationController(repository, api.fetch, new FakeClock());
  await c.loadIssue("5"); await c.openJob(jobId);
  assert.equal(c.state.report.report.provider, "openai");
  const html = render(views.InvestigationReport, { envelope: c.state.report, repository });
  assert.match(html, /MODEL-GENERATED REPORT — HUMAN REVIEW REQUIRED/);
  assert.doesNotMatch(html, /MOCK REPORT — DEMONSTRATION ONLY/);
  c.dispose();
  const mismatch = structuredClone(real); mismatch.report.model = "deterministic-v1";
  const other = new InvestigationController(repository, backend({ reportValue: mismatch }).fetch, new FakeClock());
  await other.loadIssue("5"); await other.openJob(jobId);
  assert.match(other.state.error, /Invalid report response/);
  other.dispose();
});
