export async function GET() {
  try {
    const response = await fetch(`${process.env.API_INTERNAL_URL ?? "http://api:8000"}/ready`, { cache: "no-store", signal: AbortSignal.timeout(5000) });
    return Response.json({ ready: response.ok }, { headers: { "Cache-Control": "no-store" } });
  } catch { return Response.json({ ready: false }); }
}
