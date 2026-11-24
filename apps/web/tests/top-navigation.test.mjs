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
function load(file, dependencies = {}, globals = {}) {
  const source = fs.readFileSync(path.join(root, file), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const loaded = { exports: {} };
  vm.runInNewContext(code, { module: loaded, exports: loaded.exports, ...globals,
    require: name => name in dependencies ? dependencies[name] : name === "react" ? React :
      name === "react/jsx-runtime" ? jsxRuntime : (() => { throw new Error(name); })() });
  return loaded.exports;
}
const status = load("components/status-badge.tsx");
const ui = load("components/ui.tsx");
const Link = ({ children, ...props }) => React.createElement("a", props, children);
const nav = load("components/top-navigation.tsx", { "next/link": { default: Link }, "./status-badge": status });
const account = load("components/github-account.tsx", { "react-dom": { createPortal() { throw new Error("Unexpected portal"); } }, "./ui": ui });
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));

test("navbar renders the existing destinations once with accessible mobile controls", () => {
  const html = render(nav.TopNavigation, { demo: false, ready: true, accountRef() {} });
  assert.match(html, /aria-label="Main navigation"/);
  assert.match(html, /aria-expanded="false"/);
  assert.match(html, /aria-controls="primary-navigation"/);
  assert.match(html, /API &amp; storage ready/);
  for (const href of ["#inbox", "#github-account", "#code-search"]) {
    assert.equal(html.split(`href="${href}"`).length - 1, 1);
  }
  assert.equal((html.match(/aria-current="page"/g) || []).length, 1);
  assert.doesNotMatch(html, /Sprint 01|Reports/);
});

test("system status is keyboard-focusable and reflects the actual health state", () => {
  for (const [ready, label, tone] of [[true, "API &amp; storage ready", "good"], [false, "System unavailable", "danger"], [null, "Checking system", "warn"]]) {
    const html = render(nav.TopNavigation, { demo: false, ready, accountRef() {} });
    assert.ok(html.includes(label));
    assert.match(html, new RegExp(`data-tone="${tone}"`));
    assert.match(html, /role="status" tabindex="0"/);
    assert.match(html, /data-tooltip=/);
  }
});

test("section links, active state and demo destinations match the existing page", () => {
  assert.equal(nav.sectionForHash("#github-account"), "repositories");
  assert.equal(nav.sectionForHash("#repositories"), "repositories");
  assert.equal(nav.sectionForHash("#code-search"), "code-search");
  assert.equal(nav.sectionForHash(""), "inbox");
  const html = render(nav.NavigationLinks, { active: "code-search", demo: false, onNavigate() {} });
  assert.match(html, /href="#code-search"[^>]*aria-current="page"/);
  const demo = render(nav.NavigationLinks, { active: "repositories", demo: true, onNavigate() {} });
  assert.match(demo, /href="#repositories"[^>]*aria-current="page"/);
  assert.doesNotMatch(demo, /Code Search/);
});

test("the active section follows markers above the header and the visible end of the page", () => {
  const markers = [
    { section: "inbox", top: -350 },
    { section: "repositories", top: -50 },
    { section: "code-search", top: 450 },
  ];
  assert.equal(nav.sectionForViewport([], 104, 800, false), "inbox");
  assert.equal(nav.sectionForViewport(markers, 104, 800, false), "repositories");
  assert.equal(nav.sectionForViewport(markers, 104, 800, true), "code-search");
  assert.equal(nav.sectionForViewport([...markers.slice(0, 2), { section: "code-search", top: 900 }], 104, 800, true), "repositories");
  assert.equal(nav.sectionForViewport([...markers.slice(0, 2), { section: "code-search", top: 100 }], 104, 800, false), "code-search");
});

test("scroll, resize and dynamic layout changes update navigation and clean up listeners", () => {
  const effects = [], updates = [], handlers = {}, frames = new Map();
  let nextFrame = 0, disconnected = false, observerCallback;
  const positions = { inbox: 180, "github-account": 350, repositories: 700, "code-search": 1400 };
  const visible = { inbox: true, "github-account": true, repositories: true, "code-search": true };
  const main = {};
  const window = {
    location: { hash: "" }, innerHeight: 800, scrollY: 0,
    addEventListener(name, callback) { handlers[name] = callback; },
    removeEventListener(name) { delete handlers[name]; },
    requestAnimationFrame(callback) { const id = ++nextFrame; frames.set(id, callback); return id; },
    cancelAnimationFrame(id) { frames.delete(id); },
  };
  const document = {
    scrollingElement: { scrollHeight: 2500 }, documentElement: { scrollHeight: 2500 },
    getElementById(id) { return { getBoundingClientRect() { return { top: positions[id] - window.scrollY, width: 100, height: visible[id] ? 100 : 0 }; } }; },
    querySelector(selector) { return selector === ".topbar" ? { getBoundingClientRect: () => ({ bottom: 72 }) } : selector === "main" ? main : null; },
  };
  class TestResizeObserver {
    constructor(callback) { observerCallback = callback; }
    observe(element) { assert.equal(element, main); }
    disconnect() { disconnected = true; }
  }
  const hooks = { useState: initial => [initial, value => updates.push(value)], useReducer: () => [false, () => {}],
    useRef: initial => ({ current: initial }), useEffect: effect => effects.push(effect) };
  const component = load("components/top-navigation.tsx", { react: hooks, "next/link": { default: Link }, "./status-badge": status },
    { window, document, ResizeObserver: TestResizeObserver, queueMicrotask: callback => callback() });
  component.TopNavigation({ demo: false, ready: true, accountRef() {} });
  const cleanup = effects[0]();
  const flush = () => { const batch = [...frames.values()]; frames.clear(); batch.forEach(callback => callback()); };
  flush();
  assert.equal(updates.at(-1), "inbox");
  window.scrollY = 300;
  handlers.scroll(); handlers.scroll();
  assert.equal(frames.size, 1);
  flush();
  assert.equal(updates.at(-1), "repositories");
  visible["github-account"] = false; observerCallback(); flush();
  assert.equal(updates.at(-1), "inbox");
  window.scrollY = 700; handlers.scroll(); flush();
  assert.equal(updates.at(-1), "repositories");
  window.scrollY = 1300; handlers.scroll(); flush();
  assert.equal(updates.at(-1), "code-search");
  visible["code-search"] = false; observerCallback(); flush();
  assert.equal(updates.at(-1), "repositories");
  window.scrollY = 0; handlers.resize(); flush();
  assert.equal(updates.at(-1), "inbox");
  handlers.scroll();
  cleanup();
  assert.equal(frames.size, 0);
  assert.equal(Object.keys(handlers).length, 0);
  assert.equal(disconnected, true);
});

test("mobile menu state toggles and closes for navigation or Escape", () => {
  assert.equal(nav.mobileMenuReducer(false, "toggle"), true);
  assert.equal(nav.mobileMenuReducer(true, "toggle"), false);
  assert.equal(nav.mobileMenuReducer(true, "close"), false);
});

test("repository navigation uses the visible section when account controls are absent", () => {
  const calls = [], updates = [], effects = [];
  const hooks = { useState: initial => [initial, value => updates.push(value)], useReducer: () => [false, () => {}],
    useRef: initial => ({ current: initial }), useEffect: effect => effects.push(effect) };
  const document = { querySelector: () => null, getElementById: id => ({ scrollIntoView: options => calls.push([id, options.behavior]) }) };
  const window = { matchMedia: () => ({ matches: true }) };
  const component = load("components/top-navigation.tsx", { react: hooks, "next/link": { default: Link }, "./status-badge": status },
    { window, document });
  const tree = component.TopNavigation({ demo: false, ready: true, accountRef() {} });
  const links = tree.props.children.props.children[1].props.children;
  links.props.onNavigate("repositories");
  assert.equal(updates.at(-1), "repositories");
  assert.deepEqual(calls, [["repositories", "auto"]]);
});

test("navbar account actions preserve the GitHub sign-in and sign-out controls", () => {
  const signedOut = render(account.AccountActions, { checking: false, identity: null, onLogout() {} });
  assert.match(signedOut, /action="\/api\/auth\/start"/);
  assert.match(signedOut, /aria-label="Sign in with GitHub"/);
  const signedIn = render(account.AccountActions, { checking: false, identity: { demo: false, user: { login: "alice" } }, onLogout() {} });
  assert.match(signedIn, /alice/);
  assert.match(signedIn, /Sign out/);
  assert.doesNotMatch(signedIn, /\/api\/auth\/start/);
});

test("account session check is shared across an effect replay", async () => {
  const effects = [], updates = [], calls = [];
  let resolveRequest, stateIndex = 0;
  const response = new Promise(resolve => { resolveRequest = resolve; });
  const hooks = { useState: initial => { const index = stateIndex++; return [initial, value => updates.push([index, value])]; },
    useRef: initial => ({ current: initial }), useEffect: effect => { effects.push(effect); } };
  const componentModule = load("components/github-account.tsx", { react: hooks, "react-dom": { createPortal() {} }, "./ui": ui },
    { window: { location: { search: "" } }, URLSearchParams, queueMicrotask,
      fetch: (url, options) => { calls.push({ url, options }); return response; } });
  componentModule.GitHubAccount({ onConnected() {}, connectedIds: [], actionTarget: null });
  const cleanup = effects[0]();
  cleanup();
  const cleanupReplay = effects[0]();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/auth/me");
  assert.equal(calls[0].options.cache, "no-store");
  resolveRequest({ ok: true, json: async () => ({ user: { login: "alice" }, demo: false }) });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(updates.filter(([index]) => index === 0).length, 1);
  assert.equal(updates.filter(([index]) => index === 1).length, 1);
  cleanupReplay();
});

test("an unavailable session check leaves the account signed out", async () => {
  const effects = [], updates = [];
  let stateIndex = 0;
  const hooks = { useState: initial => { const index = stateIndex++; return [initial, value => updates.push([index, value])]; },
    useRef: initial => ({ current: initial }), useEffect: effect => { effects.push(effect); } };
  const componentModule = load("components/github-account.tsx", { react: hooks, "react-dom": { createPortal() {} }, "./ui": ui },
    { window: { location: { search: "" } }, URLSearchParams, queueMicrotask,
      fetch: async () => ({ ok: false }) });
  componentModule.GitHubAccount({ onConnected() {}, connectedIds: [], actionTarget: null });
  const cleanup = effects[0]();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(updates.some(([index]) => index === 0), false);
  assert.ok(updates.some(([index, value]) => index === 1 && value === false));
  cleanup();
});
