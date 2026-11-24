"use client";

import Link from "next/link";
import { useEffect, useReducer, useRef, useState } from "react";
import { StatusBadge } from "./status-badge";

type Section = "inbox" | "repositories" | "code-search";
type MenuAction = "toggle" | "close";

export function mobileMenuReducer(open: boolean, action: MenuAction): boolean {
  return action === "toggle" ? !open : false;
}

export function sectionForHash(hash: string): Section {
  if (hash === "#repositories" || hash === "#github-account") return "repositories";
  return hash === "#code-search" ? "code-search" : "inbox";
}

type SectionMarker = { section: Section; top: number };

export function sectionForViewport(markers: SectionMarker[], activationLine: number, viewportHeight: number, atBottom: boolean): Section {
  let section: Section = "inbox";
  for (const marker of markers) {
    if (marker.top <= activationLine) section = marker.section;
  }
  const last = markers[markers.length - 1];
  return atBottom && last && last.top < viewportHeight ? last.section : section;
}

function NavIcon({ section }: { section: Section }) {
  return <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    {section === "inbox" ? <><rect x="4" y="4" width="16" height="16" rx="3" /><path d="M4 14h5l1.5 2h3L15 14h5" /></> :
      section === "repositories" ? <><path d="M4 7a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" /></> :
        <><path d="m8 8-4 4 4 4M16 8l4 4-4 4M14 5l-4 14" /></>}
  </svg>;
}

export function NavigationLinks({ active, demo, onNavigate }: { active: Section; demo: boolean; onNavigate: (section: Section) => void }) {
  const items: { id: Section; href: string; label: string }[] = [
    { id: "inbox", href: "#inbox", label: "Issue Inbox" },
    { id: "repositories", href: demo ? "#repositories" : "#github-account", label: "Repositories" },
    ...(!demo ? [{ id: "code-search" as const, href: "#code-search", label: "Code Search" }] : []),
  ];
  return <>{items.map(item => <a key={item.id} href={item.href} className="topbar-link"
    aria-current={active === item.id ? "page" : undefined} onClick={() => onNavigate(item.id)}>
    <NavIcon section={item.id} /><span>{item.label}</span>
  </a>)}</>;
}

export function TopNavigation({ demo, ready, accountRef }: { demo: boolean; ready: boolean | null; accountRef: (node: HTMLDivElement | null) => void }) {
  const [open, dispatch] = useReducer(mobileMenuReducer, false);
  const [active, setActive] = useState<Section>("inbox");
  const menuButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    let live = true;
    let frame: number | null = null;
    const updateFromScroll = () => {
      frame = null;
      if (!live) return;
      const anchors: { id: string; section: Section }[] = [
        { id: "inbox", section: "inbox" },
        { id: "github-account", section: "repositories" },
        { id: "repositories", section: "repositories" },
        { id: "code-search", section: "code-search" },
      ];
      const markers: SectionMarker[] = [];
      for (const anchor of anchors) {
        const rect = document.getElementById(anchor.id)?.getBoundingClientRect();
        if (rect && rect.width > 0 && rect.height > 0) markers.push({ section: anchor.section, top: rect.top });
      }
      const headerBottom = document.querySelector(".topbar")?.getBoundingClientRect().bottom ?? 0;
      const scrollRoot = document.scrollingElement ?? document.documentElement;
      const atBottom = window.scrollY > 0 && scrollRoot.scrollHeight - window.innerHeight - window.scrollY <= 2;
      setActive(sectionForViewport(markers, headerBottom + 32, window.innerHeight, atBottom));
    };
    const schedule = () => {
      if (live && frame === null) frame = window.requestAnimationFrame(updateFromScroll);
    };
    const sync = () => { if (live) { setActive(sectionForHash(window.location.hash)); schedule(); } };
    queueMicrotask(sync);
    window.addEventListener("hashchange", sync);
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    const main = document.querySelector("main");
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(schedule);
    if (main) observer?.observe(main);
    return () => {
      live = false;
      window.removeEventListener("hashchange", sync);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      if (frame !== null) window.cancelAnimationFrame(frame);
      observer?.disconnect();
    };
  }, []);
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { dispatch("close"); menuButton.current?.focus(); }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);
  const navigate = (section: Section) => {
    setActive(section);
    dispatch("close");
    if (section === "repositories" && !demo) {
      const details = document.querySelector<HTMLDetailsElement>("#github-account details");
      if (details) details.open = true;
      else {
        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        document.getElementById("repositories")?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth" });
      }
    }
  };
  const status = ready === null ? "Checking system" : ready ? "API & storage ready" : "System unavailable";
  const statusDetail = ready === null ? "Checking API and storage availability." : ready ? "The API and storage are responding." : "The API or storage is not responding.";
  return <header className="topbar">
    <div className="topbar-inner">
      <Link href="/" className="topbar-brand" aria-label="RepoPilot home" onClick={() => { setActive("inbox"); dispatch("close"); }}>
        <span className="topbar-logo" aria-hidden="true"><span /><span /><span /><span /></span><span>RepoPilot<span className="brand-period">.</span></span>
      </Link>
      <nav id="primary-navigation" aria-label="Main navigation" className="topbar-nav" data-open={open}>
        <NavigationLinks active={active} demo={demo} onNavigate={navigate} />
      </nav>
      <div className="topbar-controls">
        <span className="topbar-status" role="status" tabIndex={0} aria-label={`${status}. ${statusDetail}`} data-tooltip={statusDetail}><StatusBadge tone={ready === null ? "warn" : ready ? "good" : "danger"}><span className="topbar-status-label">{status}</span></StatusBadge></span>
        <div className="topbar-account" ref={accountRef} />
        <button ref={menuButton} type="button" className="topbar-menu-button" aria-label={open ? "Close navigation menu" : "Open navigation menu"}
          aria-expanded={open} aria-controls="primary-navigation" onClick={() => dispatch("toggle")}>
          <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            {open ? <path d="M6 6l12 12M18 6 6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
          </svg>
        </button>
      </div>
    </div>
  </header>;
}
