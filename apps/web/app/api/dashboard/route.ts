import { apiFetch } from "@/lib/server-api";

export async function GET(request: Request) {
  const query = new URL(request.url).searchParams;
  const repository = query.get("repository");
  const offset = query.get("offset") ?? "0";
  if ((repository && !/^\d+$/.test(repository)) || !/^\d+$/.test(offset)) {
    return Response.json({ detail: "Invalid repository or offset" }, { status: 400 });
  }
  try {
    const upstream = await apiFetch(repository ? `/v1/repositories/${repository}/issues?offset=${offset}` : "/v1/repositories", request.headers.get("cookie") ?? "");
    return Response.json(await upstream.json(), { status: upstream.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ detail: "API unavailable. Check the local services and try again." }, { status: 503 });
  }
}
