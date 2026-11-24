"use strict";
// Trusted parse-only runner. Source is data; never import it or load its configuration.
const fs = require("node:fs");
const crypto = require("node:crypto");
const ts = require("./typescript.js");
try {
  const input = fs.readFileSync(0);
  if (input.length > 220000) throw Error("input_limit");
  const req = JSON.parse(input.toString("utf8"));
  if (req.version !== 1 || typeof req.path !== "string" || typeof req.source !== "string" ||
      !/\.(ts|tsx)$/.test(req.path)) throw Error("invalid_input");
  const digest = crypto.createHash("sha256").update(req.source, "utf8").digest("hex");
  if (digest !== req.source_sha256) throw Error("source_mismatch");
  const kind = req.path.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const source = ts.createSourceFile("input." + (kind === ts.ScriptKind.TSX ? "tsx" : "ts"), req.source,
    ts.ScriptTarget.Latest, true, kind);
  if (source.parseDiagnostics.length) throw Error("syntax_error");
  const findings = [];
  let shadowed = false, nodes = 0;
  function visit(node) {
    if (++nodes > 100000) throw Error("node_limit");
    if (ts.isIdentifier(node) && node.text === "eval") {
      const p = node.parent;
      if (!(ts.isCallExpression(p) && p.expression === node)) shadowed = true;
    }
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === "eval" &&
        node.arguments.length === 1 && ts.isIdentifier(node.arguments[0])) {
      findings.push({ rule: "TS-EVAL-001", line: source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1 });
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  const result = { version: 1, path: req.path, source_sha256: digest, pid: process.pid,
                   findings: shadowed ? [] : [...new Map(findings.map(f => [f.line, f])).values()] };
  const output = JSON.stringify(result);
  if (Buffer.byteLength(output) > 32768) throw Error("output_limit");
  process.stdout.write(output);
} catch (_) {
  process.exitCode = 2; // Never echo source or raw parser errors.
}
