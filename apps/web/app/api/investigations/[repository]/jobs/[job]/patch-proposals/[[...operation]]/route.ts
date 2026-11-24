import { NextRequest } from "next/server";
import { forwardInvestigation, forwardPatchExport, validRepository } from "@/lib/investigation-proxy";

type Context = { params: Promise<{ repository: string; job: string; operation?: string[] }> };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const invalid = () => Response.json({ detail: "Invalid request" }, { status: 422, headers: { "Cache-Control": "no-store" } });

async function boundedBody(request: NextRequest): Promise<string> {
  if (!request.body || !request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) throw new Error();
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    for (;;) {
      const next = await reader.read();
      if (next.done) break;
      size += next.value.length;
      if (size > 2048) { await reader.cancel(); throw new Error(); }
      chunks.push(next.value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
}

async function forward(request: NextRequest, context: Context) {
  const { repository, job, operation = [] } = await context.params;
  if (!validRepository(repository) || !uuid.test(job) || operation.length > 2 ||
      (operation.length > 0 && !uuid.test(operation[0])) ||
      (operation.length === 2 && !["static-validation", "test-validation", "review", "export"].includes(operation[1])) ||
      (request.method === "GET" && operation.length > 1 && operation[1] !== "export") ||
      (request.method === "POST" && (operation.length === 1 || operation[1] === "export"))) return invalid();
  if (operation.length === 2 && operation[1] === "export") {
    const query = new URL(request.url).searchParams;
    const hash = query.get("sha256");
    if (!hash || !/^[a-f0-9]{64}$/.test(hash) || query.getAll("sha256").length !== 1 || Array.from(query.keys()).length !== 1) return invalid();
    return forwardPatchExport(request, `/v1/repositories/${repository}/investigations/${job}/patch-proposals/${operation[0]}/export`, operation[0].toLowerCase(), hash);
  }
  let body: string | undefined;
  if (request.method === "POST" && (operation.length === 0 || operation[1] === "review")) {
    try {
      const value: unknown = JSON.parse(await boundedBody(request));
      if (!value || typeof value !== "object" || Array.isArray(value)) return invalid();
      const record = value as Record<string, unknown>;
      if (operation.length === 0) {
        if (Object.keys(record).length !== 1 || typeof record.request_id !== "string" || !uuid.test(record.request_id)) return invalid();
      } else if (Object.keys(record).length !== 1 || !["approved_for_review", "rejected"].includes(String(record.decision))) return invalid();
      body = JSON.stringify(record);
    } catch { return invalid(); }
  }
  const suffix = operation.length ? `/${operation.join("/")}` : "";
  return forwardInvestigation(request, `/v1/repositories/${repository}/investigations/${job}/patch-proposals${suffix}`, body);
}
export async function GET(request: NextRequest, context: Context) { return forward(request, context); }
export async function POST(request: NextRequest, context: Context) { return forward(request, context); }
