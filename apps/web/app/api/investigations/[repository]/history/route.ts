import { NextRequest } from "next/server";
import { forwardInvestigation, validRepository } from "@/lib/investigation-proxy";

export async function GET(request: NextRequest, context: { params: Promise<{ repository: string }> }) {
  const { repository } = await context.params;
  const input = new URL(request.url).searchParams;
  const limit = input.get("limit") ?? "20", offset = input.get("offset") ?? "0", status = input.get("status");
  if (!validRepository(repository) || [...input.keys()].some(key => !["limit", "offset", "status"].includes(key)) ||
      [...input.keys()].some(key => input.getAll(key).length !== 1) || !/^(?:[1-9]|[1-4][0-9]|50)$/.test(limit) ||
      !/^(?:0|[1-9][0-9]{0,3}|10000)$/.test(offset) ||
      (status !== null && !["queued", "running", "completed", "failed", "cancelled"].includes(status))) {
    return Response.json({ detail: "Invalid request" }, { status: 422, headers: { "Cache-Control": "no-store" } });
  }
  const params = new URLSearchParams({ limit, offset });
  if (status) params.set("status", status);
  return forwardInvestigation(request, `/v1/repositories/${repository}/investigations?${params}`);
}
