import "server-only";

export function demoEnabled(): boolean {
  return process.env.APP_ENV === "development" && process.env.DEMO_AUTH_ENABLED === "true";
}

export async function apiFetch(path: string, cookie = ""): Promise<Response> {
  const headers: Record<string, string> = {};
  if (cookie) headers.Cookie = cookie;
  if (demoEnabled() && process.env.DEMO_API_TOKEN) {
    headers.Authorization = `Bearer ${process.env.DEMO_API_TOKEN}`;
  }
  if (!cookie && !headers.Authorization) {
    return Response.json({ detail: "Authentication required." }, { status: 401 });
  }
  return fetch(`${process.env.API_INTERNAL_URL ?? "http://api:8000"}${path}`, {
    headers, cache: "no-store", signal: AbortSignal.timeout(30000),
  });
}
