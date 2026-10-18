"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { request } from "@/lib/api";
import { incidentPage } from "@/lib/schemas";
import type { components } from "@/lib/generated";
import { percent } from "@/lib/format";
import { IncidentTable } from "@/components/IncidentTable";
import { PageHeading, QueryState } from "@/components/QueryState";
export default function IncidentsPage() {
  const [status, setStatus] = useState(""),
    [cursor, setCursor] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["incidents", "list", status, cursor],
    queryFn: () =>
      request(
        `/incidents?limit=50${status ? `&status=${status}` : ""}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
        incidentPage,
      ),
  });
  const { data: live } = useQuery<components["schemas"]["LiveFrame"]>({
    queryKey: ["live"],
    enabled: false,
  });
  const items = query.data?.items ?? [];
  const { data: connected = false } = useQuery<boolean>({
    queryKey: ["live-connection"],
    enabled: false,
  });
  return (
    <>
      <PageHeading
        eyebrow="01 / SIGNAL INTELLIGENCE"
        title="Incidents, in focus."
        description="Find the first deviation. Follow its path through your system."
        action={
          <span className={`badge ${connected ? "green" : ""}`}>
            {connected ? "LIVE CONNECTION" : "WAITING FOR LIVE DATA"}
          </span>
        }
      />
      <div className="metrics">
        {[
          [
            "Event throughput",
            live ? `${live.events_per_sec.toFixed(0)}/s` : "—",
            "Ingested over the last 10 seconds",
          ],
          [
            "Request error rate",
            live ? percent(live.error_rate) : "—",
            "Server spans · rolling 10 seconds",
          ],
          [
            "Open in this view",
            String(items.filter((item) => item.status === "open").length),
            "Grouped, deduplicated signals",
          ],
          [
            "Observed services",
            live ? String(Object.keys(live.per_service).length) : "—",
            "Active over the last 10 seconds",
          ],
        ].map(([label, value, foot]) => (
          <div className="metric" key={label}>
            <div className="metric-label">{label}</div>
            <div className="metric-value">{value}</div>
            <div className="metric-foot">{foot}</div>
          </div>
        ))}
      </div>
      <QueryState
        loading={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {query.data && (
        <section className="panel panel-flush">
          <div className="panel-head">
            <h2>
              Incident stream{" "}
              <span className="subtle mono"> / {items.length}</span>
            </h2>
            <div className="filters">
              <select
                aria-label="Filter incident status"
                value={status}
                onChange={(event) => {
                  setStatus(event.target.value);
                  setCursor(null);
                }}
              >
                <option value="">All statuses</option>
                <option value="open">Open</option>
                <option value="resolved">Resolved</option>
              </select>
            </div>
          </div>
          {items.length ? (
            <IncidentTable items={items} />
          ) : (
            <div className="empty">
              <div className="orbit">◉</div>
              <h2>All quiet, so far.</h2>
              <p>
                Connect a service and train its normal history. Incidents appear
                here when recorded evidence supports a deviation.
              </p>
              <Link href="/settings">
                <button>Connect your first service →</button>
              </Link>
            </div>
          )}
          {query.data.next_cursor && (
            <div style={{ padding: 20 }}>
              <button
                className="ghost"
                onClick={() => setCursor(query.data!.next_cursor)}
              >
                Next page →
              </button>
            </div>
          )}
          {cursor && (
            <div style={{ padding: 20 }}>
              <button className="ghost" onClick={() => setCursor(null)}>
                ← Newest incidents
              </button>
            </div>
          )}
        </section>
      )}
      <div className="notice">
        Detection starts after an endpoint has at least 24 hours of clean
        history. A quiet view can also mean a service is warming up; check the
        pipeline metrics.
      </div>
    </>
  );
}
