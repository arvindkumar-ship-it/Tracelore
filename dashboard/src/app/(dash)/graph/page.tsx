"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { request } from "@/lib/api";
import { graphView } from "@/lib/schemas";
import { CausalGraph } from "@/components/CausalGraph";
import { PageHeading, QueryState } from "@/components/QueryState";
import { Icon } from "@/components/Icon";
export default function GraphPage() {
  const query = useQuery({
    queryKey: ["graph"],
    queryFn: () => request("/graph", graphView),
    refetchInterval: 30_000,
  });
  return (
    <>
      <PageHeading
        eyebrow="System topology"
        title="Dependencies"
        description="Understand how your services connect, and follow the path of a deviation."
        action={
          <button
            className="secondary"
            disabled={query.isFetching}
            onClick={() => void query.refetch()}
          >
            <Icon name="refresh" size={15} />
            Refresh map
          </button>
        }
      />
      <QueryState
        loading={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {query.data && (
        <section className="panel panel-flush graph-panel">
          <div className="panel-head">
            <div>
              <h2>Dependency map</h2>
              <p>
                {query.data.nodes.length} nodes · {query.data.edges.length}{" "}
                connections · Updates every 30 seconds
              </p>
            </div>
            <div className="graph-legend">
              <span>
                <i />
                Observed
              </span>
              <span>
                <i className="affected" />
                Affected
              </span>
              <span>
                <i className="root" />
                Root candidate
              </span>
            </div>
          </div>
          {query.data.nodes.length ? (
            <CausalGraph value={query.data} />
          ) : (
            <div className="empty">
              <span className="empty-icon">
                <Icon name="graph" size={24} />
              </span>
              <h3>Your map starts with a call</h3>
              <p>
                Instrument outgoing HTTP, database, cache, and queue operations
                to see your dependency paths.
              </p>
              <Link className="button secondary" href="/settings#sdk-setup">
                Set up instrumentation
                <Icon name="arrow" size={15} />
              </Link>
            </div>
          )}
          <div className="graph-footer">
            <span>Calls point from a service to its dependency.</span>
            <span>Drag to pan · Scroll to zoom</span>
          </div>
        </section>
      )}
      <div className="page-note">
        <Icon name="info" size={16} />
        <p>
          Failure can propagate against the direction of a call. A root
          candidate is a possible explanation; Granger support strengthens
          evidence but does not prove causality.
        </p>
      </div>
    </>
  );
}
