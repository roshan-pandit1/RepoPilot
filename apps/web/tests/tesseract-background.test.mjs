import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import * as jsxRuntime from "react/jsx-runtime";

function load(file, dependencies = {}, globals = {}) {
  const source = fs.readFileSync(path.resolve(file), "utf8");
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const loaded = { exports: {} };
  vm.runInNewContext(js, { module: loaded, exports: loaded.exports, Float32Array, Math, require: name => dependencies[name], ...globals });
  return loaded.exports;
}
const geometry = load("lib/tesseract-geometry.ts");
const component = load("components/tesseract-background.tsx", { react: React, "react/jsx-runtime": jsxRuntime, "@/lib/tesseract-geometry": geometry });

test("orbital geometry is deterministic and mobile quality is bounded", () => {
  const mobile = geometry.qualityForWidth(390), desktop = geometry.qualityForWidth(1200);
  assert.ok(mobile.strands < desktop.strands);
  assert.equal(mobile.fps, 30);
  assert.ok(desktop.fps <= 30 && desktop.strands <= 100);
  const first = geometry.createStrands(mobile), second = geometry.createStrands(mobile);
  assert.equal(first.length, mobile.strands);
  assert.deepEqual(Array.from(first[0].points), Array.from(second[0].points));
  assert.ok(first.some(strand => strand.dotted));
});

test("server rendering keeps the canvas decorative and hydration-safe", () => {
  const html = renderToStaticMarkup(React.createElement(component.TesseractBackground));
  assert.match(html, /aria-hidden="true"/);
  assert.match(html, /<canvas/);
  assert.doesNotMatch(html, /tabindex/i);
});

test("canvas lifecycle respects reduced motion, visibility, resize and cleanup", () => {
  let effect, scheduled = 0, cancelled = 0;
  let renderedWidth = 373, observerCallback, observed, disconnected = false, draws = 0;
  const transforms = [];
  const handlers = {}, motionHandlers = {};
  const motion = { matches: true, addEventListener: (n, f) => { motionHandlers[n] = f; }, removeEventListener: n => { delete motionHandlers[n]; } };
  const ctx = { setTransform(...args) { transforms.push(args); }, clearRect() { draws++; }, setLineDash() {} };
  const canvas = { width: 0, height: 0, getContext: () => ctx,
    getBoundingClientRect: () => ({ width: renderedWidth, height: 800 }) };
  const window = { innerWidth: 390, innerHeight: 800, devicePixelRatio: 3, matchMedia: () => motion,
    getComputedStyle: () => ({ getPropertyValue: () => "" }),
    addEventListener: (n, f) => { handlers[n] = f; }, removeEventListener: n => { delete handlers[n]; } };
  const document = { hidden: false, addEventListener: (n, f) => { handlers[n] = f; }, removeEventListener: n => { delete handlers[n]; } };
  const deps = { react: { useRef: () => ({ current: canvas }), useEffect: fn => { effect = fn; } }, "react/jsx-runtime": jsxRuntime,
    "@/lib/tesseract-geometry": { qualityForWidth: geometry.qualityForWidth, createStrands: () => [] } };
  class TestResizeObserver {
    constructor(callback) { observerCallback = callback; }
    observe(element) { observed = element; }
    disconnect() { disconnected = true; }
  }
  const bg = load("components/tesseract-background.tsx", deps, { window, document, ResizeObserver: TestResizeObserver,
    requestAnimationFrame: () => ++scheduled, cancelAnimationFrame: () => { cancelled++; } });
  bg.TesseractBackground();
  const cleanup = effect();
  assert.equal(canvas.width, 560);
  assert.equal(canvas.height, 1200);
  assert.equal(transforms[0][0], 560 / 373);
  assert.equal(observed, canvas);
  assert.equal(scheduled, 0);
  motion.matches = false; motionHandlers.change();
  assert.equal(scheduled, 1);
  document.hidden = true; handlers.visibilitychange();
  assert.equal(cancelled, 1);
  const drawsBeforeHiddenResize = draws;
  renderedWidth = 380; observerCallback();
  assert.equal(draws, drawsBeforeHiddenResize);
  document.hidden = false; handlers.visibilitychange();
  assert.equal(scheduled, 2);
  window.innerWidth = 500; renderedWidth = 483; observerCallback();
  assert.equal(canvas.width, 725);
  cleanup();
  assert.equal(cancelled, 2);
  assert.equal(disconnected, true);
  assert.equal(Object.keys(handlers).length, 0);
  assert.equal(Object.keys(motionHandlers).length, 0);
});

test("canvas uses the shared silver and amethyst palette", () => {
  let effect;
  const strokes = [];
  const ctx = { setTransform() {}, clearRect() {}, setLineDash() {}, beginPath() {}, moveTo() {}, lineTo() {},
    stroke() { strokes.push([this.strokeStyle, this.shadowColor]); } };
  const canvas = { width: 0, height: 0, getContext: () => ctx,
    getBoundingClientRect: () => ({ width: 390, height: 800 }) };
  const motion = { matches: true, addEventListener() {}, removeEventListener() {} };
  const palette = { "--rp-orbit-rgb": "213, 215, 232", "--rp-glow-rgb": "171, 146, 255" };
  const window = { innerWidth: 390, innerHeight: 800, devicePixelRatio: 1, matchMedia: () => motion,
    getComputedStyle: () => ({ getPropertyValue: name => palette[name] }), addEventListener() {}, removeEventListener() {} };
  const document = { hidden: false, addEventListener() {}, removeEventListener() {} };
  const deps = { react: { useRef: () => ({ current: canvas }), useEffect: fn => { effect = fn; } }, "react/jsx-runtime": jsxRuntime,
    "@/lib/tesseract-geometry": { qualityForWidth: geometry.qualityForWidth, createStrands: () => [{ points: new Float32Array([0, 0, 0, 1, 1, 0]), family: 1, dotted: false, brightness: 0.2 }] } };
  const bg = load("components/tesseract-background.tsx", deps, { window, document });
  bg.TesseractBackground();
  const cleanup = effect();
  assert.match(strokes[0][0], /^rgba\(213, 215, 232,/);
  assert.equal(strokes[0][1], "rgba(171, 146, 255,0.22)");
  cleanup();
});

test("unavailable canvas context leaves the CSS fallback in place", () => {
  let effect;
  const bg = load("components/tesseract-background.tsx", {
    react: { useRef: () => ({ current: { getContext: () => null } }), useEffect: fn => { effect = fn; } },
    "react/jsx-runtime": jsxRuntime, "@/lib/tesseract-geometry": geometry
  });
  bg.TesseractBackground();
  assert.equal(effect(), undefined);
});
