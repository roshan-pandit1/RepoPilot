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

function loadComponent(file, dependencies) {
  const source = fs.readFileSync(path.join(root, file), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const loaded = { exports: {} };
  const context = vm.createContext({
    module: loaded, exports: loaded.exports,
    require: (name) => {
      if (name === "react/jsx-runtime") return jsxRuntime;
      if (name in dependencies) return dependencies[name];
      throw new Error(`Unexpected import: ${name}`);
    },
  });
  new vm.Script(compiled, { filename: file }).runInContext(context);
  return loaded.exports;
}

const badge = loadComponent("components/status-badge.tsx", {});
const ui = loadComponent("components/ui.tsx", {});
const { IssueList } = loadComponent("components/issue-list.tsx", { "./status-badge": badge, "./ui": ui });
const defaults = { error: "", loading: false, page: null, hasRepositories: true, onRetry: () => {} };
function render(props) { return renderToStaticMarkup(React.createElement(IssueList, { ...defaults, ...props })); }

test("loading state is announced while data is being fetched", () => {
  const html = render({ loading: true });
  assert.match(html, /role="status"/);
  assert.match(html, /Loading verified issues/);
  assert.doesNotMatch(html, /Ready for your first issue/);
});

test("retry shows loading instead of a stale error", () => {
  const html = render({ loading: true, error: "API unavailable" });
  assert.match(html, /role="status"/);
  assert.doesNotMatch(html, /role="alert"/);
});

test("API errors and unauthorized responses display an actionable error", () => {
  for (const error of ["API unavailable", "Authentication required"]) {
    const html = render({ error });
    assert.match(html, /role="alert"/);
    assert.ok(html.includes(error));
    assert.match(html, /Try again/);
    assert.doesNotMatch(html, /Ready for your first issue/);
  }
});

test("a 401 state presents GitHub onboarding without presenting it as a failure", () => {
  const html = render({ error: "Authentication required", unauthenticated: true, hasRepositories: false });
  assert.match(html, /Connect GitHub to see your issues/);
  assert.match(html, /action="\/api\/auth\/start"/);
  assert.match(html, /Sign in with GitHub/);
  assert.match(html, /Connect a repository/);
  assert.match(html, /Issues appear here/);
  assert.doesNotMatch(html, /Authentication required|role="alert"/);
});

test("a genuine error keeps details collapsed and offers retry", () => {
  const html = render({ error: "API unavailable" });
  assert.match(html, /<details class="error-details"><summary>Show details/);
  assert.match(html, /Try again/);
  assert.match(html, /API unavailable/);
});

test("empty issues and no authorized repositories have distinct guidance", () => {
  assert.match(render({ page: { items: [], ingestion: {} } }), /Ready for your first issue/);
  assert.match(render({ hasRepositories: false }), /No authorized repositories yet/);
});

test("successful API data renders issue fields as text", () => {
  const html = render({ repositoryName: "alice/project", page: { items: [{ id: "42", number: 7, title: "<untrusted issue>", labels: ["<label>"], state: "open", updated_at: "2026-01-01T00:00:00Z", ingestion_status: "processed" }], ingestion: {} } });
  assert.match(html, /&lt;untrusted issue&gt;/);
  assert.match(html, /&lt;label&gt;/);
  assert.match(html, /alice\/project/);
  assert.match(html, /#7/);
  assert.match(html, /processed/);
  assert.doesNotMatch(html, /<untrusted issue>/);
});

test("malformed optional labels do not prevent issue rendering", () => {
  const html = render({ page: { items: [{ id: "42", number: 7, title: "Example", labels: "unexpected",
    state: "open", updated_at: "2026-01-01T00:00:00Z", ingestion_status: "processed" }], ingestion: {} } });
  assert.match(html, /Example/);
  assert.doesNotMatch(html, /issue-labels/);
});

test("connected users can select a listed issue for investigation", () => {
  const html = render({ onSelectIssue: () => {}, page: { items: [{ id: "42", number: 7, title: "Example",
    state: "open", updated_at: "2026-01-01T00:00:00Z", ingestion_status: "processed" }], ingestion: {} } });
  assert.match(html, /aria-label="Investigate issue #7"/);
});
