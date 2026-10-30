"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Repository } from "@/lib/types";

export type IndexStatus = { status: string; commit_sha: string | null; indexed_at: string | null;
  file_count: number; chunk_count: number; skipped_count: number; error_code: string | null };
export type CodeResult = { path: string; symbol: string | null; snippet: string; start_line: number;
  end_line: number; commit_sha: string; url: string; score: number; retrieval_method?: string };
type SearchMode = "keyword" | "semantic" | "hybrid";
type SearchResponse = { items: CodeResult[]; partial: boolean; mode: SearchMode; fallback_reason: string | null };
export type EmbeddingStatus = { status: string; ready: boolean; generation_available: boolean;
  completed_chunks: number; total_chunks: number; provider: string | null; model: string | null;
  dimensions: number | null; snapshot_commit: string | null; job_commit: string | null; error_code: string | null };

const active = (status: string) => status === "pending" || status === "running";
export function createSearchGate() {
  let current: AbortController | null = null;
  return {
    start() { current?.abort(); current = new AbortController(); return current; },
    cancel() { current?.abort(); current = null; },
    isCurrent(controller: AbortController) { return current === controller && !controller.signal.aborted; },
    finish(controller: AbortController) { if (current === controller) { current = null; return !controller.signal.aborted; } return false; },
  };
}
const labels: Record<string, string> = { not_indexed: "Not indexed", pending: "Queued", running: "Indexing",
  completed: "Indexed", partial: "Partially indexed", failed: "Indexing failed", cancelled: "Indexing cancelled" };

export function messageFor(status: number, fallback: string): string {
  if (status === 401) return "Your session has expired. Sign in again to continue.";
  if (status === 403 || status === 404) return "Repository access is unavailable. Check your GitHub installation and sign in again.";
  if (status === 409) return "No published index is available yet. Index this repository first.";
  return fallback;
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, { ...options, cache: "no-store" });
  if (!response.ok) throw new Error(messageFor(response.status, "The request failed. Please try again."));
  return await response.json() as T;
}

function csrf(): string {
  const value = document.cookie.split("; ").find(item => item.startsWith("rp_csrf="));
  return value ? decodeURIComponent(value.slice("rp_csrf=".length)) : "";
}

// Render each token as text through React. Never treat repository source as HTML.
function PythonLine({ text }: { text: string }) {
  const tokens = text.split(/(#.*|\b(?:async|await|class|def|return|if|else|elif|for|while|in|import|from|as|with|try|except|raise|yield|pass|True|False|None)\b|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g);
  return <>{tokens.map((token, index) => <span key={index} className={token.startsWith("#") ? "text-slate-400" : /^['"]/.test(token) ? "text-emerald-300" : /^(async|await|class|def|return|if|else|elif|for|while|in|import|from|as|with|try|except|raise|yield|pass|True|False|None)$/.test(token) ? "text-sky-300" : "text-slate-100"}>{token}</span>)}</>;
}

function safeCitation(item: CodeResult, repository: Repository): string | null {
  try {
    const url = new URL(item.url);
    const parts = repository.full_name.split("/");
    const expected = `/${repository.full_name}/blob/${item.commit_sha}/${item.path}`;
    if (parts.length !== 2 || url.protocol !== "https:" || url.host !== "github.com" || url.username || url.password ||
        url.search || decodeURIComponent(url.pathname) !== expected || !/^[0-9a-f]{40}$/.test(item.commit_sha) ||
        item.start_line < 1 || item.end_line < item.start_line || url.hash !== `#L${item.start_line}-L${item.end_line}`) return null;
    return item.url;
  } catch { return null; }
}

export function SearchResults({ repository, results }: { repository: Repository; results: CodeResult[] }) {
  return <div className="space-y-4">{results.map((item, index) => {
    const link = safeCitation(item, repository);
    const lines = item.snippet.split("\n");
    if (lines.at(-1) === "") lines.pop();
    return <article key={`${item.path}:${item.start_line}:${index}`} className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="flex flex-wrap items-start justify-between gap-3 px-4 py-4 sm:px-5"><div className="min-w-0"><p className="mb-1 text-xs font-semibold text-emerald-700">Result {index + 1}{item.retrieval_method ? ` · ${item.retrieval_method}` : ""}</p><p className="break-all text-sm font-semibold text-slate-800">{item.path}</p><p className="mt-1 break-all text-xs text-slate-500">{repository.full_name} · {item.symbol ?? "Module"} · lines {item.start_line}–{item.end_line}</p><p className="mt-1 font-mono text-xs text-slate-400">{item.commit_sha}</p></div>
        {link ? <a href={link} target="_blank" rel="noopener noreferrer" className="text-sm font-semibold text-emerald-700 hover:underline">View source ↗</a> : <span className="text-xs text-red-700">Citation unavailable</span>}
      </div>
      <div className="overflow-x-auto bg-slate-950 py-3 font-mono text-xs leading-6"><pre aria-label={`Source from ${item.path}`}><code>{lines.map((line, lineIndex) => <span className="flex min-w-max px-4" key={lineIndex}><span aria-hidden="true" className="mr-5 w-8 select-none text-right text-slate-500">{item.start_line + lineIndex}</span><span><PythonLine text={line} /></span>{"\n"}</span>)}</code></pre></div>
    </article>;
  })}</div>;
}

export function EmbeddingSummary({ status }: { status: EmbeddingStatus }) {
  return <div className="mt-4 border-t border-slate-100 pt-4 text-sm text-slate-600">
    <p className="font-semibold">Embeddings: {status.ready ? "Ready for current snapshot" : "Not ready for current snapshot"}</p>
    <p className="mt-1">Job: {status.status.replaceAll("_", " ")}{active(status.status) ? ` · ${status.completed_chunks} / ${status.total_chunks} chunks` : ""}</p>
    {status.job_commit && <p className="mt-1 break-all font-mono text-xs">Job commit {status.job_commit}</p>}
    {status.model && <p className="mt-1">{status.provider} · {status.model} · {status.dimensions} dimensions</p>}
    {status.provider === "fake" && <p className="mt-1 text-xs text-amber-700">Test vectors are deterministic and do not demonstrate semantic understanding.</p>}
    {!status.generation_available && <p className="mt-1 text-xs">Embedding generation is unavailable. Keyword search remains available.</p>}
    {(status.status === "failed" || status.status === "cancelled") && <p role="alert" className="mt-1 text-red-700">Embedding job {status.status}. Check access and retry.{status.error_code ? ` (${status.error_code})` : ""}</p>}
  </div>;
}

export function SearchNotice({ result }: { result: SearchResponse }) {
  return result.fallback_reason ? <p role="status" className="mb-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Compatible embeddings are unavailable; showing keyword results instead. ({result.fallback_reason})</p> : <p className="mb-3 text-xs text-slate-500">Search mode: {result.mode}</p>;
}

export function IndexSummary({ status }: { status: IndexStatus }) {
  return <div><div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-800">{status.status === "completed" && !status.commit_sha ? "Snapshot unavailable" : labels[status.status] ?? "Status unavailable"}</span>{active(status.status) && <span className="text-xs text-slate-500">{status.status === "pending" ? "Waiting for a worker" : "Worker is processing the repository"}</span>}</div>
    {status.commit_sha ? <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3"><div><p className="text-xs text-slate-500">Indexed files</p><p className="mt-1 font-semibold">{status.file_count}</p></div><div><p className="text-xs text-slate-500">Code chunks</p><p className="mt-1 font-semibold">{status.chunk_count}</p></div><div><p className="text-xs text-slate-500">Last indexed</p><p className="mt-1 font-medium">{status.indexed_at ? new Date(status.indexed_at).toLocaleString() : "Unavailable"}</p></div><p className="break-all font-mono text-xs text-slate-500 sm:col-span-3">Commit {status.commit_sha}</p></div> : <p className="mt-3 text-sm text-slate-500">No published snapshot yet. Index this repository to search its Python code.</p>}
    {status.skipped_count > 0 && <p className="mt-3 text-xs text-amber-700">{status.skipped_count} files were skipped by indexing limits or source filtering.</p>}
    {(status.status === "failed" || status.status === "cancelled") && <p role="alert" className="mt-3 text-sm text-red-700">{status.status === "cancelled" ? "Indexing stopped. Check your session and repository access before retrying." : "Indexing did not complete. Check repository access and try again."}{status.error_code && <span className="ml-1 text-xs">({status.error_code})</span>}</p>}
  </div>;
}

export function CodeIntelligence({ repository }: { repository: Repository }) {
  const [status, setStatus] = useState<IndexStatus | null>(null);
  const [statusError, setStatusError] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("keyword");
  const [embedding, setEmbedding] = useState<EmbeddingStatus | null>(null);
  const [embeddingError, setEmbeddingError] = useState("");
  const [embeddingBusy, setEmbeddingBusy] = useState(false);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [lastQuery, setLastQuery] = useState("");
  const operations = useRef(new Set<AbortController>());
  const indexInFlight = useRef(false);
  const searchGate = useRef(createSearchGate());
  const embeddingInFlight = useRef(false);
  const path = `/api/code/${repository.id}`;
  const embeddingJobStatus = embedding?.status;
  const loadStatus = useCallback(async (signal: AbortSignal) => {
    try { const result = await request<IndexStatus>(`${path}/index-status`, { signal }); if (!signal.aborted) { setStatus(result); setStatusError(""); } }
    catch (error) { if (!signal.aborted) { setStatus(null); setResults(null); setStatusError(error instanceof Error ? error.message : "Unable to load indexing status."); } }
  }, [path]);
  useEffect(() => { const controller = new AbortController(); queueMicrotask(() => { if (!controller.signal.aborted) void loadStatus(controller.signal); }); return () => controller.abort(); }, [loadStatus]);
  const loadEmbedding = useCallback(async (signal: AbortSignal) => {
    try { const result = await request<EmbeddingStatus>(`${path}/embedding-status`, { signal }); if (!signal.aborted) { setEmbedding(result); setEmbeddingError(""); } }
    catch (error) { if (!signal.aborted) { setEmbedding(null); setEmbeddingError(error instanceof Error ? error.message : "Unable to load embedding status."); } }
  }, [path]);
  useEffect(() => { const controller = new AbortController(); queueMicrotask(() => { if (!controller.signal.aborted) void loadEmbedding(controller.signal); }); return () => controller.abort(); }, [loadEmbedding, status?.commit_sha, status?.status]);
  useEffect(() => {
    if (!embeddingJobStatus || !active(embeddingJobStatus)) return;
    const controller = new AbortController(); let running = false;
    const timer = setInterval(() => { if (!running) { running = true; void loadEmbedding(controller.signal).finally(() => { running = false; }); } }, 5000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [embeddingJobStatus, loadEmbedding]);
  useEffect(() => {
    if (!status || !active(status.status)) return;
    const controller = new AbortController(); let running = false;
    const timer = setInterval(() => { if (!running) { running = true; void loadStatus(controller.signal).finally(() => { running = false; }); } }, 5000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [status?.status, loadStatus, status]);
  useEffect(() => { const controllers = operations.current; return () => { for (const controller of controllers) controller.abort(); }; }, []);

  async function startIndex() {
    if (indexInFlight.current || busy || (status && active(status.status))) return;
    const token = csrf(); if (!token) { setStatusError("Your session has expired. Sign in again to continue."); return; }
    indexInFlight.current = true;
    const controller = new AbortController(); operations.current.add(controller); setBusy(true); setStatusError("");
    try {
      const result = await request<{ status: string }>(`${path}/index`, { method: "POST", signal: controller.signal, headers: { "X-CSRF-Token": token } });
      if (!controller.signal.aborted) setStatus(previous => ({ status: result.status, commit_sha: previous?.commit_sha ?? null, indexed_at: previous?.indexed_at ?? null, file_count: previous?.file_count ?? 0, chunk_count: previous?.chunk_count ?? 0, skipped_count: previous?.skipped_count ?? 0, error_code: null }));
    } catch (error) { if (!controller.signal.aborted) { setStatus(null); setResults(null); setStatusError(error instanceof Error ? error.message : "Unable to start indexing."); } }
    finally { indexInFlight.current = false; operations.current.delete(controller); if (!controller.signal.aborted) setBusy(false); }
  }
  async function startEmbedding() {
    if (embeddingInFlight.current || !embedding?.generation_available || active(embedding.status)) return;
    const token = csrf(); if (!token) { setEmbeddingError("Your session has expired. Sign in again to continue."); return; }
    embeddingInFlight.current = true;
    const controller = new AbortController(); operations.current.add(controller); setEmbeddingBusy(true); setEmbeddingError("");
    try {
      await request(`${path}/embeddings`, { method: "POST", signal: controller.signal, headers: { "X-CSRF-Token": token } });
      if (!controller.signal.aborted) await loadEmbedding(controller.signal);
    } catch (error) { if (!controller.signal.aborted) setEmbeddingError(error instanceof Error ? error.message : "Unable to start embedding generation."); }
    finally { embeddingInFlight.current = false; operations.current.delete(controller); if (!controller.signal.aborted) setEmbeddingBusy(false); }
  }
  function cancelSearch() {
    searchGate.current.cancel(); setSearching(false); setResults(null); setSearchError("");
  }
  async function search(value: string) {
    const term = value.trim(); if (!term) return;
    const token = csrf(); if (!token) { setResults(null); setSearchError("Your session has expired. Sign in again to continue."); return; }
    const controller = searchGate.current.start(); operations.current.add(controller); setSearching(true); setSearchError(""); setResults(null); setLastQuery(term);
    try { const data = await request<SearchResponse>(`${path}/search`, { method: "POST", signal: controller.signal, headers: { "Content-Type": "application/json", "X-CSRF-Token": token }, body: JSON.stringify({ query: term, limit: 10, mode }) }); if (searchGate.current.isCurrent(controller)) setResults(data); }
    catch (error) { if (!controller.signal.aborted) setSearchError(error instanceof Error ? error.message : "Search failed."); }
    finally { operations.current.delete(controller); if (searchGate.current.finish(controller)) setSearching(false); }
  }
  const repoUrl = `https://github.com/${repository.full_name.split("/").map(encodeURIComponent).join("/")}`;
  return <section id="code-search" className="mt-8 scroll-mt-6" aria-label="Repository code search">
    <div className="mb-4"><p className="eyebrow">CODE INTELLIGENCE</p><h2 className="mt-2 text-2xl font-semibold tracking-tight">Search repository code</h2><p className="mt-2 text-sm text-slate-500">Find Python symbols and open their exact source at the indexed commit.</p></div>
    <div className="panel p-5 sm:p-6"><div className="flex flex-wrap items-start justify-between gap-4"><div><h3 className="break-all font-semibold text-slate-900">{repository.full_name}</h3><a href={repoUrl} target="_blank" rel="noopener noreferrer" className="mt-1 inline-block text-xs font-semibold text-emerald-700 hover:underline">Open repository ↗</a></div><button className="button" disabled={busy || !status || active(status.status)} onClick={() => { void startIndex(); }}>{busy ? "Starting…" : status?.commit_sha ? "Reindex repository" : "Index repository"}</button></div>
      <div className="mt-5 border-t border-slate-100 pt-5">{statusError ? <div role="alert" className="text-sm text-red-700">{statusError} <button className="ml-2 font-semibold underline" onClick={() => { const controller = new AbortController(); operations.current.add(controller); void loadStatus(controller.signal).finally(() => operations.current.delete(controller)); }}>Retry</button></div> : status ? <IndexSummary status={status} /> : <p role="status" className="text-sm text-slate-500">Loading indexing status…</p>}</div>
      {embeddingError ? <p role="alert" className="mt-4 text-sm text-red-700">{embeddingError} <button className="ml-2 underline" onClick={() => { const controller = new AbortController(); operations.current.add(controller); void loadEmbedding(controller.signal).finally(() => operations.current.delete(controller)); }}>Retry</button></p> : embedding ? <><EmbeddingSummary status={embedding} />{embedding.generation_available && status?.commit_sha && <button className="button mt-3" disabled={embeddingBusy || active(embedding.status)} onClick={() => { void startEmbedding(); }}>{embeddingBusy ? "Starting…" : embedding.ready ? "Regenerate test embeddings" : "Generate test embeddings"}</button>}</> : <p role="status" className="mt-4 text-sm text-slate-500">Loading embedding status…</p>}
    </div>
    <form onSubmit={event => { event.preventDefault(); void search(query); }} className="mt-5"><label htmlFor="search-mode" className="text-sm font-semibold text-slate-800">Search mode</label><select id="search-mode" value={mode} onChange={event => { cancelSearch(); setMode(event.target.value as SearchMode); }} className="ml-3 rounded-lg border border-slate-200 bg-white p-2 text-sm"><option value="keyword">Keyword</option><option value="semantic">Semantic</option><option value="hybrid">Hybrid</option></select><div className="mt-4"><label htmlFor="code-query" className="text-sm font-semibold text-slate-800">Search indexed code</label></div><div className="mt-2 flex flex-wrap gap-2"><input id="code-query" name="query" type="search" maxLength={200} value={query} onChange={event => setQuery(event.target.value)} placeholder="Search for a function, symbol, or keyword" className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm" /><button className="button button-primary" type="submit" disabled={!status?.commit_sha || searching || !query.trim()}>{searching ? "Searching…" : "Search code"}</button></div></form>
    <div className="mt-5" aria-live="polite">{searching && <p role="status" className="text-sm text-slate-500">Searching indexed code…</p>}{searchError && <div role="alert" className="rounded-lg border border-red-100 bg-red-50 p-4 text-sm text-red-800">{searchError} <button className="ml-2 font-semibold underline" onClick={() => { void search(lastQuery); }}>Retry search</button></div>}{results && <><SearchNotice result={results} />{results.items.length ? <><div className="mb-3 flex items-center justify-between text-xs text-slate-500"><span>{results.items.length} results for “{lastQuery}”</span>{results.partial && <span className="text-amber-700">Partial index</span>}</div><SearchResults repository={repository} results={results.items} /></> : <p className="panel p-6 text-sm text-slate-500">No matches for “{lastQuery}”. Try another keyword or symbol.</p>}</>}</div>
  </section>;
}
