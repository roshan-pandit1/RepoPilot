import { NextRequest } from "next/server";

// Forward browser sessions and CSRF headers to the existing backend checks. The browser
// never receives GitHub credentials; only explicit routes are reachable.
async function proxy(request: NextRequest, repository: string, action: string) {
  const valid = /^\d{1,19}$/.test(repository) && BigInt(repository) > BigInt(0) &&
    ((request.method === "GET" && (action === "index-status" || action === "embedding-status")) ||
     (request.method === "POST" && (action === "index" || action === "search" || action === "embeddings")));
  if (!valid) return Response.json({ detail: "Not found" }, { status: 404 });
  const headers: Record<string, string> = {};
  for (const name of ["cookie", "origin", "x-csrf-token"]) {
    const value = request.headers.get(name);
    if (value) headers[name] = value;
  }
  let body: string | undefined;
  if (action === "search") {
    try {
      if (!request.body) return Response.json({ detail: "Invalid request" }, { status: 422 });
      const reader = request.body.getReader();
      const decoder = new TextDecoder();
      let input = "";
      let size = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > 4096) { await reader.cancel(); return Response.json({ detail: "Request too large" }, { status: 413 }); }
        input += decoder.decode(value, { stream: true });
      }
      input += decoder.decode();
      const data = JSON.parse(input) as { query?: unknown; limit?: unknown; mode?: unknown };
      if (!data || typeof data.query !== "string" || data.query.length > 200 ||
          (data.mode !== undefined && !["keyword", "semantic", "hybrid"].includes(data.mode as string)) ||
          (data.limit !== undefined && (!Number.isInteger(data.limit) || Number(data.limit) < 1 || Number(data.limit) > 50))) {
        return Response.json({ detail: "Invalid request" }, { status: 422 });
      }
      body = JSON.stringify({ query: data.query, limit: data.limit ?? 10, mode: data.mode ?? "keyword" });
      headers["content-type"] = "application/json";
    } catch {
      return Response.json({ detail: "Invalid request" }, { status: 422 });
    }
  }
  try {
    const response = await fetch(`${process.env.API_INTERNAL_URL ?? "http://api:8000"}/v1/repositories/${repository}/${action}`, {
      method: request.method, headers, body, cache: "no-store", signal: AbortSignal.timeout(30000),
    });
    return Response.json(await response.json(), { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ detail: "Index service unavailable" }, { status: 503 });
  }
}

type Context = { params: Promise<{ repository: string; action: string }> };
export async function GET(request: NextRequest, context: Context) {
  const { repository, action } = await context.params;
  return proxy(request, repository, action);
}
export async function POST(request: NextRequest, context: Context) {
  const { repository, action } = await context.params;
  return proxy(request, repository, action);
}
