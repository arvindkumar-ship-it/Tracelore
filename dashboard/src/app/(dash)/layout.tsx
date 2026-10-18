"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { token } from "@/lib/api";
import { Login } from "@/components/Login";
import { useLive } from "@/lib/ws";

const links = [
  ["/incidents", "01", "Incidents"],
  ["/state", "02", "Observed state"],
  ["/graph", "03", "Dependencies"],
  ["/counterfactual", "04", "What-if lab"],
  ["/settings", "05", "Settings"],
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
  if (!ready) return <div className="loading">Opening observatory…</div>;
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
  return (
    <div className="shell">
      <aside>
        <Link href="/incidents" className="brand">
          <span className="orbit">◉</span> tracelore
        </Link>
        <div className="workspace">
          <span className="status-dot" /> SYSTEM OBSERVATORY
        </div>
        <nav aria-label="Main navigation">
          {links.map(([href, number, label]) => (
            <Link
              key={href}
              href={href}
              aria-current={pathname.startsWith(href) ? "page" : undefined}
            >
              <span>{number}</span>
              {label}
            </Link>
          ))}
        </nav>
        <div className="aside-bottom">
          <span className={`badge ${connected ? "green" : ""}`}>
            {connected ? "● LIVE CONNECTION" : "○ RECONNECTING"}
          </span>
          <p>
            Recorded facts.
            <br />
            Repeatable answers.
          </p>
          <button className="ghost" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      </aside>
      <div className="main">
        <header>
          <span>
            WORKSPACE <b>/</b>{" "}
            {links.find(([href]) => pathname.startsWith(href))?.[2] ?? "Trace"}
          </span>
          <span className="mono subtle">v0.1.0 · UTC</span>
        </header>
        <main>{children}</main>
        <footer>
          TRACELORE{" "}
          <span>Observed state · Evidence grounded · Deterministic replay</span>
        </footer>
      </div>
    </div>
  );
}
