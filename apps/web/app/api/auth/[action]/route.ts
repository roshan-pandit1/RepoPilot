import { NextRequest } from "next/server";
import { demoEnabled } from "@/lib/server-api";

const paths: Record<string, string> = {
  start: "/v1/auth/github/start", callback: "/v1/auth/github/callback",
  me: "/v1/auth/me", logout: "/v1/auth/logout",
};

async function proxy(request: NextRequest, action: string) {
  const path = paths[action];
  if (!path || (action === "logout") !== (request.method === "POST")) {
    return Response.json({ detail: "Not found" }, { status: 404 });
  }
  const headers: Record<string, string> = {};
  const cookie = request.headers.get("cookie");
  if (cookie) headers.Cookie = cookie;
  if (demoEnabled() && process.env.DEMO_API_TOKEN) headers.Authorization = `Bearer ${process.env.DEMO_API_TOKEN}`;
  const origin = request.headers.get("origin");
  const csrf = request.headers.get("x-csrf-token");
  if (origin) headers.Origin = origin;
  if (csrf) headers["X-CSRF-Token"] = csrf;
  try {
    const query = action === "callback" ? request.nextUrl.search : "";
    const upstream = await fetch(`${process.env.API_INTERNAL_URL ?? "http://api:8000"}${path}${query}`, {
      method: request.method, headers, redirect: "manual", cache: "no-store", signal: AbortSignal.timeout(15000),
    });
    if (action === "callback" && upstream.status >= 400) {
      const destination = new URL("/", request.url);
      destination.searchParams.set("auth_error", "sign_in_failed");
      return new Response(null, { status: 303, headers: { Location: destination.toString(),
        "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" } });
    }
    const result = new Response(upstream.body, { status: upstream.status });
    for (const header of ["content-type", "location"]) {
      const value = upstream.headers.get(header);
      if (value) result.headers.set(header, value);
    }
    for (const value of upstream.headers.getSetCookie()) result.headers.append("set-cookie", value);
    result.headers.set("Cache-Control", "no-store");
    result.headers.set("Referrer-Policy", "no-referrer");
    return result;
  } catch {
    if (action === "callback") {
      const destination = new URL("/", request.url);
      destination.searchParams.set("auth_error", "sign_in_failed");
      return new Response(null, { status: 303, headers: { Location: destination.toString(),
        "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" } });
    }
    return Response.json({ detail: "Authentication service unavailable" }, { status: 503 });
  }
}

export async function GET(request: NextRequest, context: { params: Promise<{ action: string }> }) {
  return proxy(request, (await context.params).action);
}
export async function POST(request: NextRequest, context: { params: Promise<{ action: string }> }) {
  return proxy(request, (await context.params).action);
}
