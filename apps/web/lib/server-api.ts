import "server-only";

export function demoEnabled(): boolean {
  return process.env.APP_ENV === "development" && process.env.DEMO_AUTH_ENABLED === "true";
}

export async function apiFetch(path: string): Promise<Response> {
  if (!demoEnabled() || !process.env.DEMO_API_TOKEN) {
    return Response.json({ detail: "Demo access is disabled. Production sign-in is not yet available." }, { status: 401 });
  }
  return fetch(`${process.env.API_INTERNAL_URL ?? "http://api:8000"}${path}`, {
    headers: { Authorization: `Bearer ${process.env.DEMO_API_TOKEN}` },
    cache: "no-store", signal: AbortSignal.timeout(5000),
  });
}
