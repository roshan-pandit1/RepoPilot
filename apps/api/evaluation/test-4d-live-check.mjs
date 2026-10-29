import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(new URL("./investigation-4d-live-check.js", import.meta.url), "utf8");
const parent = "457d40bf-7e15-4e10-9a27-b8a0de9e513b";
const snapshot = "24e51533-c612-4833-921d-447cfed7df99";
const commit = "63491908290e6874dbaaf2b15c2a96473aad1324";
const base = `/api/investigations/1435878031/jobs/${parent}`;

async function run({ existing = false, badParent = false, badCitation = false } = {}) {
  let posts = 0;
  let reportReads = 0;
  const logs = [];
  const errors = [];
  const state = { job_id: parent, status: badParent ? "running" : "completed", operation: "code_evidence",
    attempts: 1, snapshot_id: snapshot, commit_sha: commit, created_at: "a", updated_at: "b",
    started_at: "c", completed_at: "d" };
  const items = Array.from({ length: 20 }, (_, i) => ({ chunk_id: `chunk-${i}`, path: `src/${i}.py`,
    symbol: "symbol", start_line: 1, end_line: 2, url: `https://github.com/example/${i}` }));
  const ref = { ...items[0], snapshot_id: snapshot, commit_sha: badCitation ? "b".repeat(40) : commit };
  const report = { investigation_id: parent, repository_id: "1435878031", snapshot_id: snapshot,
    commit_sha: commit, provider: "mock", model: "deterministic-v1", status: "completed",
    hypotheses: [{ evidence: [ref], contradictory_evidence: [] }] };
  const response = (status, body) => ({ ok: status >= 200 && status < 300, status, json: async () => body });
  const fetch = async (url, init = {}) => {
    if (url === base) return response(200, state);
    if (url === `${base}/evidence`) return response(200, { snapshot_id: snapshot, commit_sha: commit,
      evidence_count: items.length, items });
    if (url === `${base}/report` && init.method === "POST") {
      posts++;
      assert.equal(init.headers["X-CSRF-Token"], "test-csrf-value");
      return response(202, { report_job_id: "fixture-job", status: "queued" });
    }
    if (url === `${base}/report`) {
      reportReads++;
      if (reportReads === 1 && !existing) return response(404, {});
      return response(200, { report_job_id: "fixture-job", status: "completed", attempts: 1, report });
    }
    throw new Error("unexpected request");
  };
  await vm.runInNewContext(source, { location: { origin: "http://localhost:3000" },
    document: { cookie: "rp_csrf=test-csrf-value" }, fetch,
    console: { log: (...args) => logs.push(args), error: (...args) => errors.push(args) },
    setTimeout: fn => fn(), decodeURIComponent });
  assert.ok(!JSON.stringify({ logs, errors }).includes("test-csrf-value"));
  return { posts, logs, errors };
}

test("one report request verifies citations and preserves parent state", async () => {
  const result = await run();
  assert.equal(result.posts, 1);
  assert.equal(result.errors.length, 0);
  assert.ok(result.logs.some(row => String(row[0]).includes("Validated authorized report references")));
});

test("existing report or changed parent prevents submission", async () => {
  for (const scenario of [{ existing: true }, { badParent: true }]) {
    const result = await run(scenario);
    assert.equal(result.posts, 0);
    assert.equal(result.errors.length, 1);
  }
});

test("a bad citation fails verification without another request", async () => {
  const result = await run({ badCitation: true });
  assert.equal(result.posts, 1);
  assert.equal(result.errors.length, 1);
  assert.match(result.errors[0][1], /citations failed/);
});
