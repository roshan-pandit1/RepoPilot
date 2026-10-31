import type { Repository } from "./types";

export type IssueContext = { repository_id: string; issue_id: string; number: number; title: string;
  body: string; state: "open" | "closed"; labels: string[];
  comments: { id: string; body: string; created_at: string; updated_at: string; truncated: boolean }[];
  created_at: string; updated_at: string; retrieved_at: string; url: string;
  truncation: Record<"title" | "body" | "labels" | "comments" | "total", boolean> };
export type JobState = "queued" | "running" | "completed" | "failed" | "cancelled";
export type Job = { job_id: string; issue_id: string; issue_number: number; status: JobState; attempts: number;
  operation: "code_evidence" | "mock_orchestration"; snapshot_id: string | null; commit_sha: string | null; retrieval_status: string;
  evidence_count: number; error_code: string | null; snapshot_partial: boolean | null };
export type EvidenceItem = { chunk_id: string; rank: number; query_id: string; query_rank: number; method: string;
  path: string; symbol: string | null; start_line: number; end_line: number; commit_sha: string; url: string;
  snippet: string | null; snippet_truncated: boolean; snippet_unavailable: boolean };
export type Evidence = { job_id: string; snapshot_id: string; commit_sha: string; retrieval_status: string;
  evidence_count: number; items: EvidenceItem[] };
export type Citation = { chunk_id: string; snapshot_id: string; commit_sha: string; path: string;
  symbol: string | null; start_line: number; end_line: number; url: string };
export type Hypothesis = { title: string; explanation: string; observations: string[]; missing_or_contradictory: string[];
  evidence: Citation[]; contradictory_evidence: Citation[]; support_status: "speculative" | "unsupported"; uncertainty: "high" };
export type Report = { investigation_id: string; repository_id: string; issue_id: string; issue_number: number;
  snapshot_id: string; commit_sha: string; provider: "mock" | "openai"; model: "deterministic-v1" | "gpt-5.6-terra"; status: "completed";
  summary: string; hypotheses: Hypothesis[]; missing_evidence: string[]; next_steps: string[]; warnings: string[];
  disclaimer: string; input_truncated: boolean; snapshot_partial: boolean; created_at: string };
export type ReportEnvelope = { report_job_id: string; status: JobState; attempts: number;
  error_code: string | null; report: Report | null };
export type InvestigationView = { context: IssueContext | null; job: Job | null; evidence: Evidence | null;
  report: ReportEnvelope | null; reportMissing: boolean; acceptedJobId: string | null; busy: string; error: string; notice: string };

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const commit = /^[0-9a-f]{40}$/;
const states = new Set(["queued", "running", "completed", "failed", "cancelled"]);
const terminal = (s: JobState) => s === "completed" || s === "failed" || s === "cancelled";
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown, max = 30000): value is string => typeof value === "string" && [...value].length <= max;
const number = (value: unknown, min: number, max: number): value is number =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= min && value <= max;
const strings = (value: unknown, max: number) => Array.isArray(value) && value.length <= max && value.every(v => text(v, 2000));
const validId = (value: unknown): value is string => typeof value === "string" && uuid.test(value);

export function issueNumber(value: string): number | null {
  if (!/^[0-9]{1,10}$/.test(value)) return null;
  const n = Number(value);
  return Number.isSafeInteger(n) && n > 0 && n < 2147483648 ? n : null;
}

export function safeCitation(item: { url: string; path: string; commit_sha: string; start_line: number; end_line: number }, repository: Repository): string | null {
  try {
    const url = new URL(item.url);
    const expected = `/${repository.full_name}/blob/${item.commit_sha}/${item.path}`;
    if (repository.full_name.split("/").length !== 2 || url.protocol !== "https:" || url.host !== "github.com" ||
        url.username || url.password || url.search || decodeURIComponent(url.pathname) !== expected ||
        !commit.test(item.commit_sha) || !number(item.start_line, 1, 10000000) ||
        !number(item.end_line, item.start_line, 10000000) || url.hash !== `#L${item.start_line}-L${item.end_line}`) return null;
    return item.url;
  } catch { return null; }
}

export function safeIssueUrl(url: string, repository: Repository, issue: number): string | null {
  const parts = repository.full_name.split("/");
  if (parts.length !== 2 || parts.some(part => !part || part === "." || part === "..")) return null;
  return url === `https://github.com/${parts.map(encodeURIComponent).join("/")}/issues/${issue}` ? url : null;
}

function issueContext(value: unknown, repo: Repository, expected: number): IssueContext {
  if (!object(value) || value.repository_id !== repo.id || !text(value.issue_id, 20) || !/^[0-9]+$/.test(value.issue_id) ||
      value.number !== expected || !text(value.title, 1024) || !text(value.body, 50000) ||
      (value.state !== "open" && value.state !== "closed") || !strings(value.labels, 30) ||
      !Array.isArray(value.comments) || value.comments.length > 30 || !value.comments.every(c => object(c) && text(c.id, 20) &&
        text(c.body, 5000) && text(c.created_at, 64) && text(c.updated_at, 64) && typeof c.truncated === "boolean") ||
      !text(value.created_at, 64) || !text(value.updated_at, 64) || !text(value.retrieved_at, 64) ||
      !text(value.url, 2048) || !object(value.truncation) ||
      !["title", "body", "labels", "comments", "total"].every(k => typeof (value.truncation as Record<string, unknown>)[k] === "boolean")) {
    throw new Error("Invalid issue context response.");
  }
  if (!safeIssueUrl(value.url, repo, expected)) throw new Error("Invalid issue context response.");
  return value as IssueContext;
}

function jobResponse(value: unknown, id: string, context: IssueContext): Job {
  if (!object(value) || value.job_id !== id || value.issue_number !== context.number || value.issue_id !== context.issue_id ||
      !text(value.status, 20) || !states.has(value.status) || !number(value.attempts, 0, 100) ||
      !text(value.retrieval_status, 40) || !number(value.evidence_count, 0, 30) ||
      !(value.error_code === null || text(value.error_code, 80)) ||
      !(value.snapshot_partial === null || typeof value.snapshot_partial === "boolean")) throw new Error("Invalid investigation status response.");
  if (value.operation === "mock_orchestration") {
    if (value.snapshot_id !== null || value.commit_sha !== null || value.retrieval_status !== "not_applicable" ||
        value.evidence_count !== 0 || value.snapshot_partial !== null) throw new Error("Invalid investigation status response.");
  } else if (value.operation !== "code_evidence" || !validId(value.snapshot_id) ||
      !text(value.commit_sha, 40) || !commit.test(value.commit_sha)) throw new Error("Invalid investigation status response.");
  return value as Job;
}

function evidenceResponse(value: unknown, job: Job, repo: Repository): Evidence {
  if (!object(value) || value.job_id !== job.job_id || value.snapshot_id !== job.snapshot_id || value.commit_sha !== job.commit_sha ||
      !text(value.retrieval_status, 40) || !number(value.evidence_count, 0, 30) || !Array.isArray(value.items) ||
      value.items.length !== value.evidence_count || value.items.length > 30) throw new Error("Invalid evidence response.");
  const seen = new Set<string>();
  for (const [index, item] of value.items.entries()) {
    if (!object(item) || !validId(item.chunk_id) || seen.has(item.chunk_id) || item.rank !== index + 1 ||
        !text(item.path, 1000) || !(item.symbol === null || text(item.symbol, 300)) ||
        !number(item.start_line, 1, 10000000) || !number(item.end_line, item.start_line, 10000000) ||
        item.commit_sha !== job.commit_sha || !text(item.url, 2048) || !text(item.query_id, 40) ||
        !number(item.query_rank, 1, 20) || item.method !== "keyword" ||
        !(item.snippet === null || text(item.snippet, 4000)) || typeof item.snippet_truncated !== "boolean" ||
        typeof item.snippet_unavailable !== "boolean" || (item.snippet === null) !== item.snippet_unavailable ||
        !safeCitation(item as EvidenceItem, repo)) throw new Error("Invalid evidence response.");
    seen.add(item.chunk_id);
  }
  return value as Evidence;
}

function reportResponse(value: unknown, job: Job, context: IssueContext, evidence: Evidence, repo: Repository): ReportEnvelope {
  if (!object(value) || !validId(value.report_job_id) || !text(value.status, 20) || !states.has(value.status) ||
      !number(value.attempts, 0, 100) || !(value.error_code === null || text(value.error_code, 80))) throw new Error("Invalid report response.");
  if (value.status !== "completed") {
    if (value.report !== null) throw new Error("Invalid report response.");
    return value as ReportEnvelope;
  }
  const r = value.report;
  if (!object(r) || r.investigation_id !== job.job_id || r.repository_id !== repo.id || r.issue_id !== context.issue_id ||
      r.issue_number !== context.number || r.snapshot_id !== job.snapshot_id || r.commit_sha !== job.commit_sha ||
      !((r.provider === "mock" && r.model === "deterministic-v1") ||
        (r.provider === "openai" && r.model === "gpt-5.6-terra")) || r.status !== "completed" ||
      !text(r.summary, 600) || !text(r.disclaimer, 300) || !text(r.created_at, 64) ||
      !Array.isArray(r.hypotheses) || r.hypotheses.length > 3 || !strings(r.missing_evidence, 4) ||
      !strings(r.next_steps, 4) || !strings(r.warnings, 4) || typeof r.input_truncated !== "boolean" ||
      typeof r.snapshot_partial !== "boolean") throw new Error("Invalid report response.");
  for (const h of r.hypotheses) {
    if (!object(h) || !text(h.title, 160) || !text(h.explanation, 500) || !strings(h.observations, 3) ||
        !strings(h.missing_or_contradictory, 3) || !Array.isArray(h.evidence) || h.evidence.length > 4 ||
        !Array.isArray(h.contradictory_evidence) || h.contradictory_evidence.length > 4 || h.uncertainty !== "high" ||
        h.support_status !== (h.evidence.length ? "speculative" : "unsupported")) throw new Error("Invalid report response.");
    const seen = new Set<string>();
    for (const ref of [...h.evidence, ...h.contradictory_evidence]) {
      if (!object(ref) || !validId(ref.chunk_id) || seen.has(ref.chunk_id)) throw new Error("Invalid report citation.");
      const item = evidence.items.find(item => item.chunk_id === ref.chunk_id);
      if (!item || ref.snapshot_id !== job.snapshot_id || ref.commit_sha !== job.commit_sha ||
          ref.path !== item.path || ref.symbol !== item.symbol || ref.start_line !== item.start_line ||
          ref.end_line !== item.end_line || ref.url !== item.url) throw new Error("Invalid report citation.");
      seen.add(ref.chunk_id);
    }
  }
  return value as ReportEnvelope;
}

class RequestFailure extends Error {
  constructor(public status: number) { super(status === 401 ? "Your session has expired. Sign in again." :
    status === 403 || status === 404 ? "Repository, issue or investigation is unavailable. Check your access." :
    status === 409 ? "The selected source snapshot or evidence is no longer available." : "Request unavailable. Please try again."); }
}
type Fetcher = (url: string, options: RequestInit) => Promise<Response>;
type Timer = ReturnType<typeof setTimeout>;
type Clock = { setTimeout: (callback: () => void, ms: number) => Timer; clearTimeout: (id: Timer) => void };
const clock: Clock = { setTimeout: (fn, ms) => setTimeout(fn, ms), clearTimeout: id => clearTimeout(id) };
const initial = (): InvestigationView => ({ context: null, job: null, evidence: null, report: null,
  reportMissing: false, acceptedJobId: null, busy: "", error: "", notice: "" });

export class InvestigationController {
  state: InvestigationView = initial();
  private listeners = new Set<(value: InvestigationView) => void>();
  private epoch = 0;
  private controllers = new Set<AbortController>();
  private timers = new Set<Timer>();
  private scheduled: Timer | null = null;
  private submitting = false;
  private disposed = false;
  private hidden = false;
  private jobPolls = 0;
  private reportPolls = 0;
  private accessChecks = 0;
  constructor(private repo: Repository, private fetcher: Fetcher = (url, options) => globalThis.fetch(url, options),
    private timer: Clock = clock) {}
  subscribe(listener: (value: InvestigationView) => void) { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  private update(patch: Partial<InvestigationView>) { if (this.disposed) return; this.state = { ...this.state, ...patch }; this.listeners.forEach(fn => fn(this.state)); }
  private cancel() { this.epoch++; this.controllers.forEach(c => c.abort()); this.controllers.clear();
    this.timers.forEach(t => this.timer.clearTimeout(t)); this.timers.clear(); this.scheduled = null; this.submitting = false; }
  dispose() { this.cancel(); this.disposed = true; this.listeners.clear(); }
  clear() { this.cancel(); this.update(initial()); }
  hideResults() {
    this.hidden = true;
    // Do not abort an accepted-or-pending POST: its outcome may already be durable.
    if (this.submitting) {
      this.update({ evidence: null, report: null, reportMissing: false,
        notice: "Evidence hidden while this tab was inactive. Refresh to recheck access." });
      return;
    }
    if (!this.state.job && this.state.busy !== "job") return;
    this.cancel(); this.update({ evidence: null, report: null, reportMissing: false, busy: "",
      notice: this.state.job?.operation === "mock_orchestration" ?
        "Status checks paused while this tab was inactive. Refresh status to recheck access." :
        this.state.job && !terminal(this.state.job.status) ?
        "Status polling paused while this tab was inactive. Refresh status to continue." :
        "Evidence hidden while this tab was inactive. Refresh to recheck access." });
  }
  showResults() { this.hidden = false; }
  private later(callback: () => void, ms: number) {
    if (this.scheduled !== null) { this.timer.clearTimeout(this.scheduled); this.timers.delete(this.scheduled); }
    const id = this.timer.setTimeout(() => { this.timers.delete(id); this.scheduled = null; callback(); }, ms);
    this.scheduled = id; this.timers.add(id);
  }
  private async request(url: string, method = "GET"): Promise<unknown> {
    const controller = new AbortController(); this.controllers.add(controller);
    const timeout = this.timer.setTimeout(() => controller.abort(), 20000);
    try {
      const response = await this.fetcher(url, { method, cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new RequestFailure(response.status);
      return await response.json();
    } finally { this.timer.clearTimeout(timeout); this.controllers.delete(controller); }
  }
  private failed(error: unknown, epoch: number) {
    if (epoch !== this.epoch || this.disposed) return;
    const safe = new Set(["Invalid issue context response.", "Invalid investigation status response.", "Invalid evidence response.",
      "Invalid report response.", "Invalid report citation.", "Invalid submission response.", "Invalid report submission response."]);
    const message = error instanceof RequestFailure ? error.message : error instanceof Error && error.name === "AbortError" ?
      "Request timed out. Please try again." : error instanceof Error && safe.has(error.message) ? error.message : "Request unavailable. Please try again.";
    // On any inability to revalidate, remove cached issue and source/report content.
    const acceptedJobId = this.state.acceptedJobId;
    this.cancel(); this.update({ ...initial(), acceptedJobId, error: message });
  }
  async loadIssue(raw: string) {
    this.cancel(); const epoch = this.epoch; this.update({ ...initial(), busy: "issue" });
    const n = issueNumber(raw);
    if (!n) { this.update({ busy: "", error: "Enter a valid GitHub issue number (1–2147483647)." }); return; }
    try {
      const value = await this.request(`/api/repositories/${this.repo.id}/issues/${n}/context`);
      const context = issueContext(value, this.repo, n);
      if (epoch === this.epoch) this.update({ context, busy: "", error: "" });
    } catch (error) { this.failed(error, epoch); }
  }
  async submit() {
    const context = this.state.context;
    if (!context || this.submitting || this.state.job) return;
    this.submitting = true; const epoch = this.epoch; this.update({ busy: "submit", error: "" });
    try {
      const value = await this.request(`/api/investigations/${this.repo.id}/issues/${context.number}`, "POST");
      if (!object(value) || !validId(value.job_id) || !text(value.status, 20) || !states.has(value.status)) throw new Error("Invalid submission response.");
      if (epoch === this.epoch) { this.update({ busy: "job", acceptedJobId: value.job_id }); this.jobPolls = 0; await this.loadJob(value.job_id, epoch); }
    } catch (error) {
      if (epoch === this.epoch && !(error instanceof RequestFailure && [401, 403, 404, 409, 422].includes(error.status))) {
        this.cancel(); this.update({ ...initial(), error: "Submission may have reached the server. Check for an existing job before retrying." });
      } else this.failed(error, epoch);
    }
    finally { if (epoch === this.epoch) this.submitting = false; }
  }
  async openJob(id: string) {
    if (!this.state.context) { this.update({ error: "Load the issue before opening an investigation." }); return; }
    if (!uuid.test(id)) { this.update({ error: "Enter a valid investigation job ID." }); return; }
    this.cancel(); const epoch = this.epoch; this.jobPolls = 0; this.accessChecks = 0; this.update({ job: null, evidence: null, report: null,
      reportMissing: false, acceptedJobId: id, busy: "job", error: "", notice: "" });
    await this.loadJob(id, epoch);
  }
  async refreshJob() { if (this.state.job && !this.state.busy) { const id = this.state.job.job_id; this.cancel(); this.jobPolls = 0; this.accessChecks = 0; await this.loadJob(id, this.epoch); } }
  private async loadJob(id: string, epoch: number) {
    const context = this.state.context; if (!context) return;
    try {
      const value = await this.request(`/api/investigations/${this.repo.id}/jobs/${id}`);
      const job = jobResponse(value, id, context);
      if (epoch !== this.epoch) return;
      this.update({ job, busy: "", error: "", notice: "" });
      if (this.hidden) {
        this.update({ notice: "Investigation paused while this tab was inactive. Refresh to recheck access." });
        return;
      }
      if (!terminal(job.status)) {
        if (++this.jobPolls <= 40) this.later(() => { void this.loadJob(id, epoch); }, 3000);
        else this.update({ notice: "Status polling paused. Refresh status to continue." });
      } else if (job.status === "completed" && job.operation === "code_evidence" && job.retrieval_status !== "snapshot_unavailable") {
        this.accessChecks = 0; await this.loadResults(epoch, true);
      } else if (job.status === "completed" && job.operation === "mock_orchestration") {
        // Reauthorize displayed historical status on the same bounded cadence as evidence.
        if (++this.accessChecks <= 4) this.later(() => { void this.loadJob(id, epoch); }, 30000);
        else this.update({ ...initial(), acceptedJobId: id, notice: "Investigation status expired. Reload the issue and open the job to recheck access." });
      }
    } catch (error) { this.failed(error, epoch); }
  }
  async refreshResults() { if (!this.state.busy) { this.cancel(); this.accessChecks = 0; await this.loadResults(this.epoch, true); } }
  private async loadResults(epoch: number, schedule: boolean) {
    const job = this.state.job, context = this.state.context;
    if (!job || !context || job.status !== "completed" || job.operation !== "code_evidence") return;
    if (this.hidden) {
      this.update({ busy: "", evidence: null, report: null, reportMissing: false,
        notice: "Evidence hidden while this tab was inactive. Refresh to recheck access." });
      return;
    }
    try {
      const base = `/api/investigations/${this.repo.id}/jobs/${job.job_id}`;
      const evidence = evidenceResponse(await this.request(`${base}/evidence?include_snippets=true`), job, this.repo);
      if (epoch !== this.epoch || this.hidden) return;
      let report: ReportEnvelope | null = null, missing = false;
      try { report = reportResponse(await this.request(`${base}/report`), job, context, evidence, this.repo); }
      catch (error) {
        if (!(error instanceof RequestFailure) || error.status !== 404) throw error;
        if (epoch !== this.epoch || this.hidden) return;
        // A 404 can mean either no report or lost access. Recheck access before showing evidence.
        evidenceResponse(await this.request(`${base}/evidence?include_snippets=true`), job, this.repo);
        missing = true;
      }
      if (epoch !== this.epoch || this.hidden) return;
      this.update({ evidence, report, reportMissing: missing, busy: "", error: "", notice: "" });
      if (report && !terminal(report.status)) {
        if (++this.reportPolls <= 40) this.later(() => { void this.loadResults(epoch, true); }, 3000);
        else this.update({ evidence: null, report: null, reportMissing: false, notice: "Report polling paused. Refresh evidence to continue." });
      } else if (schedule) {
        // Periodically reauthorize displayed content, then expire it rather than cache indefinitely.
        if (++this.accessChecks <= 4) this.later(() => { void this.loadResults(epoch, true); }, 30000);
        else this.update({ evidence: null, report: null, reportMissing: false,
          notice: "Evidence display expired. Refresh to recheck access." });
      }
    } catch (error) { this.failed(error, epoch); }
  }
  async generateReport() {
    const job = this.state.job;
    if (!job || job.status !== "completed" || job.operation !== "code_evidence" || !this.state.evidence || !this.state.reportMissing || this.submitting) return;
    this.cancel(); this.submitting = true; const epoch = this.epoch; this.update({ busy: "report", error: "" });
    try {
      const value = await this.request(`/api/investigations/${this.repo.id}/jobs/${job.job_id}/report`, "POST");
      if (!object(value) || !validId(value.report_job_id) || !text(value.status, 20) || !states.has(value.status) || !["mock", "openai"].includes(value.provider as string)) throw new Error("Invalid report submission response.");
      if (epoch === this.epoch) { this.reportPolls = 0; await this.loadResults(epoch, true); }
    } catch (error) { this.failed(error, epoch); }
    finally { if (epoch === this.epoch) this.submitting = false; }
  }
}
