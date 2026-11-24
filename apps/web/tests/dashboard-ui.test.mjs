import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";
import * as jsxRuntime from "react/jsx-runtime";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const source = fs.readFileSync(path.join(root, "components/dashboard.tsx"), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2017, jsx: ts.JsxEmit.ReactJSX } }).outputText;

async function exercise({ status, demo = false, overrides = {} }) {
  const effects = [], timers = [], calls = [], updates = [];
  let index = 0;
  const hooks = { useState: initial => { const i = index++; return [Object.hasOwn(overrides, i) ? overrides[i] : initial, value => updates.push([i, value])]; },
    useEffect: effect => effects.push(effect), useCallback: fn => fn };
  const names = { "./top-navigation": "TopNavigation", "./issue-list": "IssueList", "./github-account": "GitHubAccount",
    "./pr-reviews": "PRReviews", "./code-intelligence": "CodeIntelligence", "./investigation-workspace": "InvestigationWorkspace", "./repository-selector": "RepositorySelector" };
  const modules = Object.fromEntries(Object.entries(names).map(([key, value]) => [key, { [value]: () => null }]));
  modules["./ui"] = { Button: () => null, Icon: () => null, Skeleton: () => null };
  const loaded = { exports: {} };
  vm.runInNewContext(compiled, { module: loaded, exports: loaded.exports, AbortController, Date,
    fetch: async url => { calls.push(url); return { ok: url === "/api/health" || status === 200, status: url === "/api/health" ? 200 : status,
      json: async () => url === "/api/health" ? { ready: true } : status === 200 ? [] : { detail: status === 401 ? "Authentication required" : "API unavailable" } }; },
    setInterval: (fn, delay) => { timers.push({ fn, delay }); return timers.length; }, clearInterval() {},
    require: name => name === "react" ? hooks : name === "react/jsx-runtime" ? jsxRuntime : modules[name] ?? (() => { throw new Error(name); })() });
  const tree = loaded.exports.Dashboard({ demo });
  const cleanups = effects.map(effect => effect());
  await new Promise(resolve => setImmediate(resolve));
  return { timers, calls, updates, cleanups, tree, modules };
}

function findElement(node, type) {
  if (Array.isArray(node)) return node.map(child => findElement(child, type)).find(Boolean);
  if (!node || typeof node !== "object") return undefined;
  if (node.type === type) return node;
  return findElement(node.props?.children, type);
}

test("normal refresh remains 30 seconds and 401 selects onboarding without extra requests", async () => {
  const result = await exercise({ status: 401 });
  assert.deepEqual(result.calls, ["/api/health", "/api/dashboard"]);
  assert.deepEqual(result.timers.map(item => item.delay), [30000]);
  assert.ok(result.updates.some(([index, value]) => index === 4 && value === true));
  result.cleanups.forEach(cleanup => cleanup?.());
});

test("real service errors remain errors and demo polling remains five seconds", async () => {
  const result = await exercise({ status: 503, demo: true });
  assert.deepEqual(result.calls, ["/api/health", "/api/dashboard"]);
  assert.deepEqual(result.timers.map(item => item.delay), [5000]);
  assert.ok(result.updates.some(([index, value]) => index === 4 && value === false));
  assert.ok(result.updates.some(([index, value]) => index === 3 && value === "API unavailable"));
  result.cleanups.forEach(cleanup => cleanup?.());
});

test("signed-out presentation does not expose a previously selected repository", async () => {
  const result = await exercise({ status: 401, overrides: { 0: [{ id: "42", full_name: "old/repository", enabled: true }], 1: "42", 4: true } });
  const selector = findElement(result.tree, result.modules["./repository-selector"].RepositorySelector);
  assert.ok(selector);
  assert.equal(selector.props.repositories.length, 0);
  assert.equal(findElement(result.tree, result.modules["./code-intelligence"].CodeIntelligence), undefined);
  result.cleanups.forEach(cleanup => cleanup?.());
});
