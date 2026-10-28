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
const { IssueList } = loadComponent("components/issue-list.tsx", { "./status-badge": badge });
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

test("empty issues and no authorized repositories have distinct guidance", () => {
  assert.match(render({ page: { items: [], ingestion: {} } }), /Ready for your first issue/);
  assert.match(render({ hasRepositories: false }), /No authorized repositories yet/);
});

test("successful API data renders issue fields as text", () => {
  const html = render({ page: { items: [{ id: "42", number: 7, title: "<untrusted issue>", state: "open", updated_at: "2026-01-01T00:00:00Z", ingestion_status: "processed" }], ingestion: {} } });
  assert.match(html, /&lt;untrusted issue&gt;/);
  assert.match(html, /#7/);
  assert.match(html, /processed/);
  assert.doesNotMatch(html, /<untrusted issue>/);
});
