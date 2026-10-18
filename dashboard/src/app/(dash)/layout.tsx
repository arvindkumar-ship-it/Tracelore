"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { token } from "@/lib/api";
import { Login } from "@/components/Login";
import { Brand } from "@/components/Brand";
import { Icon, type IconName } from "@/components/Icon";
import { useLive } from "@/lib/ws";

const links: { href: string; icon: IconName; label: string }[] = [
  { href: "/incidents", icon: "activity", label: "Incidents" },
  { href: "/state", icon: "clock", label: "Observed state" },
  { href: "/graph", icon: "graph", label: "Dependencies" },
  { href: "/counterfactual", icon: "flask", label: "What-if lab" },
  { href: "/settings", icon: "settings", label: "Settings" },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [ready, setReady] = useState(false),
    [authenticated, setAuthenticated] = useState(false);
  useEffect(() => {
    const expired = () => setAuthenticated(false);
    window.addEventListener("tracelore:unauthorized", expired);
    setAuthenticated(Boolean(token()));
    setReady(true);
    return () => window.removeEventListener("tracelore:unauthorized", expired);
  }, []);
  if (!ready)
    return (
      <div className="loading" role="status">
        <Brand />
        <span>Opening your observatory…</span>
      </div>
    );
  if (!authenticated) return <Login onSuccess={() => setAuthenticated(true)} />;
  return (
    <Shell
      onSignOut={() => {
        sessionStorage.removeItem("tracelore.token");
        setAuthenticated(false);
      }}
    >
      {children}
    </Shell>
  );
}

function Shell({
  children,
  onSignOut,
}: {
  children: React.ReactNode;
  onSignOut: () => void;
}) {
  const pathname = usePathname(),
    { connected } = useLive();
  const [mobileOpen, setMobileOpen] = useState(false);
  const sidebar = useRef<HTMLElement>(null),
    menuButton = useRef<HTMLButtonElement>(null);
  const current = links.find(({ href }) => pathname.startsWith(href));
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);
  useEffect(() => {
    if (!mobileOpen) return;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const controls = () =>
      Array.from(
        sidebar.current?.querySelectorAll<HTMLElement>(
          "a[href], button:not([disabled])",
        ) ?? [],
      ).filter((element) => element.getClientRects().length);
    controls()[0]?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileOpen(false);
        return;
      }
      if (event.key !== "Tab") return;
      const items = controls(),
        first = items[0],
        last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    const resize = () => {
      if (window.innerWidth > 800) setMobileOpen(false);
    };
    window.addEventListener("keydown", keydown);
    window.addEventListener("resize", resize);
    return () => {
      document.body.style.overflow = oldOverflow;
      window.removeEventListener("keydown", keydown);
      window.removeEventListener("resize", resize);
      menuButton.current?.focus();
    };
  }, [mobileOpen]);
  return (
    <div className="shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {mobileOpen && (
        <button
          className="sidebar-backdrop"
          tabIndex={-1}
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside
        ref={sidebar}
        id="workspace-navigation"
        className={`sidebar ${mobileOpen ? "is-open" : ""}`}
        role={mobileOpen ? "dialog" : undefined}
        aria-modal={mobileOpen || undefined}
        aria-label="Workspace navigation"
      >
        <div className="sidebar-brand">
          <Link href="/incidents" aria-label="Tracelore home">
            <Brand />
          </Link>
          <button
            className="icon-button mobile-close"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          >
            <Icon name="close" />
          </button>
        </div>
        <div className="workspace-card">
          <span className="workspace-icon">
            <Icon name="layers" />
          </span>
          <div>
            <strong>System observatory</strong>
            <span>Your workspace</span>
          </div>
          <span className="workspace-initial">T</span>
        </div>
        <div className="nav-label">Workspace</div>
        <nav aria-label="Main navigation">
          {links.slice(0, 3).map(({ href, icon, label }) => (
            <Link
              key={href}
              href={href}
              aria-current={pathname.startsWith(href) ? "page" : undefined}
            >
              <Icon name={icon} />
              {label}
              <span className="nav-active-dot" />
            </Link>
          ))}
        </nav>
        <div className="nav-label nav-label-second">Investigate</div>
        <nav aria-label="Investigation">
          <Link
            href="/counterfactual"
            aria-current={
              pathname.startsWith("/counterfactual") ? "page" : undefined
            }
          >
            <Icon name="flask" />
            What-if lab
            <span className="nav-active-dot" />
          </Link>
        </nav>
        <div className="aside-bottom">
          <div className="sidebar-guide">
            <Icon name="layers" size={20} />
            <strong>Every event tells a story.</strong>
            <p>Connect your services to see the full picture.</p>
            <Link href="/settings#sdk-setup">
              Set up instrumentation
              <Icon name="arrow" size={15} />
            </Link>
          </div>
          <nav aria-label="Workspace settings">
            <Link
              href="/settings"
              aria-current={
                pathname.startsWith("/settings") ? "page" : undefined
              }
            >
              <Icon name="settings" />
              Settings
              <span className="nav-active-dot" />
            </Link>
          </nav>
          <div className="sidebar-account">
            <span className="avatar">T</span>
            <div>
              <strong>Dashboard access</strong>
              <span>Current tab session</span>
            </div>
            <button
              className="icon-button"
              onClick={onSignOut}
              aria-label="Sign out"
              title="Sign out"
            >
              <Icon name="logout" size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              ref={menuButton}
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              aria-expanded={mobileOpen}
              aria-controls="workspace-navigation"
              onClick={() => setMobileOpen(true)}
            >
              <Icon name="menu" />
            </button>
            <span className="breadcrumb-workspace">Workspace</span>
            <Icon name="chevron" size={13} />
            <span className="breadcrumb-current">
              {current?.label ?? "Trace explorer"}
            </span>
            {pathname.startsWith("/incidents/") && (
              <>
                <Icon name="chevron" size={13} />
                <span className="breadcrumb-detail">Investigation</span>
              </>
            )}
          </div>
          <div className="topbar-meta">
            <span
              className={`connection ${connected ? "connected" : ""}`}
              role="status"
            >
              <span className="status-dot" />
              {connected ? "Live connection" : "Reconnecting"}
            </span>
            <span className="timezone">UTC</span>
            <span className="avatar small" aria-hidden="true">
              T
            </span>
          </div>
        </header>
        <main id="main-content" tabIndex={-1}>
          {children}
        </main>
        <footer className="app-footer">
          <span>
            Tracelore <span className="footer-version">v0.1.0</span>
          </span>
          <span>
            <Icon name="shield" size={13} />
            Evidence grounded. Replayable by design.
          </span>
        </footer>
      </div>
    </div>
  );
}
