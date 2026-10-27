const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");

// Exercise the actual Next.js route and server-only client with a mocked upstream.
function loadSource(file, dependencies, env, fetch) {
  const source = fs.readFileSync(path.join(__dirname, "..", file), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  const context = vm.createContext({
    module, exports: module.exports, Response, Request, URL, AbortSignal,
    process: { env }, fetch,
    require: (name) => {
      if (!(name in dependencies)) throw new Error(`Unexpected import: ${name}`);
      return dependencies[name];
    },
  });
  new vm.Script(compiled, { filename: file }).runInContext(context);
  return module.exports;
}

function routeFor(env, fetch) {
  const api = loadSource("lib/server-api.ts", { "server-only": {} }, env, fetch);
  return loadSource("app/api/dashboard/route.ts", { "@/lib/server-api": api }, env, fetch);
}

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
