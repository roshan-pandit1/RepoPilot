import { NextRequest } from "next/server";
import { forwardInvestigation, validRepository } from "@/lib/investigation-proxy";

type Context = { params: Promise<{ repository: string; job: string }> };
async function forward(request: NextRequest, context: Context) {
  const { repository, job } = await context.params;
  if (!validRepository(repository) || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(job)) {
    return Response.json({ detail: "Invalid request" }, { status: 422, headers: { "Cache-Control": "no-store" } });
  }
  return forwardInvestigation(request, `/v1/repositories/${repository}/investigations/${job}/report`);
}
export async function GET(request: NextRequest, context: Context) { return forward(request, context); }
export async function POST(request: NextRequest, context: Context) { return forward(request, context); }
