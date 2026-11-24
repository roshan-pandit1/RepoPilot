import assert from "node:assert/strict";
import { createHash, webcrypto } from "node:crypto";
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
const source = fs.readFileSync(path.join(root, "components/patch-proposals.tsx"), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
const mod = { exports: {} };
const context = vm.createContext({ module: mod, exports: mod.exports, AbortController,
  require: name => name === "react" ? React : name === "react/jsx-runtime" ? jsxRuntime : (() => { throw new Error(name); })() });
new vm.Script(code).runInContext(context);
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));

test("proposal rendering distinguishes static validation from unavailable isolated tests and escapes source", () => {
  const proposal = { id: "id", status: "static_validated", review_state: "unreviewed", commit_sha: "a".repeat(40),
    diff: "+<script>alert(1)</script>", rationale: "Fixture", provider: "synthetic", model: "test",
    changed_files: [{ path: "src/a.py" }], evidence: [{ id: "55555555-5555-4555-8555-555555555555", path: "src/a.py", start_line: 1, end_line: 2 }],
    static_result: { status: "passed" }, test_result: { status: "VALIDATION_UNAVAILABLE", sandbox_used: false } };
  const html = render(mod.exports.ProposalView, { proposal });
  assert.match(html, /Statically validated proposal/);
  assert.match(html, /Automated tests were not run\. This is a proposed patch, not a verified fix/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /never|does not apply/);
});

test("proposal panel announces loading before availability is known", () => {
  const html = render(mod.exports.PatchProposals, { repositoryId: "1", jobId: "job", snapshotId: "snapshot", commit: "a".repeat(40) });
  assert.match(html, /Loading patch availability/);
  assert.doesNotMatch(html, /Test validation: passed/);
});

test("availability states are distinct and errors are escaped", () => {
  const renderState = (state, reason) => render(mod.exports.ProposalAvailability, { state, reason });
  assert.match(renderState("loading"), /Loading patch availability/);
  assert.match(renderState("available"), /generation is available/);
  assert.match(renderState("unavailable", "No provider"), /No provider/);
  const error = renderState("error", "<script>failure</script>");
  assert.match(error, /role="alert"/);
  assert.match(error, /&lt;script&gt;/);
  assert.doesNotMatch(error, /<script>/);
});

test("an empty proposal list is identified without suggesting a completed fix", () => {
  const html = render(mod.exports.ProposalChoices, { items: [], onSelect: () => {} });
  assert.match(html, /No proposals yet/);
  assert.doesNotMatch(html, /validated|passed/);
});

test("synthetic baseline and patched results remain distinct in the review display", () => {
  const base = { id: "id", status: "tests_passed", review_state: "unreviewed", commit_sha: "a".repeat(40),
    diff: "+return a + b", rationale: "Fixture", provider: "test", model: "fixture", changed_files: [], evidence: [],
    static_result: { status: "passed" } };
  const passed = { status: "passed", exit_code: 0, duration_ms: 2, diagnostic: "pass_marker" };
  const failed = { status: "failed", exit_code: 1, duration_ms: 3, diagnostic: "assertion_failed" };
  const test_result = { status: "COMPLETED", sandbox_used: true, test_executed: true, tests_run: ["synthetic-add-reproducer-v1"],
    baseline: failed, patched: passed, outcome: "BASELINE_FAILED_PATCH_PASSED" };
  const html = render(mod.exports.ProposalView, { proposal: { ...base, test_result } });
  assert.match(html, /Baseline: .*failed/);
  assert.match(html, /Patched: .*passed/);
  assert.match(html, /Synthetic fixture only/);
  const both = render(mod.exports.ProposalView, { proposal: { ...base, test_result: { ...test_result, baseline: passed, outcome: "BOTH_PASSED" } } });
  assert.match(both, /Both versions passed/);
  const forged = render(mod.exports.ProposalView, { proposal: { ...base, test_result: { ...test_result, test_executed: false } } });
  assert.match(forged, /Unverified validation result/);
  assert.doesNotMatch(forged, /Proposal: tests_passed/);
});


test("a selected proposal error remains visible when the concurrent list refresh succeeds", async () => {
  const states = [], effects = [], pending = [];
  let cursor = 0, scheduled = [];
  const hooks = {
    useState(initial) { const i = cursor++; if (!(i in states)) states[i] = initial;
      return [states[i], value => { states[i] = typeof value === "function" ? value(states[i]) : value; }]; },
    useRef(initial) { const i = cursor++; if (!(i in states)) states[i] = { current: initial }; return states[i]; },
    useEffect(fn, deps) { const i = cursor++, previous = effects[i];
      if (!previous || deps.some((value, index) => value !== previous.deps[index])) {
        previous?.cleanup?.(); effects[i] = { deps }; scheduled.push(() => { effects[i].cleanup = fn(); });
      } }
  };
  const mockedFetch = url => new Promise(resolve => pending.push({ url, resolve }));
  const componentModule = { exports: {} };
  const fakeContext = vm.createContext({ module: componentModule, exports: componentModule.exports, AbortController,
    fetch: mockedFetch, require: name => name === "react" ? hooks : name === "react/jsx-runtime" ? jsxRuntime : (() => { throw new Error(name); })() });
  new vm.Script(code).runInContext(fakeContext);
  const id = "11111111-1111-4111-8111-111111111111", snapshot = "22222222-2222-4222-8222-222222222222", commit = "a".repeat(40);
  const item = { id, status: "queued", snapshot_id: snapshot, commit_sha: commit, review_state: "unreviewed", error_code: null, dispatch_status: "pending" };
  const listing = { available: true, reason: null, items: [item] };
  const renderPanel = () => { cursor = 0; const tree = componentModule.exports.PatchProposals({ repositoryId: "1", jobId: "job", snapshotId: snapshot, commit });
    const work = scheduled; scheduled = []; work.forEach(fn => fn()); return tree; };
  const find = (element, matches) => {
    if (!element || typeof element !== "object") return null;
    if (matches(element)) return element;
    const children = element.props?.children;
    for (const child of Array.isArray(children) ? children : [children]) { const found = find(child, matches); if (found) return found; }
    return null;
  };
  const settle = async () => { for (let i = 0; i < 5; i++) await Promise.resolve(); };
  const ok = value => ({ ok: true, json: async () => value });
  renderPanel(); pending.shift().resolve(ok(listing)); await settle();
  let tree = renderPanel();
  find(tree, element => element.type === componentModule.exports.ProposalChoices).props.onSelect(id);
  renderPanel(); pending.shift().resolve(ok(item)); await settle();
  tree = renderPanel(); find(tree, element => element.type === "button" && element.props.children === "Refresh proposal").props.onClick();
  renderPanel(); assert.equal(pending.length, 2);
  const listResponse = pending.shift(), detailResponse = pending.shift();
  detailResponse.resolve({ ok: false }); await settle();
  tree = renderPanel(); assert.equal(find(tree, element => element.type === componentModule.exports.ProposalAvailability).props.state, "error");
  listResponse.resolve(ok(listing)); await settle();
  tree = renderPanel();
  const availability = find(tree, element => element.type === componentModule.exports.ProposalAvailability);
  assert.equal(availability.props.state, "error");
  assert.equal(availability.props.reason, "Proposal source or access could not be verified.");
});

test("provider abstention, timeout and unavailability have distinct safe explanations", () => {
  const base = { id: "id", status: "failed", review_state: "unreviewed", commit_sha: "a".repeat(40), dispatch_status: "processed" };
  const show = error_code => render(mod.exports.ProposalView, { proposal: { ...base, error_code } });
  assert.match(show("local_model_insufficient_evidence"), /needs more evidence/);
  assert.match(show("provider_timeout"), /timed out/);
  assert.match(show("provider_unavailable"), /provider is unavailable/);
  assert.match(show("reviewer_cancelled"), /proposal was cancelled/);
  assert.match(show("worker_failed"), /Patch generation failed/);
  for (const code of ["local_model_insufficient_evidence", "provider_timeout", "provider_unavailable"]) {
    const html = show(code);
    assert.doesNotMatch(html, /Statically validated|Tests were run|Sandbox used: yes/);
  }
});


test("proposal preview binds coverage to each evidence reference and identifies stale source", () => {
  const id = "11111111-1111-4111-8111-111111111111", second = "22222222-2222-4222-8222-222222222222";
  const proposal = { id, snapshot_id: second, status: "static_validated", review_state: "unreviewed", commit_sha: "a".repeat(40),
    patch_sha256: "b".repeat(64), source_stale: true, diff: "--- a/a\n+++ b/a\n", rationale: "Candidate", provider: "test", model: "fixture",
    changed_files: [{ path: "src/a.py" }], evidence: [{ id, path: "src/a.py", start_line: 1, end_line: 2 },
      { id: second, path: "src/a.py", start_line: 3, end_line: 4 }],
    source_coverage: [{ evidence_id: id, path: "src/a.py", start_line: 1, end_line: 2, classification: "BOUNDED_EXCERPT" },
      { evidence_id: second, path: "src/a.py", start_line: 3, end_line: 4, classification: "UNKNOWN_COVERAGE" }],
    static_result: { status: "passed" }, test_result: { status: "VALIDATION_UNAVAILABLE", sandbox_used: false } };
  const html = render(mod.exports.ProposalView, { proposal });
  assert.match(html, /Source snapshot/); assert.match(html, /Candidate patch SHA-256/); assert.match(html, /proposal is stale/);
  assert.match(html, /Bounded excerpt/); assert.match(html, /Source coverage unknown/);
  assert.equal((html.match(/View candidate diff/g) || []).length, 2); assert.match(html, /not a verified fix/);
});

test("copy begins clipboard write in the click gesture and uses freshly verified bytes", async () => {
  const states = [], effects = [], pending = [];
  let cursor = 0, scheduled = [], clipboardCalled = false, clipboardValue;
  const hooks = {
    useState(initial) { const i = cursor++; if (!(i in states)) states[i] = initial;
      return [states[i], value => { states[i] = typeof value === "function" ? value(states[i]) : value; }]; },
    useRef(initial) { const i = cursor++; if (!(i in states)) states[i] = { current: initial }; return states[i]; },
    useEffect(fn, deps) { const i = cursor++, previous = effects[i];
      if (!previous || deps.some((value, index) => value !== previous.deps[index])) {
        previous?.cleanup?.(); effects[i] = { deps }; scheduled.push(() => { effects[i].cleanup = fn(); });
      } }
  };
  class TestClipboardItem { constructor(items) { this.items = items; } }
  const navigator = { clipboard: { write: async items => { clipboardCalled = true; clipboardValue = await items[0].items["text/plain"]; } } };
  const mockedFetch = url => new Promise(resolve => pending.push({ url, resolve }));
  const componentModule = { exports: {} };
  const fakeContext = vm.createContext({ module: componentModule, exports: componentModule.exports, AbortController, TextDecoder, Uint8Array, Blob,
    crypto: webcrypto, ClipboardItem: TestClipboardItem, navigator, fetch: mockedFetch,
    require: name => name === "react" ? hooks : name === "react/jsx-runtime" ? jsxRuntime : (() => { throw new Error(name); })() });
  new vm.Script(code).runInContext(fakeContext);
  const id = "11111111-1111-4111-8111-111111111111", snapshot = "22222222-2222-4222-8222-222222222222", commit = "a".repeat(40);
  const diff = "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new\n";
  const hash = createHash("sha256").update(diff).digest("hex");
  const item = { id, status: "static_validated", snapshot_id: snapshot, commit_sha: commit, review_state: "unreviewed", error_code: null, dispatch_status: "processed" };
  const details = { ...item, diff, rationale: "candidate", provider: "synthetic-test", model: "fixture", changed_files: [], evidence: [],
    static_result: { status: "passed" }, test_result: { status: "VALIDATION_UNAVAILABLE", sandbox_used: false }, patch_sha256: hash, export_available: true };
  const renderPanel = () => { cursor = 0; const tree = componentModule.exports.PatchProposals({ repositoryId: "1", jobId: "job", snapshotId: snapshot, commit });
    const work = scheduled; scheduled = []; work.forEach(fn => { const result = fn(); if (typeof result === "function") {} }); return tree; };
  const find = (element, matches) => { if (!element || typeof element !== "object") return null; if (matches(element)) return element;
    const children = element.props?.children; for (const child of Array.isArray(children) ? children : [children]) { const found = find(child, matches); if (found) return found; } return null; };
  const settle = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
  const ok = value => ({ ok: true, json: async () => value });
  renderPanel(); pending.shift().resolve(ok({ available: true, reason: null, items: [item] })); await settle();
  let tree = renderPanel(); find(tree, element => element.type === componentModule.exports.ProposalChoices).props.onSelect(id);
  renderPanel(); pending.shift().resolve(ok(details)); await settle(); tree = renderPanel();
  find(tree, element => element.type === "button" && element.props.children === "Copy candidate patch").props.onClick();
  assert.equal(clipboardCalled, true, "clipboard write must begin before export fetch resolves");
  const request = pending.shift(); assert.match(request.url, new RegExp(`/export\\?sha256=${hash}$`));
  request.resolve(new Response(diff, { headers: { "X-Patch-SHA256": hash, "X-Source-Commit": commit, "X-Source-Snapshot": snapshot } }));
  for (let i = 0; i < 20 && !clipboardValue; i++) await new Promise(resolve => setTimeout(resolve, 5));
  assert.ok(clipboardValue); assert.equal(await clipboardValue.text(), diff);
});

async function exerciseExportFailure(mode) {
  const states = [], effects = [], pending = [];
  let cursor = 0, scheduled = [], revoked = [], created = 0;
  const hooks = {
    useState(initial) { const i = cursor++; if (!(i in states)) states[i] = initial;
      return [states[i], value => { states[i] = typeof value === "function" ? value(states[i]) : value; }]; },
    useRef(initial) { const i = cursor++; if (!(i in states)) states[i] = { current: initial }; return states[i]; },
    useEffect(fn, deps) { const i = cursor++, previous = effects[i];
      if (!previous || deps.some((value, index) => value !== previous.deps[index])) {
        previous?.cleanup?.(); effects[i] = { deps }; scheduled.push(() => { effects[i].cleanup = fn(); });
      } }
  };
  class TestClipboardItem { constructor(items) { this.items = items; } }
  const navigator = { clipboard: { write: async items => {
    await items[0].items["text/plain"];
    throw new Error("/private/internal/storage/denied");
  } } };
  const urlApi = { createObjectURL() { created++; return "blob:test"; }, revokeObjectURL(url) { revoked.push(url); } };
  const componentModule = { exports: {} };
  const mockedFetch = url => new Promise(resolve => pending.push({ url, resolve }));
  const fakeContext = vm.createContext({ module: componentModule, exports: componentModule.exports, AbortController, TextDecoder, Uint8Array, Blob,
    crypto: webcrypto, ClipboardItem: TestClipboardItem, navigator, fetch: mockedFetch, URL: urlApi,
    document: { createElement() { return { click() { throw new Error("/private/internal/storage/denied"); } }; } },
    setTimeout: fn => fn(), require: name => name === "react" ? hooks : name === "react/jsx-runtime" ? jsxRuntime : (() => { throw new Error(name); })() });
  new vm.Script(code).runInContext(fakeContext);
  const id = "11111111-1111-4111-8111-111111111111", snapshot = "22222222-2222-4222-8222-222222222222", commit = "a".repeat(40);
  const diff = "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new\n";
  const hash = createHash("sha256").update(diff).digest("hex");
  const item = { id, status: "static_validated", snapshot_id: snapshot, commit_sha: commit, review_state: "unreviewed", error_code: null, dispatch_status: "processed" };
  const details = { ...item, diff, rationale: "Fixture", provider: "synthetic", model: "test", evidence: [], changed_files: [],
    static_result: { status: "passed" }, test_result: { status: "VALIDATION_UNAVAILABLE", sandbox_used: false }, patch_sha256: hash, export_available: true };
  const renderPanel = () => { cursor = 0; const tree = componentModule.exports.PatchProposals({ repositoryId: "1", jobId: "job", snapshotId: snapshot, commit });
    const work = scheduled; scheduled = []; work.forEach(fn => fn()); return tree; };
  const find = (element, matches) => {
    if (!element || typeof element !== "object") return null;
    if (matches(element)) return element;
    const children = element.props?.children;
    for (const child of Array.isArray(children) ? children : [children]) { const found = find(child, matches); if (found) return found; }
    return null;
  };
  const settle = async () => { for (let i = 0; i < 5; i++) await Promise.resolve(); };
  renderPanel(); pending.shift().resolve({ ok: true, json: async () => ({ available: true, reason: null, items: [item] }) }); await settle();
  let tree = renderPanel(); find(tree, element => element.type === componentModule.exports.ProposalChoices).props.onSelect(id);
  renderPanel(); pending.shift().resolve({ ok: true, json: async () => details }); await settle(); tree = renderPanel();
  const label = mode === "clipboard_denied" ? "Copy candidate patch" : "Download candidate .patch";
  find(tree, element => element.type === "button" && element.props.children === label).props.onClick();
  const request = pending.shift();
  request.resolve(mode === "fetch_failed" ? new Response("/private/internal/storage/denied", { status: 403 }) :
    new Response(diff, { headers: { "X-Patch-SHA256": hash, "X-Source-Commit": commit, "X-Source-Snapshot": snapshot } }));
  for (let i = 0; i < 50; i++) { await new Promise(resolve => setTimeout(resolve, 5)); tree = renderPanel();
    if (find(tree, element => element.props?.role === "alert")) break; }
  const alert = find(tree, element => element.props?.role === "alert");
  assert.ok(alert, "failure must appear to the user");
  assert.equal(alert.props.children, "Patch export could not be verified. Refresh the proposal and try again.");
  assert.doesNotMatch(String(alert.props.children), /private|internal|storage/);
  return { created, revoked };
}

test("clipboard permission failure is visible without exposing private error details", async () => {
  const result = await exerciseExportFailure("clipboard_denied");
  assert.equal(result.created, 0);
});

test("failed patch download does not create a blob URL", async () => {
  const result = await exerciseExportFailure("fetch_failed");
  assert.equal(result.created, 0); assert.deepEqual(result.revoked, []);
});

test("download click failure revokes the already-created blob URL", async () => {
  const result = await exerciseExportFailure("download_failed");
  assert.equal(result.created, 1); assert.deepEqual(result.revoked, ["blob:test"]);
});
