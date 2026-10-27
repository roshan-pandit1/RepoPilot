export function StatusBadge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "good" | "warn" | "neutral" }) {
  const colors = { good: "bg-emerald-50 text-emerald-800 border-emerald-200", warn: "bg-amber-50 text-amber-900 border-amber-200", neutral: "bg-slate-100 text-slate-600 border-slate-200" };
  return <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${colors[tone]}`}><span aria-hidden="true">●</span>{children}</span>;
}
