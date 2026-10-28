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

export function GitHubAccount({ onConnected }: { onConnected: () => void }) {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [checking, setChecking] = useState(true);
  const [installations, setInstallations] = useState<Installation[]>([]);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [selectedInstallation, setSelectedInstallation] = useState("");
  const [message, setMessage] = useState("");
  const [jobId, setJobId] = useState("");
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
      setMessage("");
      const items = await jsonRequest<Installation[]>("/api/installations/available");
      setInstallations(items);
      if (!items.length) setMessage("No eligible personal GitHub App installation was found. Install the app on your personal account and try again.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to verify installations"); }
  }
  async function enroll(id: string) {
    try {
      setMessage("");
      const result = await jsonRequest<{ repositories: Repository[] }>(`/api/installations/${id}/enroll`, "POST");
      setSelectedInstallation(id);
      setRepos(result.repositories);
      if (!result.repositories.length) setMessage("No accessible public repositories were found for this installation.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to verify installation"); }
  }
  async function connect(id: string) {
    try {
      const result = await jsonRequest<{ sync_job_id: string }>(`/api/installations/${selectedInstallation}/repositories/${id}/select`, "POST");
      setJobId(result.sync_job_id);
      setMessage("Repository connected. Initial issue synchronization is queued.");
      onConnected();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to connect repository"); }
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
  return <div className="panel my-6 p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm">Signed in as <strong>{identity.user.login}</strong></p><button className="button" onClick={() => { void logout(); }}>Sign out</button></div>
    <p className="mt-2 text-xs text-slate-500">Connect a public repository from your personal GitHub App installation.</p>
    <button className="button mt-4" onClick={() => { void listInstallations(); }}>Find installations</button>
    {installations.map(item => <button key={item.id} className="button ml-2 mt-4" onClick={() => { void enroll(item.id); }}>Verify {item.account}</button>)}
    {repos.map(repo => <div key={repo.id} className="mt-3 flex items-center justify-between gap-3 text-sm"><span>{repo.full_name}</span><button className="button" onClick={() => { void connect(repo.id); }}>Connect</button></div>)}
    {message && <p role="status" className="mt-4 text-sm text-slate-600">{message}</p>}
  </div>;
}
