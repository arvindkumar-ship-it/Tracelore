"use client";
import Link from "next/link";
import { useState } from "react";
import { skipToken, useQuery } from "@tanstack/react-query";
import { request } from "@/lib/api";
import { incidentPage } from "@/lib/schemas";
import type { components } from "@/lib/generated";
import { duration, percent } from "@/lib/format";
import { IncidentTable } from "@/components/IncidentTable";
import { PageHeading, QueryState } from "@/components/QueryState";
import { Icon, type IconName } from "@/components/Icon";

export default function IncidentsPage() {
  const [status, setStatus] = useState(""),
    [cursor, setCursor] = useState<string | null>(null),
    [search, setSearch] = useState("");
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
    queryFn: skipToken,
  });
  const { data: connected = false } = useQuery<boolean>({
    queryKey: ["live-connection"],
    queryFn: skipToken,
  });
  const items = query.data?.items ?? [];
  const visible = items.filter((item) =>
    `${item.services.join(" ")} ${item.id}`
      .toLowerCase()
      .includes(search.trim().toLowerCase()),
  );
  const metrics: {
    label: string;
    value: string;
    foot: string;
    icon: IconName;
  }[] = [
    {
      label: "Event throughput",
      value: live ? `${live.events_per_sec.toFixed(0)}` : "—",
      foot: "Events / second",
      icon: "activity",
    },
    {
      label: "Request error rate",
      value: live ? percent(live.error_rate) : "—",
      foot: "Server spans · last 10 seconds",
      icon: "incidents",
    },
    {
      label: "Open in this view",
      value: query.data
        ? String(items.filter((item) => item.status === "open").length)
        : "—",
      foot: "Grouped, deduplicated signals",
      icon: "layers",
    },
    {
      label: "Observed services",
      value: live ? String(Object.keys(live.per_service).length) : "—",
      foot: "Active in the last 10 seconds",
      icon: "server",
    },
  ];
  return (
    <>
      <PageHeading
        eyebrow="System observatory"
        title="Incidents"
        description="A clear view of what changed, where it started, and what needs your attention."
        action={
          <Link className="button secondary" href="/settings#sdk-setup">
            <Icon name="plus" size={16} />
            Connect a service
          </Link>
        }
      />
      <div className="metrics">
        {metrics.map(({ label, value, foot, icon }) => (
          <div className="metric" key={label}>
            <div className="metric-label">
              {label}
              <Icon name={icon} size={16} />
            </div>
            <div className="metric-value">{value}</div>
            <div className="metric-foot">{foot}</div>
          </div>
        ))}
      </div>
      <div className="overview-grid">
        <section className="panel panel-flush incident-panel">
          <div className="panel-head">
            <div>
              <h2>
                Incident stream <span className="count">{items.length}</span>
              </h2>
              <p>Evidence-backed deviations across your system.</p>
            </div>
            <button
              className="icon-button"
              aria-label="Refresh incidents"
              title="Refresh incidents"
              disabled={query.isFetching}
              onClick={() => void query.refetch()}
            >
              <Icon name="refresh" size={17} />
            </button>
          </div>
          <div className="table-toolbar">
            <div className="search-field">
              <Icon name="search" size={16} />
              <input
                aria-label="Search incidents in this page"
                placeholder="Search service or incident…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
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
          <div className="table-query">
            <QueryState
              loading={query.isPending}
              error={query.error}
              retry={() => void query.refetch()}
            />
          </div>
          {query.data &&
            (visible.length ? (
              <IncidentTable items={visible} />
            ) : (
              <div className="empty">
                <span className="empty-icon">
                  <Icon
                    name={search || status ? "search" : "activity"}
                    size={24}
                  />
                </span>
                <h3>
                  {search || status
                    ? "No matching incidents"
                    : "All quiet, so far."}
                </h3>
                <p>
                  {search || status
                    ? "Try another service name or clear the filters to see more of this incident stream."
                    : "Incidents appear here when recorded evidence supports a deviation. Connect a service to start building its normal history."}
                </p>
                {search || status ? (
                  <button
                    className="secondary"
                    onClick={() => {
                      setSearch("");
                      setStatus("");
                      setCursor(null);
                    }}
                  >
                    Clear filters
                  </button>
                ) : (
                  <Link className="button secondary" href="/settings#sdk-setup">
                    Connect your first service
                    <Icon name="arrow" size={15} />
                  </Link>
                )}
              </div>
            ))}
          <div className="table-footer">
            <span>
              {query.data
                ? `${visible.length} ${visible.length === 1 ? "incident" : "incidents"} in this page`
                : "Loading incident stream"}
            </span>
            <div className="actions">
              {cursor && (
                <button className="text-button" onClick={() => setCursor(null)}>
                  <Icon name="arrowLeft" size={14} />
                  Newest
                </button>
              )}
              {query.data?.next_cursor && (
                <button
                  className="secondary compact"
                  onClick={() => setCursor(query.data!.next_cursor)}
                >
                  Next page
                  <Icon name="arrow" size={14} />
                </button>
              )}
            </div>
          </div>
        </section>
        <section className="panel panel-flush service-panel">
          <div className="panel-head">
            <div>
              <h2>Service activity</h2>
              <p>Rolling 10-second window</p>
            </div>
            <span
              className={`status-dot ${connected ? "is-live" : ""}`}
              role="img"
              aria-label={connected ? "Live data" : "Waiting for connection"}
            />
          </div>
          <div className="service-list">
            {live && Object.entries(live.per_service).length ? (
              Object.entries(live.per_service).map(([name, service]) => (
                <div className="service-item" key={name}>
                  <div className="service-title">
                    <span className="service-icon">
                      <Icon name="server" size={15} />
                    </span>
                    <strong>{name}</strong>
                    <span
                      className={`badge ${service.errors ? "amber" : "green"}`}
                    >
                      {service.errors
                        ? `${service.errors} errors`
                        : "No errors"}
                    </span>
                  </div>
                  <div className="service-meta">
                    <span>{service.count.toLocaleString()} events</span>
                    <span>
                      p95 <b>{duration(service.p95_ms)}</b>
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="service-empty">
                <Icon name="server" size={22} />
                <h3>
                  {connected
                    ? "Waiting for service events"
                    : "Waiting for live data"}
                </h3>
                <p>
                  Service traffic and latency appear here when telemetry
                  arrives.
                </p>
              </div>
            )}
          </div>
          <Link className="section-link" href="/graph">
            Explore dependencies
            <Icon name="arrow" size={15} />
          </Link>
        </section>
      </div>
      <div className="page-note">
        <Icon name="info" size={16} />
        <p>
          Detection starts after an endpoint has 24 hours of clean history. A
          quiet view can also mean a service is still warming up.
        </p>
      </div>
    </>
  );
}