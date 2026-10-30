import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Exercise the actual Next.js route and server-only client with a mocked upstream.
function loadSource(file, dependencies, env, fetch) {
  const source = fs.readFileSync(path.join(__dirname, "..", file), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const loadedModule = { exports: {} };
  const context = vm.createContext({
    module: loadedModule, exports: loadedModule.exports, Response, Request, URL, AbortSignal, TextDecoder,
    process: { env }, fetch,
    require: (name) => {
      if (!(name in dependencies)) throw new Error(`Unexpected import: ${name}`);
      return dependencies[name];
    },
  });
  new vm.Script(compiled, { filename: file }).runInContext(context);
  return loadedModule.exports;
}

function routeFor(env, fetch) {
  const api = loadSource("lib/server-api.ts", { "server-only": {} }, env, fetch);
  return loadSource("app/api/dashboard/route.ts", { "@/lib/server-api": api }, env, fetch);
}

function codeRoute(env, fetch) {
  return loadSource("app/api/code/[repository]/[action]/route.ts", {}, env, fetch);
}

test("index proxy forwards session and CSRF headers to the authorized backend", async () => {
  let upstream;
  const route = codeRoute({ API_INTERNAL_URL: "http://api.example" }, async (url, options) => {
    upstream = { url, options };
    return Response.json({ job_id: "job", status: "pending" }, { status: 202 });
  });
  const request = new Request("http://web/api/code/902/index", { method: "POST", headers: {
    cookie: "rp_session=opaque", origin: "http://web", "x-csrf-token": "fixture" } });
  const result = await route.POST(request, { params: Promise.resolve({ repository: "902", action: "index" }) });
  assert.equal(result.status, 202);
  assert.equal(upstream.url, "http://api.example/v1/repositories/902/index");
  assert.equal(upstream.options.headers.cookie, "rp_session=opaque");
  assert.equal(upstream.options.headers["x-csrf-token"], "fixture");
  assert.equal(result.headers.get("cache-control"), "no-store");
});

test("index proxy rejects invalid paths and oversized searches", async () => {
  const route = codeRoute({}, async () => { throw new Error("must not fetch"); });
  const bad = await route.GET(new Request("http://web/"), { params: Promise.resolve({ repository: "1x", action: "index-status" }) });
  assert.equal(bad.status, 404);
  const request = new Request("http://web/", { method: "POST", body: JSON.stringify({ query: "x".repeat(5000) }) });
  const oversized = await route.POST(request, { params: Promise.resolve({ repository: "902", action: "search" }) });
  assert.equal(oversized.status, 413);
});

test("code proxy forwards search modes and embedding routes with session protections", async () => {
  const calls = [];
  const route = codeRoute({}, async (url, options) => { calls.push({ url, options }); return Response.json({ status: "ok" }); });
  for (const mode of ["keyword", "semantic", "hybrid"]) {
    const response = await route.POST(new Request("http://web", { method: "POST", headers: {
      cookie: "rp_session=opaque", origin: "http://web", "x-csrf-token": "csrf" },
      body: JSON.stringify({ query: "example", mode }) }), { params: Promise.resolve({ repository: "902", action: "search" }) });
    assert.equal(response.status, 200);
    assert.equal(JSON.parse(calls.at(-1).options.body).mode, mode);
    assert.equal(calls.at(-1).options.headers["x-csrf-token"], "csrf");
  }
  const invalid = await route.POST(new Request("http://web", { method: "POST", body: JSON.stringify({ query: "x", mode: "other" }) }), { params: Promise.resolve({ repository: "902", action: "search" }) });
  assert.equal(invalid.status, 422);
  const status = await route.GET(new Request("http://web"), { params: Promise.resolve({ repository: "902", action: "embedding-status" }) });
  assert.equal(status.status, 200);
  const start = await route.POST(new Request("http://web", { method: "POST" }), { params: Promise.resolve({ repository: "902", action: "embeddings" }) });
  assert.equal(start.status, 200);
});

const development = {
  APP_ENV: "development", DEMO_AUTH_ENABLED: "true", DEMO_API_TOKEN: "fixture-secret",
  API_INTERNAL_URL: "http://api.example",
};

test("dashboard forwards authorized repository reads without exposing the token", async () => {
  let upstream;
  const route = routeFor(development, async (url, options) => {
    upstream = { url, options };
    return Response.json({ items: [{ title: "[Mock] Signed issue" }], ingestion: {} });
  });
  const response = await route.GET(new Request("http://web/api/dashboard?repository=2001&offset=0"));
  assert.equal(response.status, 200);
  assert.equal(upstream.url, "http://api.example/v1/repositories/2001/issues?offset=0");
  assert.equal(upstream.options.headers.Authorization, "Bearer fixture-secret");
  assert.equal(response.headers.get("cache-control"), "no-store");
  const body = await response.text();
  assert.match(body, /\[Mock\] Signed issue/);
  assert.doesNotMatch(body, /fixture-secret/);
});

test("demo is disabled in production and does not make an upstream request", async () => {
  let called = false;
  const route = routeFor({ ...development, APP_ENV: "production" }, async () => { called = true; });
  const response = await route.GET(new Request("http://web/api/dashboard"));
  assert.equal(response.status, 401);
  assert.equal(called, false);
});

test("invalid repository and offset are rejected before fetching", async () => {
  const route = routeFor(development, async () => { throw new Error("must not fetch"); });
  for (const query of ["repository=abc", "repository=1&offset=-1", "offset=0%26a%3Db"]) {
    const response = await route.GET(new Request(`http://web/api/dashboard?${query}`));
    assert.equal(response.status, 400);
  }
});

test("upstream authorization errors and connection failures are handled safely", async () => {
  const denied = routeFor(development, async () => Response.json({ detail: "Authentication required" }, { status: 401 }));
  assert.equal((await denied.GET(new Request("http://web/api/dashboard"))).status, 401);
  const unavailable = routeFor(development, async () => { throw new Error("fixture-secret"); });
  const response = await unavailable.GET(new Request("http://web/api/dashboard"));
  assert.equal(response.status, 503);
  assert.doesNotMatch(await response.text(), /fixture-secret/);
});

test("production session cookie is forwarded server-side without demo credentials", async () => {
  const env = { ...development, APP_ENV: "production" };
  let upstream;
  const route = routeFor(env, async (url, options) => {
    upstream = { url, options };
    return Response.json([{ id: "902", full_name: "alice/public" }]);
  });
  const response = await route.GET(new Request("http://web/api/dashboard", {
    headers: { Cookie: "rp_session=opaque-session" },
  }));
  assert.equal(response.status, 200);
  assert.equal(upstream.options.headers.Cookie, "rp_session=opaque-session");
  assert.equal(upstream.options.headers.Authorization, undefined);
});

function authRoute(env, fetch) {
  const api = loadSource("lib/server-api.ts", { "server-only": {} }, env, fetch);
  return loadSource("app/api/auth/[action]/route.ts", { "@/lib/server-api": api }, env, fetch);
}

test("OAuth proxy forwards redirect and state cookie without exposing server secrets", async () => {
  let upstream;
  const route = authRoute({ ...development, APP_ENV: "production" }, async (url, options) => {
    upstream = { url, options };
    return new Response(null, { status: 302, headers: {
      location: "https://github.com/login/oauth/authorize?state=fixture",
      "set-cookie": "rp_oauth=fixture; Path=/; HttpOnly; SameSite=Lax",
    } });
  });
  const request = { method: "GET", headers: new Headers(), nextUrl: new URL("https://web/api/auth/start"), url: "https://web/api/auth/start" };
  const response = await route.GET(request, { params: Promise.resolve({ action: "start" }) });
  assert.equal(upstream.options.redirect, "manual");
  assert.equal(response.status, 302);
  assert.match(response.headers.get("set-cookie"), /HttpOnly/);
  assert.equal(response.headers.get("location"), "https://github.com/login/oauth/authorize?state=fixture");
  assert.doesNotMatch(await response.text(), /fixture-secret/);
});

test("failed OAuth callback redirects to a generic error without reflecting code or state", async () => {
  const route = authRoute(development, async () => Response.json({ detail: "error" }, { status: 400 }));
  const request = { method: "GET", headers: new Headers(), nextUrl: new URL("https://web/api/auth/callback?code=private-code&state=private-state"), url: "https://web/api/auth/callback?code=private-code&state=private-state" };
  const response = await route.GET(request, { params: Promise.resolve({ action: "callback" }) });
  assert.equal(response.status, 303);
  assert.equal(response.headers.get("location"), "https://web/?auth_error=sign_in_failed");
  assert.equal(response.headers.get("referrer-policy"), "no-referrer");
  assert.equal(response.headers.get("cache-control"), "no-store");
});
