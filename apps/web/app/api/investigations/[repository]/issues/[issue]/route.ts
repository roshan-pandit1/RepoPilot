import { NextRequest } from "next/server";
import { forwardInvestigation, validRepository } from "@/lib/investigation-proxy";

export async function POST(request: NextRequest, context: { params: Promise<{ repository: string; issue: string }> }) {
  const { repository, issue } = await context.params;
  if (!validRepository(repository) || !/^\d{1,10}$/.test(issue) || BigInt(issue) <= BigInt(0) ||
      BigInt(issue) >= BigInt("2147483648")) {
    return Response.json({ detail: "Invalid request" }, { status: 422, headers: { "Cache-Control": "no-store" } });
  }
  return forwardInvestigation(request, `/v1/repositories/${repository}/issues/${issue}/investigations`);
}
