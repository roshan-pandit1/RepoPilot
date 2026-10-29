import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";
const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
function load(file, deps, fetch) {
  const source = fs.readFileSync(path.join(root, file), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }}).outputText;
  const mod = { exports: {} };
  const ctx = vm.createContext({ module: mod, exports: mod.exports, Response, Request, AbortSignal,
    process: { env: { API_INTERNAL_URL: "http://api.test" } }, fetch,
    require: (name) => { if (!(name in deps)) throw new Error("unexpected import"); return deps[name]; } });
  new vm.Script(code).runInContext(ctx);
  return mod.exports;
}
function routes(fetch) {
  const helper = load("lib/investigation-proxy.ts", { "server-only": {} }, fetch);
  const deps = { "@/lib/investigation-proxy": helper };
  return {
    submit: load("app/api/investigations/[repository]/issues/[issue]/route.ts", deps, fetch),
    status: load("app/api/investigations/[repository]/jobs/[job]/route.ts", deps, fetch),
  };
}
test("submission and status use fixed backend paths and forward session/CSRF server-side", async () => {
  const calls = [];
  const r = routes(async (url, options) => { calls.push({ url, options }); return Response.json({ status: "queued" }, { status: 202 }); });
  const request = new Request("http://web", { method: "POST", headers: { cookie: "rp_session=fixture", origin: "http://web", "x-csrf-token": "csrf" } });
  const result = await r.submit.POST(request, { params: Promise.resolve({ repository: "902", issue: "5" }) });
  assert.equal(result.status, 202);
  assert.equal(calls[0].url, "http://api.test/v1/repositories/902/issues/5/investigations");
  assert.equal(calls[0].options.headers.cookie, "rp_session=fixture");
  assert.equal(calls[0].options.headers["x-csrf-token"], "csrf");
  assert.doesNotMatch(await result.text(), /fixture|csrf/);
  const id = "00000000-0000-4000-8000-000000000000";
  await r.status.GET(new Request("http://web"), { params: Promise.resolve({ repository: "902", job: id }) });
  assert.equal(calls[1].url, `http://api.test/v1/repositories/902/investigations/${id}`);
});
test("bad paths and upstream failures fail safely", async () => {
  let calls = 0;
  const r = routes(async () => { calls++; return Response.json({ detail: "private secret" }, { status: 401 }); });
  const invalid = await r.submit.POST(new Request("http://web", { method: "POST" }), { params: Promise.resolve({ repository: "1", issue: "../x" }) });
  assert.equal(invalid.status, 422); assert.equal(calls, 0);
  const denied = await r.status.GET(new Request("http://web"), { params: Promise.resolve({ repository: "1", job: "00000000-0000-4000-8000-000000000000" }) });
  assert.equal(denied.status, 401); assert.doesNotMatch(await denied.text(), /private secret/);
});

test("evidence route uses the authorized backend path and preserves denial", async () => {
  let call;
  const fetch = async (url, options) => { call = { url, options }; return Response.json({ detail: "private detail" }, { status: 404 }); };
  const helper = load("lib/investigation-proxy.ts", { "server-only": {} }, fetch);
  const route = load("app/api/investigations/[repository]/jobs/[job]/evidence/route.ts",
    { "@/lib/investigation-proxy": helper }, fetch);
  const id = "00000000-0000-4000-8000-000000000000";
  const response = await route.GET(new Request("http://web", { headers: { cookie: "rp_session=fixture" } }),
    { params: Promise.resolve({ repository: "902", job: id }) });
  assert.equal(call.url, `http://api.test/v1/repositories/902/investigations/${id}/evidence`);
  assert.equal(call.options.headers.cookie, "rp_session=fixture");
  assert.equal(response.status, 404);
  assert.doesNotMatch(await response.text(), /private detail|fixture/);
});

test("report proxy forwards only validated paths and preserves authentication and CSRF", async () => {
  const calls = [];
  const fetch = async (url, options) => { calls.push({ url, options }); return Response.json({ status: "queued" }, { status: 202 }); };
  const helper = load("lib/investigation-proxy.ts", { "server-only": {} }, fetch);
  const route = load("app/api/investigations/[repository]/jobs/[job]/report/route.ts",
    { "@/lib/investigation-proxy": helper }, fetch);
  const id = "00000000-0000-4000-8000-000000000000";
  const context = { params: Promise.resolve({ repository: "902", job: id }) };
  const response = await route.POST(new Request("http://web", { method: "POST", headers: {
    cookie: "rp_session=fixture", origin: "http://web", "x-csrf-token": "csrf" } }), context);
  assert.equal(response.status, 202);
  assert.equal(calls[0].url, `http://api.test/v1/repositories/902/investigations/${id}/report`);
  assert.equal(calls[0].options.headers.cookie, "rp_session=fixture");
  assert.equal(calls[0].options.headers["x-csrf-token"], "csrf");
  assert.doesNotMatch(await response.text(), /fixture|csrf/);
  const bad = await route.GET(new Request("http://web"), { params: Promise.resolve({ repository: "x", job: id }) });
  assert.equal(bad.status, 422); assert.equal(calls.length, 1);
});
