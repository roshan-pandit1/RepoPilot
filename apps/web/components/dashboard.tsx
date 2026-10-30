"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { IssuePage, Repository } from "@/lib/types";
import { StatusBadge } from "./status-badge";
import { IssueList } from "./issue-list";
import { GitHubAccount } from "./github-account";
import { CodeIntelligence } from "./code-intelligence";
import { InvestigationWorkspace } from "./investigation-workspace";

async function read<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal, cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail ?? "Unable to load data");
  return data as T;
}

export function Dashboard({ demo }: { demo: boolean }) {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [selected, setSelected] = useState("");
  const [page, setPage] = useState<IssuePage | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState<boolean | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [offset, setOffset] = useState(0);
  const [investigationIssue, setInvestigationIssue] = useState<{ number: number } | undefined>();
  const handleConnected = useCallback(() => setRefresh(v => v + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    let busy = false;
    async function load() {
      if (busy) return;
      busy = true;
      try {
        const health = await read<{ ready: boolean }>("/api/health", controller.signal);
        setReady(health.ready);
      } catch { if (!controller.signal.aborted) setReady(false); }
      try {
        const repos = await read<Repository[]>("/api/dashboard", controller.signal);
        setRepositories(repos);
        const id = repos.some(r => r.id === selected) ? selected : repos[0]?.id ?? "";
        if (id !== selected) { setSelected(id); setInvestigationIssue(undefined); }
        const result = id ? await read<IssuePage>(`/api/dashboard?repository=${id}&offset=${offset}`, controller.signal) : null;
        setPage(result);
        setError("");
      } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Request failed"); }
      finally { busy = false; if (!controller.signal.aborted) setLoading(false); }
    }
    void load();
    const timer = setInterval(() => { void load(); }, demo ? 5000 : 30000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [selected, refresh, offset, demo]);

  const current = repositories.find(r => r.id === selected);
  return <div className="min-h-screen lg:grid lg:grid-cols-[240px_1fr]">
    <aside className="border-b border-slate-200 bg-white p-6 lg:min-h-screen lg:border-r">
      <Link href="/" className="flex items-center gap-3 text-xl font-bold tracking-tight"><span className="grid size-9 place-items-center rounded-xl bg-emerald-800 text-sm text-white">RP</span>RepoPilot</Link>
      <p className="mt-2 text-xs text-slate-500">Repository intelligence</p>
      <nav aria-label="Main navigation" className="mt-8 flex gap-2 lg:flex-col"><a href="#inbox" className="rounded-lg bg-emerald-50 px-3 py-2.5 text-sm font-semibold text-emerald-900" aria-current="page">◫ &nbsp; Issue inbox</a><a href={demo ? "#repositories" : "#github-account"} onClick={() => { const details = document.querySelector<HTMLDetailsElement>("#github-account details"); if (details) details.open = true; }} className="rounded-lg px-3 py-2.5 text-sm text-slate-600 hover:bg-slate-50">⌘ &nbsp; Repositories</a>{!demo && <a href="#code-search" className="rounded-lg px-3 py-2.5 text-sm text-slate-600 hover:bg-slate-50">⌕ &nbsp; Code search</a>}</nav>
      <div className="mt-8 rounded-xl border border-slate-200 p-4 text-xs leading-5 text-slate-500"><strong className="block text-slate-800">Sprint 01</strong>Secure issue ingestion<br/>AI investigations are coming later.</div>
    </aside>
    <main className="min-w-0 px-5 py-7 sm:px-10 lg:px-12">
      <header className="mb-9 flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-6"><p className="text-sm text-slate-500">Workspace <span className="mx-2 text-slate-300">/</span> <span className="text-slate-800">Issue inbox</span></p><StatusBadge tone={ready ? "good" : "warn"}>{ready === null ? "Checking system" : ready ? "API & storage ready" : "System unavailable"}</StatusBadge></header>
      <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow">YOUR REPOSITORY, IN FOCUS</p><h1 id="inbox" className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Issue inbox</h1><p className="mt-3 text-sm text-slate-500">Verified GitHub events. One reliable place to start investigating.</p></div><button className="button" onClick={() => { setLoading(true); setRefresh(v => v + 1); }}>↻ Refresh</button></div>
      <GitHubAccount onConnected={handleConnected} connectedIds={repositories.map(repo => repo.id)} />
      {demo && <p className="mt-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">Development demo · Shared demo identity. Repository fixtures are explicitly seeded; issues arrive through signed webhooks.</p>}
      <section aria-label="Ingestion overview" className="my-7 grid gap-4 sm:grid-cols-3">
        {[ ["Connected repositories", repositories.length], ["Awaiting ingestion", page?.ingestion.pending ?? "—"], ["Failed deliveries", page?.ingestion.failed ?? "—"] ].map(([label, value]) => <div key={label} className="panel px-5 py-5"><p className="text-xs font-medium text-slate-500">{label}</p><p className="mt-3 text-3xl font-semibold tracking-tight">{value}</p></div>)}
      </section>
      <section id="repositories" className="panel overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 p-5"><div><h2 className="font-semibold">Connected repositories</h2><p className="mt-1 text-xs text-slate-500">{current?.full_name ?? "No repository selected"}</p></div><label className="text-sm"><span className="sr-only">Select repository</span><select id="repository-selector" name="repository" value={selected} onChange={e => { setSelected(e.target.value); setInvestigationIssue(undefined); setOffset(0); setPage(null); setLoading(true); }} className="max-w-full rounded-lg border border-slate-200 bg-white p-2.5" disabled={!repositories.length}><option value="" disabled>Select a repository</option>{repositories.map(r => <option key={r.id} value={r.id}>{r.full_name}</option>)}</select></label></div>
        <IssueList error={error} loading={loading} page={page} hasRepositories={repositories.length > 0} demo={demo} onRetry={() => { setLoading(true); setRefresh(v => v + 1); }} onSelectIssue={!demo ? number => { setInvestigationIssue({ number }); document.getElementById("issue-investigation")?.scrollIntoView({ behavior: "smooth" }); } : undefined} />
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-5 py-3 text-xs text-slate-400"><span>Signed delivery → durable queue → issue record</span><div className="flex items-center gap-3"><button disabled={offset === 0} onClick={() => { setOffset(v => Math.max(0, v - 100)); setLoading(true); }}>Previous</button><span>Page {offset / 100 + 1}</span><button disabled={page?.items.length !== 100} onClick={() => { setOffset(v => v + 100); setLoading(true); }}>Next</button></div></footer>
      </section>
      {!demo && current && <InvestigationWorkspace key={`${current.id}:${current.full_name}`} repository={current} selectedIssue={investigationIssue} />}
      {!demo && (current ? <CodeIntelligence key={current.id} repository={current} /> : <section id="code-search" className="panel mt-8 p-6"><h2 className="font-semibold">Search repository code</h2><p className="mt-2 text-sm text-slate-500">Connect and select a public repository to get started.</p></section>)}
      <p className="mt-5 text-xs text-slate-400">Refreshes every {demo ? 5 : 30} seconds · At-least-once delivery with idempotent processing</p>
    </main>
  </div>;
}
