import type { IssuePage } from "@/lib/types";
import { StatusBadge } from "./status-badge";

type Props = {
  error: string;
  loading: boolean;
  page: IssuePage | null;
  hasRepositories: boolean;
  demo?: boolean;
  onRetry: () => void;
  onSelectIssue?: (number: number) => void;
};

export function IssueList({ error, loading, page, hasRepositories, demo = false, onRetry, onSelectIssue }: Props) {
  if (loading) {
    return <div role="status" className="animate-pulse p-12 text-center text-sm text-slate-500">Loading verified issues…</div>;
  }
  if (error) {
    return <div role="alert" className="p-10 text-center"><h3 className="font-semibold">We couldn’t load your inbox</h3><p className="mt-2 text-sm text-red-700">{error}</p><button className="button mt-5" onClick={onRetry}>Try again</button></div>;
  }
  if (!page?.items.length) {
    return <div className="p-14 text-center"><span className="text-3xl text-emerald-700" aria-hidden="true">◇</span><h3 className="mt-3 font-semibold">{hasRepositories ? "Ready for your first issue" : "No authorized repositories yet"}</h3><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">{hasRepositories ? (demo ? "Send a signed issue webhook or run make smoke to see an issue here." : "Issues synchronized from GitHub or received through your webhook will appear here.") : (demo ? "Run make seed to connect the local demo repository." : "Open Manage repositories above to find your GitHub installation and connect a public repository.")}</p></div>;
  }
  return <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-xs text-slate-500"><tr>{["Issue", "State", "Ingestion", "Updated"].map(h => <th key={h} className="px-5 py-3 font-medium">{h}</th>)}</tr></thead><tbody>{page.items.map(issue => <tr key={issue.id} className="border-t border-slate-100"><td className="min-w-64 px-5 py-5"><p className="font-medium">{issue.title}</p><p className="mt-1 text-xs text-slate-400">#{issue.number}</p>{onSelectIssue && <button className="mt-2 text-xs font-semibold text-emerald-700 hover:underline" onClick={() => onSelectIssue(issue.number)}>Select issue for investigation</button>}</td><td className="px-5 py-5"><StatusBadge tone={issue.state === "open" ? "good" : "neutral"}>{issue.state}</StatusBadge></td><td className="px-5 py-5 text-xs text-slate-500">✓ {issue.ingestion_status}</td><td className="whitespace-nowrap px-5 py-5 text-xs text-slate-500">{new Date(issue.updated_at).toLocaleString()}</td></tr>)}</tbody></table></div>;
}
