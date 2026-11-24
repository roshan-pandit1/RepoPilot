import assert from "node:assert/strict";
import { createHash, webcrypto } from "node:crypto";
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
  const ctx = vm.createContext({ module: mod, exports: mod.exports, Response, Request, AbortSignal, URL, URLSearchParams, TextDecoder, Uint8Array, crypto: webcrypto,
    process: { env: { API_INTERNAL_URL: "http://api.test" } }, fetch,
    require: (name) => { if (!(name in deps)) throw new Error("unexpected import"); return deps[name]; } });
  new vm.Script(code).runInContext(ctx);
  return mod.exports;
}

test("patch proxy bounds request bodies and forwards only authorized fixed operations", async () => {
  const calls = [];
  const fetch = async (url, options) => { calls.push({ url, options }); return Response.json({ id: "ok" }, { status: 202 }); };
  const helper = load("lib/investigation-proxy.ts", { "server-only": {} }, fetch);
  const route = load("app/api/investigations/[repository]/jobs/[job]/patch-proposals/[[...operation]]/route.ts",
    { "@/lib/investigation-proxy": helper }, fetch);
  const id = "11111111-1111-4111-8111-111111111111";
  const ctx = (operation) => ({ params: Promise.resolve({ repository: "902", job: id, operation }) });
  const req = (body) => new Request("http://web/", { method: "POST", headers: { "content-type": "application/json",
    cookie: "rp_session=fixture; rp_csrf=check", origin: "http://web" }, body: JSON.stringify(body) });
  assert.equal((await route.POST(req({ request_id: id }), ctx([]))).status, 202);
  assert.equal(calls[0].url, `http://api.test/v1/repositories/902/investigations/${id}/patch-proposals`);
  assert.equal(calls[0].options.headers["x-csrf-token"], "check");
  assert.equal(calls[0].options.body, JSON.stringify({ request_id: id }));
  assert.equal((await route.POST(req({ decision: "rejected" }), ctx([id, "review"]))).status, 202);
  assert.equal((await route.POST(req({ request_id: id, extra: "x" }), ctx([]))).status, 422);
  assert.equal((await route.POST(req({ request_id: "x".repeat(3000) }), ctx([]))).status, 422);
  assert.equal((await route.POST(req({ decision: "apply" }), ctx([id, "review"]))).status, 422);
  assert.equal((await route.GET(new Request("http://web"), ctx(["../escape"])) ).status, 422);
  assert.equal(calls.length, 2);
});
test("patch export proxy preserves validated bytes and rejects tampered metadata", async () => {
  const id = "11111111-1111-4111-8111-111111111111", snapshot = "22222222-2222-4222-8222-222222222222", commit = "a".repeat(40);
  const bytes = new TextEncoder().encode("--- a/src/café.py\n+++ b/src/café.py\n@@ -1 +1 @@\n-before\n+after\n");
  const hash = createHash("sha256").update(bytes).digest("hex");
  let mode = "ok", captured;
  const fetch = async (url, options) => {
    captured = { url, options };
    if (mode === "denied") return Response.json({ detail: "private backend detail" }, { status: 409 });
    const output = mode === "tampered" ? new Uint8Array([1, 2, 3]) : mode === "oversized" ? new Uint8Array(262145) : bytes;
    return new Response(output, { headers: { "Content-Type": "text/x-diff; charset=utf-8", "X-Patch-SHA256": hash,
      "X-Source-Commit": commit, "X-Source-Snapshot": snapshot, "Set-Cookie": "unsafe=secret",
      "Content-Disposition": 'attachment; filename="../unsafe.patch"' } });
  };
  const helper = load("lib/investigation-proxy.ts", { "server-only": {} }, fetch);
  const route = load("app/api/investigations/[repository]/jobs/[job]/patch-proposals/[[...operation]]/route.ts", { "@/lib/investigation-proxy": helper }, fetch);
  const ctx = { params: Promise.resolve({ repository: "902", job: id, operation: [id, "export"] }) };
  const req = () => new Request(`http://web/api?sha256=${hash}`, { headers: { cookie: "rp_session=fixture" } });
  const result = await route.GET(req(), ctx);
  assert.equal(result.status, 200); assert.deepEqual(Buffer.from(await result.arrayBuffer()), Buffer.from(bytes));
  assert.equal(result.headers.get("x-patch-sha256"), hash); assert.equal(result.headers.get("x-source-commit"), commit);
  assert.equal(result.headers.get("x-source-snapshot"), snapshot); assert.equal(result.headers.get("cache-control"), "no-store");
  assert.equal(result.headers.get("set-cookie"), null); assert.equal(result.headers.get("content-disposition"), `attachment; filename="repopilot-${id}.patch"`);
  assert.equal(captured.options.headers.cookie, "rp_session=fixture");
  assert.match(captured.url, new RegExp(`/patch-proposals/${id}/export\\?sha256=${hash}$`));
  for (mode of ["tampered", "oversized"]) { const r = await route.GET(req(), ctx); assert.equal(r.status, 503); }
  mode = "denied"; const denied = await route.GET(req(), ctx); assert.equal(denied.status, 409); assert.doesNotMatch(await denied.text(), /private backend detail/);
  assert.equal((await route.GET(new Request(`http://web/?sha256=${hash}&sha256=${hash}`), ctx)).status, 422);
  assert.equal((await route.GET(new Request(`http://web/?sha256=${hash}&path=../x`), ctx)).status, 422);
  assert.equal((await route.POST(new Request("http://web", { method: "POST" }), ctx)).status, 422);
});

function routes(fetch) {
  const helper = load("lib/investigation-proxy.ts", { "server-only": {} }, fetch);
  const deps = { "@/lib/investigation-proxy": helper };
  return {
    submit: load("app/api/investigations/[repository]/issues/[issue]/route.ts", deps, fetch),
    status: load("app/api/investigations/[repository]/jobs/[job]/route.ts", deps, fetch),
  };
}

test("history proxy bounds pagination and forwards only validated parameters", async () => {
  const calls = [];
  const fetch = async (url, options) => { calls.push({ url, options }); return Response.json({ items: [], next_offset: null }); };
  const helper = load("lib/investigation-proxy.ts", { "server-only": {} }, fetch);
  const route = load("app/api/investigations/[repository]/history/route.ts", { "@/lib/investigation-proxy": helper }, fetch);
  const context = { params: Promise.resolve({ repository: "902" }) };
  const ok = await route.GET(new Request("http://web/?limit=20&offset=20&status=completed", { headers: { cookie: "rp_session=fixture" } }), context);
  assert.equal(ok.status, 200);
  assert.equal(calls[0].url, "http://api.test/v1/repositories/902/investigations?limit=20&offset=20&status=completed");
  assert.equal(calls[0].options.headers.cookie, "rp_session=fixture");
  for (const query of ["limit=51", "offset=-1", "status=other", "limit=1&limit=2", "extra=x"]) {
    assert.equal((await route.GET(new Request(`http://web/?${query}`), context)).status, 422);
  }
  assert.equal(calls.length, 1);
});

test("code intelligence proxy validates identifiers and forwards a read-only request", async () => {
  const calls = [];
  const fetch = async (url, options) => { calls.push({ url, options }); return Response.json({ version: "cie-v1" }); };
  const helper = load("lib/investigation-proxy.ts", { "server-only": {} }, fetch);
  const route = load("app/api/investigations/[repository]/jobs/[job]/code-intelligence/route.ts", { "@/lib/investigation-proxy": helper }, fetch);
  const job = "11111111-1111-4111-8111-111111111111";
  const ok = await route.GET(new Request("http://web/", { headers: { cookie: "rp_session=fixture" } }),
    { params: Promise.resolve({ repository: "902", job }) });
  assert.equal(ok.status, 200);
  assert.equal(calls[0].url, `http://api.test/v1/repositories/902/investigations/${job}/code-intelligence`);
  assert.equal(calls[0].options.method, "GET");
  assert.equal((await route.GET(new Request("http://web/"), { params: Promise.resolve({ repository: "902", job: "../bad" }) })).status, 422);
  assert.equal(calls.length, 1);
});
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

test("same-origin submission derives the CSRF header on the server without returning cookies", async () => {
  let call;
  const r = routes(async (url, options) => { call = { url, options }; return Response.json({ status: "queued" }, { status: 202 }); });
  const request = new Request("http://web", { method: "POST", headers: {
    cookie: "rp_session=opaque; rp_csrf=test%2Dcsrf", origin: "http://web" } });
  const result = await r.submit.POST(request, { params: Promise.resolve({ repository: "902", issue: "5" }) });
  assert.equal(call.options.headers["x-csrf-token"], "test-csrf");
  assert.equal(call.options.headers.origin, "http://web");
  assert.doesNotMatch(await result.text(), /opaque|csrf/);
  assert.equal(result.headers.get("set-cookie"), null);
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

test("evidence proxy forwards only the explicit bounded-snippet option", async () => {
  const calls = [];
  const fetch = async (url) => { calls.push(url); return Response.json({ items: [] }); };
  const helper = load("lib/investigation-proxy.ts", { "server-only": {} }, fetch);
  const route = load("app/api/investigations/[repository]/jobs/[job]/evidence/route.ts",
    { "@/lib/investigation-proxy": helper }, fetch);
  const id = "00000000-0000-4000-8000-000000000000";
  const context = { params: Promise.resolve({ repository: "902", job: id }) };
  await route.GET(new Request("http://web/?include_snippets=true&other=private"), context);
  assert.equal(calls[0], `http://api.test/v1/repositories/902/investigations/${id}/evidence?include_snippets=true`);
  await route.GET(new Request("http://web/?include_snippets=false"), context);
  assert.equal(calls[1], `http://api.test/v1/repositories/902/investigations/${id}/evidence`);
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


test("upstream issue context proxy uses only an authorized fixed job path", async () => {
  const calls = [];
  const fetch = async (url, options) => { calls.push({ url, options }); return Response.json({ issue_id: "990" }); };
  const helper = load("lib/investigation-proxy.ts", { "server-only": {} }, fetch);
  const route = load("app/api/investigations/[repository]/jobs/[job]/upstream-context/route.ts", { "@/lib/investigation-proxy": helper }, fetch);
  const job = "11111111-1111-4111-8111-111111111111";
  const ok = await route.GET(new Request("http://web/", { headers: { cookie: "rp_session=fixture" } }),
    { params: Promise.resolve({ repository: "902", job }) });
  assert.equal(ok.status, 200);
  assert.equal(calls[0].url, `http://api.test/v1/repositories/902/investigations/${job}/upstream-context`);
  assert.equal(calls[0].options.headers.cookie, "rp_session=fixture");
  for (const params of [{ repository: "../escape", job }, { repository: "902", job: "../escape" }])
    assert.equal((await route.GET(new Request("http://web/"), { params: Promise.resolve(params) })).status, 422);
  assert.equal(calls.length, 1);
});


test("PR review proxy limits routes and forwards authenticated actions safely", async () => {
  const calls = [];
  const fetch = async (url, options) => { calls.push({ url, options }); return Response.json({ id: "ok" }, { status: 202 }); };
  const helper = load("lib/investigation-proxy.ts", { "server-only": {} }, fetch);
  const route = load("app/api/repositories/[repository]/pr-reviews/[[...operation]]/route.ts", { "@/lib/investigation-proxy": helper }, fetch);
  const id = "11111111-1111-4111-8111-111111111111", finding = "22222222-2222-4222-8222-222222222222";
  const ctx = operation => ({ params: Promise.resolve({ repository: "902", operation }) });
  const req = body => new Request("http://web/", { method: "POST", headers: { "content-type": "application/json", cookie: "rp_session=fixture; rp_csrf=check", origin: "http://web" }, body: JSON.stringify(body) });
  assert.equal((await route.POST(req({ url: "https://github.com/example/project/pull/123" }), ctx([]))).status, 202);
  assert.equal(calls[0].url, "http://api.test/v1/repositories/902/pr-reviews");
  assert.equal(calls[0].options.headers["x-csrf-token"], "check");
  assert.equal((await route.POST(req({ state: "false_positive", reason: "Safe" }), ctx([id, "findings", finding, "feedback"]))).status, 202);
  assert.equal(calls[1].url, `http://api.test/v1/repositories/902/pr-reviews/${id}/findings/${finding}/feedback`);
  assert.equal((await route.POST(req({ url: "https://github.com.example.test/example/project/pull/123" }), ctx([]))).status, 422);
  assert.equal((await route.POST(req({ state: "useful", extra: "unsafe" }), ctx([id, "findings", finding, "feedback"]))).status, 422);
  assert.equal((await route.POST(req({ state: "useful", reason: "x".repeat(501) }), ctx([id, "findings", finding, "feedback"]))).status, 422);
  assert.equal((await route.GET(new Request("http://web/"), ctx(["../escape"])) ).status, 422);
  assert.equal((await route.GET(new Request("http://web/?token=private"), ctx([]))).status, 422);
  assert.equal(calls.length, 2);
});
