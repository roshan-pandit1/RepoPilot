import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const css = fs.readFileSync(path.join(root, "app/globals.css"), "utf8");
function token(name) {
  const match = css.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, "i"));
  assert.ok(match, `Missing color token ${name}`);
  return match[1];
}
function rgb(hex) { return [1, 3, 5].map(index => parseInt(hex.slice(index, index + 2), 16)); }
function luminance(color) {
  const values = rgb(color).map(value => value / 255).map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2];
}
function contrast(a, b) { const values = [luminance(a), luminance(b)].sort((x, y) => y - x); return (values[0] + 0.05) / (values[1] + 0.05); }
function mix(foreground, background, alpha) {
  const fg = rgb(foreground), bg = rgb(background);
  return "#" + fg.map((value, index) => Math.round(value * alpha + bg[index] * (1 - alpha)).toString(16).padStart(2, "0")).join("");
}

test("text and semantic palette tokens meet AA against each solid surface", () => {
  for (const foreground of ["rp-heading", "rp-body", "rp-muted", "rp-success", "rp-warning", "rp-danger", "rp-info"]) {
    for (const background of ["rp-background", "rp-surface-1", "rp-surface-2", "rp-surface-3"]) {
      assert.ok(contrast(token(foreground), token(background)) >= 4.5, `${foreground} on ${background}`);
    }
  }
});

test("white text remains AA on the darkened primary gradient endpoints", () => {
  for (const color of ["rp-indigo", "rp-violet"]) {
    for (const overlay of [0.2, 0.12]) {
      assert.ok(contrast("#ffffff", mix("#110e36", token(color), overlay)) >= 4.5, `${color} overlay ${overlay}`);
    }
  }
});

test("the shared visual system includes reduced motion and no sub-12px text", () => {
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /prefers-contrast:\s*more/);
  assert.doesNotMatch(css, /font-size:\s*(?:[0-9]|1[01])px\b/);
  for (const tokenName of ["rp-radius-sm", "rp-radius-md", "rp-radius-lg", "rp-radius-xl", "rp-space", "rp-shadow-glow", "rp-fast", "rp-normal", "rp-slow"]) {
    assert.match(css, new RegExp(`--${tokenName}:`));
  }
});
