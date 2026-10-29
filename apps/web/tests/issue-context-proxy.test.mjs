import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
function routeFor(fetch) {
  const file = "app/api/repositories/[repository]/issues/[issue]/context/route.ts";
  const source = fs.readFileSync(path.join(root, file), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
  }}).outputText;
  const mod = { exports: {} };
  const context = vm.createContext({ module: mod, exports: mod.exports, Response, Request, AbortSignal,
    process: { env: { API_INTERNAL_URL: "http://api.example" } }, fetch });
  new vm.Script(compiled, { filename: file }).runInContext(context);
  return mod.exports;
}
const params = (repository = "902", issue = "5") => ({ params: Promise.resolve({ repository, issue }) });

test("forwards session only to the precise backend GET and returns context", async () => {
  let call;
  const route = routeFor(async (url, options) => {
    call = { url, options };
    return Response.json({ repository_id: "902", number: 5, title: "Issue", truncation: { body: false } });
  });
  const response = await route.GET(new Request("http://web/", { headers: { cookie: "rp_session=fixture" } }), params());
  assert.equal(call.url, "http://api.example/v1/repositories/902/issues/5/context");
  assert.equal(call.options.method, "GET");
  assert.equal(call.options.headers.cookie, "rp_session=fixture");
  assert.equal(call.options.redirect, "manual");
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("set-cookie"), null);
  assert.doesNotMatch(await response.text(), /rp_session|fixture/);
});

test("forwards unauthenticated requests and preserves rejection", async () => {
  const route = routeFor(async (_, options) => {
    assert.equal(options.headers.cookie, undefined);
    return Response.json({ detail: "Authentication required" }, { status: 401 });
  });
  const response = await route.GET(new Request("http://web/"), params());
  assert.equal(response.status, 401);
  assert.equal((await response.json()).detail, "Authentication required");
});

test("rejects malformed or out-of-range IDs without contacting backend", async () => {
  const route = routeFor(async () => { throw new Error("unexpected request"); });
  for (const [repository, issue] of [["1/x", "1"], ["0", "1"], ["9223372036854775808", "1"],
    ["1", "-1"], ["1", "2147483648"], ["1", "1?x=2"]]) {
    assert.equal((await route.GET(new Request("http://web/"), params(repository, issue))).status, 422);
  }
});

test("preserves upstream error status without exposing upstream details or credentials", async () => {
  for (const status of [404, 422, 502, 503]) {
    const route = routeFor(async () => Response.json({ detail: "private fixture secret" }, { status }));
    const response = await route.GET(new Request("http://web/"), params());
    assert.equal(response.status, status);
    assert.doesNotMatch(await response.text(), /private fixture secret/);
  }
  const route = routeFor(async () => { throw new Error("private fixture secret"); });
  const response = await route.GET(new Request("http://web/"), params());
  assert.equal(response.status, 503);
  assert.doesNotMatch(await response.text(), /private fixture secret/);
});
