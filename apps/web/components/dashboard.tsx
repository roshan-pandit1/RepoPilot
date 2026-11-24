"use client";

import { useCallback, useEffect, useState } from "react";
import type { IssuePage, Repository } from "@/lib/types";
import { TopNavigation } from "./top-navigation";
import { IssueList } from "./issue-list";
import { GitHubAccount } from "./github-account";
import { CodeIntelligence } from "./code-intelligence";
import { InvestigationWorkspace } from "./investigation-workspace";
import { RepositorySelector } from "./repository-selector";
import { PRReviews } from "./pr-reviews";
import { Button, Icon, Skeleton } from "./ui";

class DashboardRequestError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

async function read<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal, cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new DashboardRequestError(data.detail ?? "Unable to load data", response.status);
  return data as T;
}

function RefreshAge({ timestamp }: { timestamp: number | null }) {
  const [now, setNow] = useState(0);
  useEffect(() => {
    if (timestamp === null) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [timestamp]);
  const elapsed = timestamp === null ? null : Math.max(0, Math.floor((now - timestamp) / 1000));
  return <span className="last-updated">{elapsed === null ? "Waiting for an update" : elapsed < 5 ? "Updated just now" : `Updated ${elapsed} seconds ago`}</span>;
}

function CodeSearchEmpty({ unauthenticated, unavailable }: { unauthenticated: boolean; unavailable: boolean }) {
  return <section id="code-search" className="code-placeholder reveal-panel">
    <div className="section-heading">
      <p className="eyebrow">CODE INTELLIGENCE</p>
      <h2>Find your way through code<span>.</span></h2>
      <p>Search the source behind the issue, without losing context.</p>
    </div>
    <div className="panel code-empty">
      <div className="search-input-shell is-disabled">
        <Icon name="search" />
        <input aria-label="Search indexed code" placeholder="Search for a function, symbol, or keyword" disabled />
        <kbd aria-hidden="true">/</kbd>
      </div>
      <div className="code-empty-message">
        <span><Icon name="code" /></span>
        <div><h3>Start with a repository</h3><p>Connect a repository to search its indexed code.</p></div>
        {unauthenticated ? <form action="/api/auth/start" method="get">
          <Button type="submit">Connect a repository <Icon name="arrow" width="16" height="16" /></Button>
        </form> : unavailable ? <Button disabled title="Try again when the connection is available">Connect a repository <Icon name="arrow" width="16" height="16" /></Button> : <a href="#github-account" className="button" onClick={() => {
          const details = document.querySelector<HTMLDetailsElement>("#github-account details");
          if (details) details.open = true;
        }}>Connect a repository <Icon name="arrow" width="16" height="16" /></a>}
      </div>
    </div>
  </section>;
}

export function Dashboard({ demo }: { demo: boolean }) {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [selected, setSelected] = useState("");
  const [page, setPage] = useState<IssuePage | null>(null);
  const [error, setError] = useState("");
  const [unauthenticated, setUnauthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState<boolean | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [offset, setOffset] = useState(0);
  const [investigationIssue, setInvestigationIssue] = useState<{ number: number } | undefined>();
  const [accountTarget, setAccountTarget] = useState<HTMLDivElement | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
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
        setUnauthenticated(false);
        setLastUpdated(Date.now());
      } catch (e) { if (!controller.signal.aborted) { setError(e instanceof Error ? e.message : "Request failed"); setUnauthenticated(e instanceof DashboardRequestError && e.status === 401); } }
      finally { busy = false; if (!controller.signal.aborted) setLoading(false); }
    }
    void load();
    const timer = setInterval(() => { void load(); }, demo ? 5000 : 30000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [selected, refresh, offset, demo]);

  const current = unauthenticated ? undefined : repositories.find(r => r.id === selected);
  const stats = [
    { label: "Connected repositories", value: repositories.length, icon: "repository" as const, accent: "indigo", helper: unauthenticated ? "Sign in to connect" : "Available to this account" },
    { label: "Awaiting ingestion", value: page?.ingestion.pending ?? 0, icon: "clock" as const, accent: "amber", helper: current ? "In the selected repository" : "No repository selected" },
    { label: "Failed deliveries", value: page?.ingestion.failed ?? 0, icon: "alert" as const, accent: "rose", helper: current ? "In the selected repository" : "No repository selected" },
  ];
  return <div className="min-h-screen">
    <TopNavigation demo={demo} ready={ready} accountRef={setAccountTarget} />
    <main className="dashboard-surface dashboard-shell min-w-0">
      <div className="dashboard-content">
      <header className="workspace-breadcrumb"><span>Workspace</span><span aria-hidden="true">/</span><span>Issue inbox</span><span className="workspace-breadcrumb-line" /></header>
      <div className="dashboard-hero reveal-hero"><div><p className="eyebrow">YOUR REPOSITORY, IN FOCUS</p><h1 id="inbox">Your issue <span>inbox.</span></h1><p className="hero-subtitle">From GitHub issue to a clearer next step.<br className="hero-break" /> Everything you need to start investigating, in one place.</p></div>
        <div className="hero-actions"><Button aria-busy={loading} onClick={() => { setLoading(true); setRefresh(v => v + 1); }}><Icon name="refresh" className={loading ? "icon-spinning" : ""} width="17" height="17" /> Refresh</Button><RefreshAge timestamp={lastUpdated} /></div>
      </div>
      <GitHubAccount onConnected={handleConnected} connectedIds={repositories.map(repo => repo.id)} actionTarget={accountTarget} />
      {demo && <p className="mt-6 rounded-lg border border-amber-400/30 bg-amber-950/45 px-4 py-3 text-sm text-amber-200">Development demo · Shared demo identity. Repository fixtures are explicitly seeded; issues arrive through signed webhooks.</p>}
      <section aria-label="Ingestion overview" className="stats-grid reveal-stats">
        {stats.map(stat => <article key={stat.label} className="stat-card" data-accent={stat.accent}><div className="stat-card-top"><span className="stat-icon"><Icon name={stat.icon} /></span><Icon name="spark" className="stat-marker" width="16" height="16" /></div><div className="stat-value">{loading ? <><Skeleton className="skeleton-stat" /><span className="sr-only">Loading</span></> : error ? <span className="stat-unavailable">{unauthenticated ? "No data yet" : "Unavailable"}</span> : stat.value}</div><h2>{stat.label}</h2><p>{stat.helper}</p></article>)}
      </section>
      <section id="repositories" className="panel inbox-panel reveal-panel">
        <div className="inbox-panel-header"><div className="panel-heading"><span className="panel-heading-icon"><Icon name="inbox" /></span><div><div className="panel-title-line"><h2>Issue inbox</h2><span className="panel-live"><span /> VERIFIED EVENTS</span></div><p>{current ? current.full_name : "Your issues, all in one place"}</p></div></div>
          <RepositorySelector repositories={unauthenticated ? [] : repositories} selected={selected} onSelect={id => { setSelected(id); setInvestigationIssue(undefined); setOffset(0); setPage(null); setLoading(true); }} />
        </div>
        <IssueList error={error} loading={loading} page={page} unauthenticated={unauthenticated} repositoryName={current?.full_name} hasRepositories={repositories.length > 0} demo={demo} onRetry={() => { setLoading(true); setRefresh(v => v + 1); }} onSelectIssue={!demo ? number => { setInvestigationIssue({ number }); document.getElementById("issue-investigation")?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); } : undefined} />
        <footer className="inbox-panel-footer"><div id="how-it-works" className="pipeline" role="group" aria-label="Signed delivery, durable queue, issue record"><span><Icon name="shield" /> Signed delivery</span><i aria-hidden="true" /><span><Icon name="queue" /> Durable queue</span><i aria-hidden="true" /><span><Icon name="inbox" /> Issue record</span></div><nav className="pagination" aria-label="Issue pages"><button disabled={offset === 0} onClick={() => { setOffset(v => Math.max(0, v - 100)); setLoading(true); }}>Previous</button><span>Page {offset / 100 + 1}</span><button disabled={page?.items.length !== 100} onClick={() => { setOffset(v => v + 100); setLoading(true); }}>Next</button></nav></footer>
      </section>
      {!demo && current && <PRReviews key={`pr:${current.id}`} repositoryId={current.id} repositoryName={current.full_name} />}
      {!demo && current && <InvestigationWorkspace key={`${current.id}:${current.full_name}`} repository={current} selectedIssue={investigationIssue} />}
      {!demo && (current ? <CodeIntelligence key={current.id} repository={current} /> : <CodeSearchEmpty unauthenticated={unauthenticated} unavailable={loading || !!error} />)}
      <footer className="dashboard-footer"><span><span className="footer-live-dot" /> Refreshes every {demo ? 5 : 30} seconds</span><span>At-least-once delivery <span aria-hidden="true">·</span> Idempotent processing</span></footer>
      </div>
    </main>
  </div>;
}
