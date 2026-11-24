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
function load(file, dependencies = {}) {
  const source = fs.readFileSync(path.join(root, file), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const loaded = { exports: {} };
  vm.runInNewContext(code, { module: loaded, exports: loaded.exports,
    require: name => name in dependencies ? dependencies[name] : name === "react" ? React :
      name === "react/jsx-runtime" ? jsxRuntime : (() => { throw new Error(name); })() });
  return loaded.exports;
}
const ui = load("components/ui.tsx");
const selector = load("components/repository-selector.tsx", { "./ui": ui });
const repos = [{ id: "1", full_name: "alice/alpha", enabled: true }, { id: "2", full_name: "bob/beta", enabled: true }];

test("repository selector uses the existing selected identity and an accessible combobox", () => {
  const html = renderToStaticMarkup(React.createElement(selector.RepositorySelector, { repositories: repos, selected: "1", onSelect() {} }));
  assert.match(html, /role="combobox"/);
  assert.match(html, /aria-expanded="false"/);
  assert.match(html, /Select repository/);
  assert.match(html, /value="alice\/alpha"/);
  const disabled = renderToStaticMarkup(React.createElement(selector.RepositorySelector, { repositories: [], selected: "", onSelect() {} }));
  assert.match(disabled, /disabled/);
  assert.match(disabled, /No repositories yet/);
});

test("repository filtering and arrow navigation are bounded and case insensitive", () => {
  assert.deepEqual(Array.from(selector.filterRepositories(repos, " BETA "), item => item.id), ["2"]);
  assert.equal(selector.nextRepositoryIndex(-1, 2, 1), 0);
  assert.equal(selector.nextRepositoryIndex(0, 2, -1), 1);
  assert.equal(selector.nextRepositoryIndex(1, 2, 1), 0);
  assert.equal(selector.nextRepositoryIndex(-1, 0, 1), -1);
});

test("typing, arrow selection, enter and escape retain native keyboard behavior", () => {
  const state = [false, "", -1], chosen = [];
  let cursor = 0;
  const hooks = {
    useState(initial) { const index = cursor++; if (state[index] === undefined) state[index] = initial;
      return [state[index], value => { state[index] = typeof value === "function" ? value(state[index]) : value; }]; },
    useRef() { return { current: { focus() {} } }; },
    useId() { return "repository-options"; },
  };
  const component = load("components/repository-selector.tsx", { react: hooks, "./ui": ui });
  function render() { cursor = 0; return component.RepositorySelector({ repositories: repos, selected: "1", onSelect: id => chosen.push(id) }); }
  function field(tree) { return tree.props.children[0].props.children[2]; }
  let tree = render();
  field(tree).props.onFocus();
  tree = render();
  field(tree).props.onChange({ target: { value: "beta" } });
  tree = render();
  assert.equal(field(tree).props["aria-expanded"], true);
  let prevented = 0;
  field(tree).props.onKeyDown({ key: "ArrowDown", preventDefault() { prevented++; } });
  tree = render();
  assert.match(field(tree).props["aria-activedescendant"], /repository-options-0/);
  field(tree).props.onKeyDown({ key: "Enter", preventDefault() { prevented++; } });
  assert.deepEqual(chosen, ["2"]);
  tree = render();
  field(tree).props.onFocus();
  tree = render();
  field(tree).props.onKeyDown({ key: "Escape", preventDefault() { prevented++; } });
  tree = render();
  assert.equal(field(tree).props["aria-expanded"], false);
  assert.equal(prevented, 3);
});
