import { NextRequest } from "next/server";
import { forwardInvestigation, validRepository } from "@/lib/investigation-proxy";

type Context = { params: Promise<{ repository: string; operation?: string[] }> };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const invalid = () => Response.json({ detail: "Invalid request" }, { status: 422, headers: { "Cache-Control": "no-store" } });
async function body(request: NextRequest): Promise<string> {
  if (!request.body || !request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) throw new Error();
  const reader = request.body.getReader(), chunks: Uint8Array[] = []; let size = 0;
  try { for (;;) { const next = await reader.read(); if (next.done) break; size += next.value.length;
    if (size > 4096) { await reader.cancel(); throw new Error(); } chunks.push(next.value); }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
}
async function forward(request: NextRequest, context: Context) {
  const { repository, operation = [] } = await context.params;
  if (!validRepository(repository) || ![0, 1, 4].includes(operation.length) ||
      (operation.length && !uuid.test(operation[0])) ||
      (operation.length === 4 && (operation[1] !== "findings" || !uuid.test(operation[2]) || operation[3] !== "feedback")) ||
      (request.method === "GET" && operation.length === 4) || (request.method === "POST" && operation.length === 1) ||
      new URL(request.url).search) return invalid();
  let payload: string | undefined;
  if (request.method === "POST") {
    try { const value: unknown = JSON.parse(await body(request));
      if (!value || typeof value !== "object" || Array.isArray(value)) return invalid();
      const record = value as Record<string, unknown>;
      if (!operation.length) {
        if (Object.keys(record).length !== 1 || typeof record.url !== "string" || record.url.length > 1024 ||
            !/^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/pull\/[1-9][0-9]*$/.test(record.url)) return invalid();
      } else {
        if (Object.keys(record).some(k => !["state", "reason"].includes(k)) ||
            !["useful", "false_positive", "acknowledged"].includes(String(record.state)) ||
            !(record.reason === undefined || (typeof record.reason === "string" && record.reason.length <= 500))) return invalid();
      }
      payload = JSON.stringify(record);
    } catch { return invalid(); }
  }
  return forwardInvestigation(request, `/v1/repositories/${repository}/pr-reviews${operation.length ? `/${operation.join("/")}` : ""}`, payload);
}
export async function GET(request: NextRequest, context: Context) { return forward(request, context); }
export async function POST(request: NextRequest, context: Context) { return forward(request, context); }
