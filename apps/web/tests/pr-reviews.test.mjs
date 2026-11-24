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
const source = fs.readFileSync(path.join(root, "components/pr-reviews.tsx"), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
const mod = { exports: {} };
new vm.Script(code).runInContext(vm.createContext({ module: mod, exports: mod.exports,
  require: name => name === "react" ? React : name === "react/jsx-runtime" ? jsxRuntime : (() => { throw new Error(name); })() }));
const fixture = { id: "11111111-1111-4111-8111-111111111111", status: "completed", number: 12, title: "Review <script>",
  base_sha: "a".repeat(40), head_sha: "b".repeat(40), coverage: "partial", repository_id: "123", limitations: ["One file omitted"],
  files: [{ path: "src/a.py", status: "modified", additions: 1, deletions: 1, coverage: "complete", patch: "+<script>" }],
  findings: [{ id: "22222222-2222-4222-8222-222222222222", rule_id: "rule1", category: "SECURITY", severity: "HIGH",
    confidence: "HIGH", path: "src/a.py", start_line: 2, end_line: 2, explanation: "Unsafe <script>", recommendation: "Review safely" }] };

test("review detail renders evidence and honest limitations without HTML injection", () => {
  const html = renderToStaticMarkup(React.createElement(mod.exports.PRReviewDetail, { review: fixture, onFeedback: () => {}, busy: false }));
  assert.match(html, /One file omitted/); assert.match(html, /Rule rule1/); assert.match(html, /src\/a.py:2/);
  assert.match(html, /&lt;script&gt;/); assert.doesNotMatch(html, /<script>/); assert.match(html, /No repository code/);
});
test("review details reject cross-repository payloads and malformed identities", () => {
  assert.equal(mod.exports.parsePRDetail(fixture, "123").id, fixture.id);
  assert.throws(() => mod.exports.parsePRDetail(fixture, "124"));
  assert.throws(() => mod.exports.parsePRDetail({ ...fixture, head_sha: "fake" }, "123"));
});
test("queued reviews allow pending provenance without inventing a head", () => {
  const pending = mod.exports.parsePRSummary({ ...fixture, title: null, base_sha: null, head_sha: null, coverage: null, status: "queued" });
  assert.equal(pending.head_sha, null);
});
test("no findings does not claim a clean or fully secure review", () => {
  const html = renderToStaticMarkup(React.createElement(mod.exports.PRReviewDetail, { review: { ...fixture, findings: [] }, onFeedback: () => {}, busy: false }));
  assert.match(html, /not a complete security assessment/); assert.doesNotMatch(html, /No vulnerabilities/);
});

test("an access denial invalidates a previously pending review response", async () => {
  const guard = mod.exports.createReviewAccessGuard();
  let resolve;
  const deferred = new Promise(r => { resolve = r; });
  const epoch = guard.snapshot();
  let displayed = false;
  const pending = deferred.then(() => { if (guard.valid(epoch)) displayed = true; });
  guard.revoke();
  resolve();
  await pending;
  assert.equal(displayed, false);
  assert.equal(guard.valid(guard.snapshot()), true);
});

for (const deniedStatus of [403, 404]) test(`authorization denial ${deniedStatus} cannot be undone by an older detail response`, async () => {
  const states = [], effects = [], pending = [], timers = [];
  let cursor = 0, scheduled = [];
  const same = (a, b) => a && b && a.length === b.length && a.every((v, i) => v === b[i]);
  const hooks = {
    useState(initial) { const i = cursor++; if (!(i in states)) states[i] = initial;
      return [states[i], value => { states[i] = typeof value === "function" ? value(states[i]) : value; }]; },
    useRef(initial) { const i = cursor++; if (!(i in states)) states[i] = { current: initial }; return states[i]; },
    useCallback(fn, deps) { const i = cursor++; if (!states[i] || !same(states[i].deps, deps)) states[i] = { fn, deps }; return states[i].fn; },
    useEffect(fn, deps) { const i = cursor++, previous = effects[i];
      if (!previous || !same(previous.deps, deps)) {
        previous?.cleanup?.(); effects[i] = { deps }; scheduled.push(() => { effects[i].cleanup = fn(); });
      } }
  };
  const component = { exports: {} };
  const fake = vm.createContext({ module: component, exports: component.exports, AbortController,
    fetch: url => new Promise(resolve => pending.push({ url, resolve })),
    setInterval: fn => { timers.push(fn); return timers.length; }, clearInterval() {},
    require: name => name === "react" ? hooks : name === "react/jsx-runtime" ? jsxRuntime : (() => { throw new Error(name); })() });
  new vm.Script(code).runInContext(fake);
  const renderPanel = () => { cursor = 0; const tree = component.exports.PRReviews({ repositoryId: "123", repositoryName: "example/repo" });
    const work = scheduled; scheduled = []; work.forEach(fn => fn()); return tree; };
  const find = (node, matches) => {
    if (!node || typeof node !== "object") return null;
    if (Array.isArray(node)) { for (const child of node) { const result = find(child, matches); if (result) return result; } return null; }
    if (matches(node)) return node;
    const children = node.props?.children;
    for (const child of Array.isArray(children) ? children : [children]) { const result = find(child, matches); if (result) return result; }
    return null;
  };
  const settle = async () => { for (let i = 0; i < 5; i++) await Promise.resolve(); };
  const ok = value => ({ ok: true, status: 200, json: async () => value });
  renderPanel(); pending.shift().resolve(ok({ items: [fixture] })); await settle();
  let tree = renderPanel();
  find(tree, node => node.type === "button" && Array.isArray(node.props.children) && node.props.children.includes(fixture.title)).props.onClick();
  renderPanel();
  const detail = pending.shift();
  timers[0]();
  const listing = pending.shift();
  listing.resolve({ ok: false, status: deniedStatus }); await settle();
  detail.resolve(ok(fixture)); await settle();
  tree = renderPanel();
  assert.equal(find(tree, node => node.type === component.exports.PRReviewDetail), null);
  assert.ok(find(tree, node => node.type === "p" && node.props.role === "alert"));
});


test("finding source identity is shown only when bound to the review head and line", () => {
  const evidence = { commit_sha: "b".repeat(40), file_sha256: "c".repeat(64), git_blob_sha1: "d".repeat(40), line: 2, changed_line: true };
  const review = { ...fixture, findings: [{ ...fixture.findings[0], evidence }] };
  const render = value => renderToStaticMarkup(React.createElement(mod.exports.PRReviewDetail, { review: value, onFeedback: () => {}, busy: false }));
  assert.match(render(review), /Source SHA-256/);
  assert.match(render(review), /c{64}/);
  assert.doesNotMatch(render({ ...review, head_sha: "a".repeat(40) }), /Source SHA-256/);
});


test("retry and missing diff counts are presented truthfully", () => {
  const review = { ...fixture, status: "queued", error_code: "github_temporarily_unavailable",
    files: [{ ...fixture.files[0], additions: null, deletions: null, coverage: "partial" }] };
  assert.equal(mod.exports.parsePRDetail(review, "123").id, fixture.id);
  const html = renderToStaticMarkup(React.createElement(mod.exports.PRReviewDetail, { review, onFeedback: () => {}, busy: false }));
  assert.match(html, /will retry automatically/);
  assert.match(html, /unknown/);
});


test("scheduled rate-limit retries show the persisted eligibility time", () => {
  const review = { ...fixture, status: "queued", error_code: "github_rate_limited", next_retry_at: "2026-01-01T00:02:00Z" };
  assert.equal(mod.exports.parsePRDetail(review, "123").next_retry_at, review.next_retry_at);
  const html = renderToStaticMarkup(React.createElement(mod.exports.PRReviewDetail, { review, onFeedback: () => {}, busy: false }));
  assert.match(html, /eligible to retry after/);
  assert.match(html, /2026-01-01T00:02:00Z/);
  assert.throws(() => mod.exports.parsePRDetail({ ...review, next_retry_at: "invalid" }, "123"));
});


test("pinned head repository identity is rendered as text", () => {
  const review = { ...fixture, head_repository_id: "903", head_repository_name: "contributor/public" };
  assert.equal(mod.exports.parsePRDetail(review, "123").head_repository_id, "903");
  const html = renderToStaticMarkup(React.createElement(mod.exports.PRReviewDetail, { review, onFeedback: () => {}, busy: false }));
  assert.match(html, /Head repository: contributor\/public/);
  assert.throws(() => mod.exports.parsePRDetail({ ...review, head_repository_id: "invalid" }, "123"));
});


test("unavailable TypeScript analysis is not presented as a clean result", () => {
  const review = { ...fixture, findings: [], limitations: ["typescript_analysis_unavailable"],
    files: [{ path: "src/a.ts", status: "modified", additions: 1, deletions: 1,
              coverage: "partial", reason: "typescript_analysis_unavailable" }] };
  const html = renderToStaticMarkup(React.createElement(mod.exports.PRReviewDetail, { review, onFeedback: () => {}, busy: false }));
  assert.match(html, /TypeScript analysis was unavailable/);
  assert.match(html, /no conclusion can be drawn/);
  assert.match(html, /not a complete security assessment/);
});


test("review summary counts files without implying complete security coverage", () => {
  const html = renderToStaticMarkup(React.createElement(mod.exports.PRReviewDetail, { review: fixture, onFeedback: () => {}, busy: false }));
  assert.match(html, /Recorded files checked by enabled rules: 1/);
  assert.match(html, /Recorded files not fully checked: 0/);
  assert.match(html, /One file omitted/);
});
