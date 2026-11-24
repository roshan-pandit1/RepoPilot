export function StatusBadge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "good" | "warn" | "danger" | "neutral" }) {
  return <span className="status-badge" data-tone={tone}><span className="status-dot" aria-hidden="true" />{children}</span>;
}
