"use client";
import { useQuery } from "@tanstack/react-query";
import { request } from "@/lib/api";
import { graphView } from "@/lib/schemas";
import { CausalGraph } from "@/components/CausalGraph";
import { PageHeading, QueryState } from "@/components/QueryState";
export default function GraphPage() {
  const query = useQuery({
    queryKey: ["graph"],
    queryFn: () => request("/graph", graphView),
    refetchInterval: 30_000,
  });
  return (
    <>
      <PageHeading
        eyebrow="03 / DEPENDENCY MAP"
        title="See the propagation path."
        description="Calls point from a service to its dependency. Failure can propagate in the reverse direction."
      />
      <QueryState
        loading={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {query.data?.nodes.length ? (
        <CausalGraph value={query.data} />
      ) : (
        query.data && (
          <section className="panel empty">
            <h2>Your dependency map starts with a call.</h2>
            <p>
              Instrument outgoing HTTP, database, cache and queue operations to
              populate this graph.
            </p>
          </section>
        )
      )}
      <div className="notice">
        ! marks affected services. A green ring marks a root candidate. Granger
        support strengthens an explanation; it does not prove causality.
      </div>
    </>
  );
}
