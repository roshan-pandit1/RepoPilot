import { NextRequest } from "next/server";

// Only the authenticated backend makes repository and tenant authorization decisions.
export async function GET(request: NextRequest, context: { params: Promise<{ repository: string; issue: string }> }) {
  const { repository, issue } = await context.params;
  const valid = /^\d{1,19}$/.test(repository) && /^\d{1,10}$/.test(issue) &&
    BigInt(repository) > BigInt(0) && BigInt(repository) < BigInt("9223372036854775808") &&
    BigInt(issue) > BigInt(0) && BigInt(issue) < BigInt("2147483648");
  const headers = { "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" };
  if (!valid) return Response.json({ detail: "Invalid request" }, { status: 422, headers });

  const cookie = request.headers.get("cookie");
  try {
    const response = await fetch(
      `${process.env.API_INTERNAL_URL ?? "http://api:8000"}/v1/repositories/${repository}/issues/${issue}/context`,
      { method: "GET", headers: cookie ? { cookie } : {}, cache: "no-store", redirect: "manual",
        signal: AbortSignal.timeout(75000) },
    );
    if (response.status !== 200) {
      const status = response.status >= 400 && response.status <= 599 ? response.status : 502;
      const detail = status === 401 ? "Authentication required" :
        status === 404 ? "Issue or repository not found" : "Issue context unavailable";
      return Response.json({ detail }, { status, headers });
    }
    return Response.json(await response.json(), { status: 200, headers });
  } catch {
    return Response.json({ detail: "Issue context unavailable" }, { status: 503, headers });
  }
}
