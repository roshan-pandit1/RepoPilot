import "server-only";
import { NextRequest } from "next/server";

export function validRepository(value: string) {
  return /^\d{1,19}$/.test(value) && BigInt(value) > BigInt(0) && BigInt(value) < BigInt("9223372036854775808");
}

export async function forwardInvestigation(request: NextRequest, path: string) {
  const headers: Record<string, string> = {};
  for (const name of ["cookie", "origin", "x-csrf-token"]) {
    const value = request.headers.get(name);
    if (value) headers[name] = value;
  }
  if (request.method === "POST" && !headers["x-csrf-token"] && headers.cookie) {
    // Keep the existing double-submit CSRF check while deriving its header server-side.
    const part = headers.cookie.split(";").map(value => value.trim()).find(value => value.startsWith("rp_csrf="));
    if (part) {
      try {
        const value = decodeURIComponent(part.slice("rp_csrf=".length));
        if (value.length <= 256) headers["x-csrf-token"] = value;
      } catch { /* The backend will reject a malformed or missing CSRF value. */ }
    }
  }
  const responseHeaders = { "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" };
  try {
    const upstream = await fetch(`${process.env.API_INTERNAL_URL ?? "http://api:8000"}${path}`, {
      method: request.method, headers, cache: "no-store", redirect: "manual", signal: AbortSignal.timeout(75000),
    });
    if (!upstream.ok) {
      const status = upstream.status >= 400 && upstream.status <= 599 ? upstream.status : 502;
      return Response.json({ detail: status === 401 ? "Authentication required" :
        status === 404 ? "Not found" : "Investigation unavailable" }, { status, headers: responseHeaders });
    }
    if (![200, 202].includes(upstream.status)) throw new Error("Invalid upstream status");
    return Response.json(await upstream.json(), { status: upstream.status, headers: responseHeaders });
  } catch {
    return Response.json({ detail: "Investigation unavailable" }, { status: 503, headers: responseHeaders });
  }
}
