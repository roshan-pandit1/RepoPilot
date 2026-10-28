"use client";

import { useEffect, useState } from "react";

type Identity = { user: { login: string }; demo: boolean };
type Installation = { id: string; account: string };
type Repository = { id: string; full_name: string };

function csrfToken(): string {
  const item = document.cookie.split("; ").find(value => value.startsWith("rp_csrf="));
  return item ? decodeURIComponent(item.slice("rp_csrf=".length)) : "";
}

async function jsonRequest<T>(url: string, method = "GET"): Promise<T> {
  const response = await fetch(url, {
    method, cache: "no-store", headers: method === "POST" ? { "X-CSRF-Token": csrfToken() } : {},
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail ?? "Request failed");
  return data as T;
}

export function GitHubAccount({ onConnected, connectedIds }: { onConnected: () => void; connectedIds: string[] }) {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [checking, setChecking] = useState(true);
  const [installations, setInstallations] = useState<Installation[]>([]);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [selectedInstallation, setSelectedInstallation] = useState("");
  const [message, setMessage] = useState("");
  const [jobId, setJobId] = useState("");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState("");
  useEffect(() => {
    let live = true;
    if (new URLSearchParams(window.location.search).get("auth_error") === "sign_in_failed") {
      queueMicrotask(() => { if (live) setMessage("GitHub sign-in failed. Please try again."); });
    }
    fetch("/api/auth/me", { cache: "no-store" }).then(async response => {
      if (!response.ok) return;
      const value = await response.json() as Identity;
      if (live) setIdentity(value);
    }).catch(() => {}).finally(() => { if (live) setChecking(false); });
    return () => { live = false; };
  }, []);

  useEffect(() => {
    if (!jobId) return;
    let live = true;
    const poll = async () => {
      try {
        const job = await jsonRequest<{ status: string }>(`/api/installations/sync/${jobId}`);
        if (!live) return;
        const messages: Record<string, string> = {
          pending: "Initial issue synchronization is queued.",
          processed: "Initial issue synchronization completed.",
          partial: "First 100 GitHub entries synchronized; additional pages are not yet supported.",
          ignored: "Synchronization stopped because access is no longer available.",
          failed: "Synchronization failed; check installation access and try again.",
        };
        setMessage(messages[job.status] ?? "Synchronization status unavailable.");
        if (job.status !== "pending") { setJobId(""); onConnected(); }
      } catch { if (live) { setMessage("Unable to check synchronization status."); setJobId(""); } }
    };
    void poll();
    const timer = setInterval(() => { void poll(); }, 5000);
    return () => { live = false; clearInterval(timer); };
  }, [jobId, onConnected]);

  async function listInstallations() {
    try {
      setBusy("installations");
      setMessage("");
      setRepos([]);
      setSelectedInstallation("");
      const items = await jsonRequest<Installation[]>("/api/installations/available");
      setInstallations(items);
      if (!items.length) setMessage("No eligible personal GitHub App installation was found. Install the app on your personal account and try again.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to verify installations"); }
    finally { setBusy(""); }
  }
  async function enroll(id: string) {
    try {
      setBusy(id);
      setMessage("");
      setRepos([]);
      setQuery("");
      const result = await jsonRequest<{ repositories: Repository[] }>(`/api/installations/${id}/enroll`, "POST");
      setSelectedInstallation(id);
      setRepos(result.repositories);
      if (!result.repositories.length) setMessage("No accessible public repositories were found for this installation.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to verify installation"); }
    finally { setBusy(""); }
  }
  async function connect(id: string) {
    try {
      setBusy(id);
      const result = await jsonRequest<{ sync_job_id: string }>(`/api/installations/${selectedInstallation}/repositories/${id}/select`, "POST");
      setJobId(result.sync_job_id);
      setMessage("Repository connected. Initial issue synchronization is queued.");
      onConnected();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to connect repository"); }
    finally { setBusy(""); }
  }
  async function logout() {
    try {
      await jsonRequest("/api/auth/logout", "POST");
      window.location.reload();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to sign out"); }
  }
  if (checking) return <p className="text-xs text-slate-500" role="status">Checking account…</p>;
  if (!identity) return <div><form action="/api/auth/start" method="get"><button className="button">Sign in with GitHub</button></form>{message && <p role="alert" className="mt-2 text-sm text-red-700">{message}</p>}</div>;
  if (identity.demo) return <p className="text-xs text-slate-500">Development demo account</p>;
  const visibleRepos = repos.filter(repo => repo.full_name.toLowerCase().includes(query.trim().toLowerCase()));
  return <section className="panel my-6 p-5 sm:p-6" aria-label="GitHub account">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div><p className="text-xs font-semibold uppercase tracking-wider text-emerald-700">GitHub connected</p><p className="mt-1 text-sm text-slate-600">Signed in as <strong className="text-slate-900">{identity.user.login}</strong></p></div>
      <button className="button" onClick={() => { void logout(); }}>Sign out</button>
    </div>
    <details className="group mt-5 border-t border-slate-100 pt-4">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 rounded-lg text-sm font-semibold text-emerald-800 [&::-webkit-details-marker]:hidden">
        <span>Manage repositories <span className="ml-2 font-normal text-slate-500">Connect a public repository</span></span><span aria-hidden="true" className="text-lg transition-transform group-open:rotate-180">⌄</span>
      </summary>
      <div className="mt-4 max-w-2xl">
        <p className="text-sm leading-6 text-slate-500">Find your personal GitHub App installation, then choose a repository to connect.</p>
        <div className="mt-4 flex flex-wrap gap-2"><button className="button" disabled={!!busy} onClick={() => { void listInstallations(); }}>{busy === "installations" ? "Finding installations…" : "Find installations"}</button>
          {installations.map(item => <button key={item.id} className="button" disabled={!!busy} onClick={() => { void enroll(item.id); }}>{busy === item.id ? "Verifying…" : `Verify ${item.account}`}</button>)}
        </div>
        {selectedInstallation && repos.length > 0 && <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50/60 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-sm font-semibold text-slate-900">Available repositories</h3><p className="mt-1 text-xs text-slate-500">Public repositories accessible to this installation</p></div><span className="text-xs text-slate-500">{visibleRepos.length} shown</span></div>
          <label className="mt-4 block text-xs font-medium text-slate-600" htmlFor="repository-search">Search repositories</label>
          <input id="repository-search" name="repository-search" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search by name" className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm" />
          <ul className="mt-3 max-h-64 space-y-2 overflow-y-auto" aria-label="Available repositories">{visibleRepos.map(repo => <li key={repo.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2"><span className="min-w-0 flex-1 break-all text-sm font-medium text-slate-700">{repo.full_name}</span><button className="button shrink-0" disabled={!!busy || connectedIds.includes(repo.id)} onClick={() => { void connect(repo.id); }}>{connectedIds.includes(repo.id) ? "Connected" : busy === repo.id ? "Connecting…" : "Connect"}</button></li>)}</ul>
          {!visibleRepos.length && <p className="py-4 text-sm text-slate-500">No repositories match your search.</p>}
        </div>}
      </div>
    </details>
    {message && <p role="status" className="mt-4 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">{message}</p>}
  </section>;
}
