import "server-only";
import { NextRequest } from "next/server";

export function validRepository(value: string) {
  return /^\d{1,19}$/.test(value) && BigInt(value) > BigInt(0) && BigInt(value) < BigInt("9223372036854775808");
}

export async function forwardInvestigation(request: NextRequest, path: string, body?: string) {
  const headers: Record<string, string> = {};
  for (const name of ["cookie", "origin", "x-csrf-token"]) {
    const value = request.headers.get(name);
    if (value) headers[name] = value;
  }
  if (body !== undefined) headers["content-type"] = "application/json";
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
      method: request.method, headers, body, cache: "no-store", redirect: "manual", signal: AbortSignal.timeout(75000),
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


/** Fetch the server-validated export as bounded bytes; never trust arbitrary headers or filenames. */
export async function forwardPatchExport(request: NextRequest, path: string, proposalId: string, expectedHash: string) {
  const responseHeaders = { "Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff" };
  try {
    const cookie = request.headers.get("cookie");
    const upstream = await fetch(`${process.env.API_INTERNAL_URL ?? "http://api:8000"}${path}?sha256=${expectedHash}`, {
      method: "GET", headers: cookie ? { cookie } : {}, cache: "no-store", redirect: "manual", signal: AbortSignal.timeout(75000),
    });
    if (!upstream.ok) {
      const status = upstream.status >= 400 && upstream.status <= 599 ? upstream.status : 502;
      return Response.json({ detail: status === 401 ? "Authentication required" : status === 404 ? "Not found" : "Patch export unavailable" }, { status, headers: responseHeaders });
    }
    const hash = upstream.headers.get("x-patch-sha256");
    const commit = upstream.headers.get("x-source-commit");
    const snapshot = upstream.headers.get("x-source-snapshot");
    if (upstream.status !== 200 || hash !== expectedHash || !commit || !/^[a-f0-9]{40}$/.test(commit) ||
        !snapshot || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(snapshot) ||
        upstream.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "text/x-diff" || !upstream.body) throw new Error();
    const reader = upstream.body.getReader();
    const parts: Uint8Array[] = [];
    let size = 0;
    try {
      for (;;) {
        const next = await reader.read();
        if (next.done) break;
        size += next.value.length;
        if (size > 262144) { await reader.cancel(); throw new Error(); }
        parts.push(next.value);
      }
    } finally { reader.releaseLock(); }
    if (!size) throw new Error();
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const part of parts) { bytes.set(part, offset); offset += part.length; }
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))).map(n => n.toString(16).padStart(2, "0")).join("");
    if (digest !== expectedHash) throw new Error();
    return new Response(bytes, { status: 200, headers: { ...responseHeaders, "Content-Type": "text/x-diff; charset=utf-8",
      "Content-Disposition": `attachment; filename="repopilot-${proposalId}.patch"`, "X-Patch-SHA256": hash,
      "X-Source-Commit": commit, "X-Source-Snapshot": snapshot } });
  } catch {
    return Response.json({ detail: "Patch export unavailable" }, { status: 503, headers: responseHeaders });
  }
}
