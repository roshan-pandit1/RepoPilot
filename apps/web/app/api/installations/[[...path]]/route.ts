import { NextRequest } from "next/server";

async function proxy(request: NextRequest, path: string[]) {
  const getPath = request.method === "GET" && path.length === 1 && path[0] === "available";
  const status = request.method === "GET" && path.length === 2 && path[0] === "sync" && /^[0-9a-f-]{36}$/i.test(path[1]);
  const enroll = request.method === "POST" && path.length === 2 && /^\d+$/.test(path[0]) && path[1] === "enroll";
  const select = request.method === "POST" && path.length === 4 && /^\d+$/.test(path[0]) &&
    path[1] === "repositories" && /^\d+$/.test(path[2]) && path[3] === "select";
  if (!getPath && !status && !enroll && !select) return Response.json({ detail: "Not found" }, { status: 404 });
  const headers: Record<string, string> = {};
  for (const name of ["cookie", "origin", "x-csrf-token"]) {
    const value = request.headers.get(name);
    if (value) headers[name] = value;
  }
  try {
    const upstream = await fetch(`${process.env.API_INTERNAL_URL ?? "http://api:8000"}/v1/installations/${path.join("/")}`, {
      method: request.method, headers, cache: "no-store", signal: AbortSignal.timeout(30000),
    });
    return Response.json(await upstream.json(), { status: upstream.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ detail: "GitHub verification unavailable" }, { status: 503 });
  }
}

export async function GET(request: NextRequest, context: { params: Promise<{ path?: string[] }> }) {
  return proxy(request, (await context.params).path ?? []);
}
export async function POST(request: NextRequest, context: { params: Promise<{ path?: string[] }> }) {
  return proxy(request, (await context.params).path ?? []);
}
