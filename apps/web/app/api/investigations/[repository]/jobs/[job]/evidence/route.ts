import { NextRequest } from "next/server";
import { forwardInvestigation, validRepository } from "@/lib/investigation-proxy";

export async function GET(request: NextRequest, context: { params: Promise<{ repository: string; job: string }> }) {
  const { repository, job } = await context.params;
  if (!validRepository(repository) || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(job)) {
    return Response.json({ detail: "Invalid request" }, { status: 422, headers: { "Cache-Control": "no-store" } });
  }
  const query = new URL(request.url).searchParams;
  const includeSnippets = query.get("include_snippets") === "true";
  return forwardInvestigation(request, `/v1/repositories/${repository}/investigations/${job}/evidence${includeSnippets ? "?include_snippets=true" : ""}`);
}
