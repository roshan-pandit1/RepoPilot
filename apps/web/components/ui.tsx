import type { ButtonHTMLAttributes, ReactNode, SVGProps } from "react";

type IconName = "inbox" | "repository" | "clock" | "alert" | "refresh" | "search" | "chevron" | "arrow" | "check" | "code" | "shield" | "queue" | "spark" | "external";

export function Icon({ name, ...props }: SVGProps<SVGSVGElement> & { name: IconName }) {
  const icons: Record<IconName, ReactNode> = {
    inbox: <><path d="M4 4.75h16l1 9.25v4.25a1.75 1.75 0 0 1-1.75 1.75H4.75A1.75 1.75 0 0 1 3 18.25V14z" /><path d="M3 14h5.3a3.7 3.7 0 0 0 7.4 0H21" /></>,
    repository: <><path d="M5 4.5A2.5 2.5 0 0 1 7.5 2H20v17H7.5A2.5 2.5 0 0 0 5 21.5z" /><path d="M5 19a2.5 2.5 0 0 1 2.5-2.5H20M9 6h7" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3.2 2" /></>,
    alert: <><path d="M12 3 2.7 19.2a1 1 0 0 0 .9 1.5h16.8a1 1 0 0 0 .9-1.5z" /><path d="M12 9v4M12 17h.01" /></>,
    refresh: <><path d="M20 7v5h-5M4 17v-5h5" /><path d="M5.4 9a7 7 0 0 1 12-2L20 12M4 12l2.6 5a7 7 0 0 0 12-2" /></>,
    search: <><circle cx="10.75" cy="10.75" r="6.75" /><path d="m16 16 4 4" /></>,
    chevron: <path d="m7 10 5 5 5-5" />,
    arrow: <><path d="M4 12h16M14 6l6 6-6 6" /></>,
    check: <path d="m5 12 4.5 4.5L19 7" />,
    code: <><path d="m8 7-5 5 5 5M16 7l5 5-5 5M14 4l-4 16" /></>,
    shield: <><path d="M12 2.5 20 6v5c0 5-3.2 8.2-8 10.5C7.2 19.2 4 16 4 11V6z" /><path d="m8.5 12 2.4 2.4 4.6-4.8" /></>,
    queue: <><rect x="4" y="4" width="16" height="16" rx="3" /><path d="M8 8h8M8 12h8M8 16h5" /></>,
    spark: <><path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7z" /><path d="m19 16 .6 1.8L21.5 18.5l-1.9.6L19 21l-.6-1.9-1.9-.6 1.9-.7z" /></>,
    external: <><path d="M13 5h6v6M19 5l-8 8" /><path d="M18 13v5H6V6h5" /></>,
  };
  return <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" {...props}>{icons[name]}</svg>;
}

export function GitHubMark(props: SVGProps<SVGSVGElement>) {
  return <svg aria-hidden="true" width="19" height="19" viewBox="0 0 24 24" fill="currentColor" {...props}><path d="M12 .9a11.1 11.1 0 0 0-3.51 21.63c.56.1.76-.24.76-.54v-2.06c-3.1.67-3.75-1.32-3.75-1.32-.5-1.28-1.24-1.62-1.24-1.62-1.01-.69.08-.68.08-.68 1.12.08 1.7 1.15 1.7 1.15.99 1.7 2.6 1.21 3.23.92.1-.72.39-1.21.7-1.49-2.48-.28-5.09-1.24-5.09-5.52 0-1.22.44-2.22 1.15-3-.12-.28-.5-1.42.11-2.95 0 0 .94-.3 3.05 1.14a10.6 10.6 0 0 1 5.55 0c2.12-1.44 3.05-1.14 3.05-1.14.61 1.53.23 2.67.11 2.95.72.78 1.15 1.78 1.15 3.01 0 4.29-2.61 5.23-5.1 5.5.4.35.76 1.02.76 2.07v3.04c0 .3.2.65.77.54A11.1 11.1 0 0 0 12 .9Z" /></svg>;
}

export function Button({ variant = "secondary", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "tertiary" }) {
  return <button className={`button ${variant === "primary" ? "button-primary" : variant === "tertiary" ? "button-tertiary" : ""} ${className}`} {...props} />;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <span aria-hidden="true" className={`skeleton ${className}`} />;
}

export function EmptyState({ icon, title, description, children, alert = false }: { icon: ReactNode; title: string; description: string; children?: ReactNode; alert?: boolean }) {
  return <div className="empty-state" role={alert ? "alert" : undefined}>
    <div className="empty-state-art" aria-hidden="true">{icon}</div>
    <h3>{title}</h3><p>{description}</p>{children}
  </div>;
}
