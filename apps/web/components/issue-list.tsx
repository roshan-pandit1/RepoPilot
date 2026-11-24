import type { IssuePage } from "@/lib/types";
import { StatusBadge } from "./status-badge";
import { Button, EmptyState, GitHubMark, Icon, Skeleton } from "./ui";

type Props = {
  error: string;
  loading: boolean;
  page: IssuePage | null;
  hasRepositories: boolean;
  unauthenticated?: boolean;
  repositoryName?: string;
  demo?: boolean;
  onRetry: () => void;
  onSelectIssue?: (number: number) => void;
};

function relativeTime(value: string): string {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return "Date unavailable";
  const seconds = Math.round((timestamp - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (Math.abs(seconds) < 60) return formatter.format(seconds, "second");
  const minutes = Math.round(seconds / 60);
  if (Math.abs(minutes) < 60) return formatter.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return formatter.format(hours, "hour");
  const days = Math.round(hours / 24);
  if (Math.abs(days) < 30) return formatter.format(days, "day");
  const months = Math.round(days / 30);
  return Math.abs(months) < 12 ? formatter.format(months, "month") : formatter.format(Math.round(months / 12), "year");
}

export function IssueList({ error, loading, page, hasRepositories, unauthenticated = false, repositoryName, demo = false, onRetry, onSelectIssue }: Props) {
  if (loading) {
    return <div className="issue-skeletons" role="status" aria-label="Loading verified issues">
      <span className="sr-only">Loading verified issues…</span>{[0, 1, 2].map(index => <div className="issue-skeleton-row" key={index}><Skeleton className="skeleton-icon" /><span><Skeleton className="skeleton-title" /><Skeleton className="skeleton-subtitle" /></span><Skeleton className="skeleton-pill" /></div>)}
    </div>;
  }
  if (unauthenticated) {
    return <EmptyState icon={<><Icon name="inbox" className="empty-inbox-icon" /><span className="empty-github-icon"><GitHubMark /></span></>}
      title="Connect GitHub to see your issues" description="Bring your repository issues into one clear place to investigate what matters.">
      <div className="empty-actions"><form action="/api/auth/start" method="get"><Button variant="primary" type="submit"><GitHubMark /> Sign in with GitHub</Button></form><a className="text-link" href="#how-it-works">Learn how it works <Icon name="arrow" width="15" height="15" /></a></div>
      <ol className="onboarding-steps" aria-label="Getting started"><li><span>1</span> Sign in</li><li><span>2</span> Connect a repository</li><li><span>3</span> Issues appear here</li></ol>
    </EmptyState>;
  }
  if (error) {
    return <EmptyState alert icon={<Icon name="alert" />} title="We couldn’t load your inbox" description="Something interrupted the connection. Please try again.">
      <Button onClick={onRetry}><Icon name="refresh" width="17" height="17" /> Try again</Button>
      <details className="error-details"><summary>Show details</summary><p>{error}</p></details>
    </EmptyState>;
  }
  if (!page?.items.length) {
    return <EmptyState icon={<Icon name={hasRepositories ? "inbox" : "repository"} />}
      title={hasRepositories ? "Ready for your first issue" : "No authorized repositories yet"}
      description={hasRepositories ? (demo ? "Send a signed issue webhook or run make smoke to see an issue here." : "Issues synchronized from GitHub or received through your webhook will appear here.") : (demo ? "Run make seed to connect the local demo repository." : "Connect a public repository to bring its issues into your workspace.")}>
      {!hasRepositories && !demo && <a className="button" href="#github-account" onClick={() => { const details = document.querySelector<HTMLDetailsElement>("#github-account details"); if (details) details.open = true; }}>Connect a repository <Icon name="arrow" width="16" height="16" /></a>}
    </EmptyState>;
  }
  return <ul className="issue-list" aria-label="Repository issues">{page.items.map(issue => <li key={issue.id} className="issue-row">
    <span className={`issue-state-icon ${issue.state === "open" ? "is-open" : "is-closed"}`} aria-hidden="true"><span /></span>
    <div className="issue-main"><div className="issue-meta">{repositoryName && <span className="issue-repo"><Icon name="repository" width="14" height="14" />{repositoryName}</span>}<span className="issue-number">#{issue.number}</span></div>
      <p className="issue-title">{issue.title}</p>
      {Array.isArray(issue.labels) && issue.labels.length > 0 && <div className="issue-labels">{issue.labels.filter(label => typeof label === "string").slice(0, 20).map((label, index) => <span className="issue-label" data-color={index % 3} key={`${label}-${index}`}>{label}</span>)}</div>}
      <div className="issue-submeta"><StatusBadge tone={issue.state === "open" ? "good" : "neutral"}>{issue.state}</StatusBadge><span>Ingestion: {issue.ingestion_status}</span><time dateTime={issue.updated_at} suppressHydrationWarning>{relativeTime(issue.updated_at)}</time></div>
    </div>
    {onSelectIssue && <button className="issue-action" onClick={() => onSelectIssue(issue.number)} aria-label={`Investigate issue #${issue.number}`}>Investigate <Icon name="arrow" width="16" height="16" /></button>}
  </li>)}</ul>;
}
