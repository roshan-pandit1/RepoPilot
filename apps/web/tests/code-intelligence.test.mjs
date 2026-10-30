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

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = fs.readFileSync(path.join(root, "components/code-intelligence.tsx"), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
const loaded = { exports: {} };
const context = vm.createContext({ module: loaded, exports: loaded.exports, URL, AbortController,
  require: name => name === "react" ? React : name === "react/jsx-runtime" ? jsxRuntime : (() => { throw new Error(name); })() });
new vm.Script(compiled).runInContext(context);
const { IndexSummary, SearchResults, CodeIntelligence, messageFor, EmbeddingSummary, SearchNotice, createSearchGate } = loaded.exports;
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));
const base = { status: "not_indexed", commit_sha: null, indexed_at: null, file_count: 0, chunk_count: 0, skipped_count: 0, error_code: null };

test("index status distinguishes empty, queued, published, partial and failures", () => {
  assert.match(render(IndexSummary, { status: base }), /No published snapshot/);
  assert.match(render(IndexSummary, { status: { ...base, status: "pending" } }), /Waiting for a worker/);
  assert.match(render(IndexSummary, { status: { ...base, status: "running" } }), /Worker is processing/);
  assert.match(render(IndexSummary, { status: { ...base, status: "completed" } }), /Snapshot unavailable/);
  const published = render(IndexSummary, { status: { ...base, status: "completed", commit_sha: "a".repeat(40), file_count: 40, chunk_count: 278 } });
  assert.match(published, /Indexed files/); assert.match(published, /278/);
  assert.match(render(IndexSummary, { status: { ...base, status: "partial", skipped_count: 2 } }), /2 files were skipped/);
  assert.match(render(IndexSummary, { status: { ...base, status: "failed" } }), /Indexing did not complete/);
  assert.match(render(IndexSummary, { status: { ...base, status: "cancelled" } }), /Indexing stopped/);
});

test("initial rendering and access failures provide actionable guidance", () => {
  const html = render(CodeIntelligence, { repository: { id: "1", full_name: "alice/project", enabled: true } });
  assert.match(html, /Loading indexing status/);
  assert.match(html, /Search indexed code/);
  assert.match(html, /<option value="keyword" selected="">Keyword/);
  assert.match(html, /<option value="semantic">Semantic/);
  assert.match(html, /<option value="hybrid">Hybrid/);
  assert.match(messageFor(401, "Error"), /session has expired/);
  assert.match(messageFor(403, "Error"), /Repository access is unavailable/);
  assert.match(messageFor(404, "Error"), /Repository access is unavailable/);
  assert.match(messageFor(409, "Error"), /No published index/);
  assert.equal(messageFor(503, "Retry"), "Retry");
});

test("embedding readiness and fallback describe the actual search behavior", () => {
  const status = { status: "not_started", ready: false, generation_available: true, completed_chunks: 0, total_chunks: 0, provider: null, model: null, dimensions: null, job_commit: null, error_code: null };
  assert.match(render(EmbeddingSummary, { status }), /Not ready for current snapshot/);
  const ready = render(EmbeddingSummary, { status: { ...status, status: "completed", ready: true, provider: "fake", model: "deterministic-hash", dimensions: 32 } });
  assert.match(ready, /Ready for current snapshot/);
  assert.match(ready, /do not demonstrate semantic understanding/);
  assert.match(render(EmbeddingSummary, { status: { ...status, status: "failed", error_code: "revoked" } }), /revoked/);
  assert.match(render(SearchNotice, { result: { mode: "keyword", fallback_reason: "embeddings_not_ready" } }), /showing keyword results instead/);
  assert.match(render(SearchNotice, { result: { mode: "hybrid", fallback_reason: null } }), /Search mode: hybrid/);
});

test("superseded searches cannot replace newer results", () => {
  const gate = createSearchGate();
  const first = gate.start();
  const second = gate.start();
  assert.equal(first.signal.aborted, true);
  assert.equal(gate.isCurrent(first), false);
  assert.equal(gate.finish(first), false);
  assert.equal(gate.isCurrent(second), true);
  gate.cancel();
  assert.equal(gate.isCurrent(second), false);
});

test("search results escape untrusted source and only link to matching GitHub citations", () => {
  const repository = { id: "1", full_name: "alice/project", enabled: true };
  const sha = "a".repeat(40);
  const item = { path: "src/example.py", symbol: "hello", snippet: "def hello():\n    return '<script>'\n", start_line: 3, end_line: 4, commit_sha: sha, url: `https://github.com/alice/project/blob/${sha}/src/example.py#L3-L4`, score: 1 };
  const safe = render(SearchResults, { repository, results: [item] });
  assert.match(safe, /&lt;script&gt;/); assert.doesNotMatch(safe, /<script>/);
  assert.match(safe, /View source/); assert.match(safe, /#L3-L4/);
  const malicious = render(SearchResults, { repository, results: [{ ...item, url: "javascript:alert(1)" }] });
  assert.match(malicious, /Citation unavailable/); assert.doesNotMatch(malicious, /href="javascript:/);
});
