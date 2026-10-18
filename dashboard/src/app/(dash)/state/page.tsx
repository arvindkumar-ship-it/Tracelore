"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { request } from "@/lib/api";
import { stateView } from "@/lib/schemas";
import { StateInspector } from "@/components/StateInspector";
import { PageHeading, QueryState } from "@/components/QueryState";
export default function StatePage() {
  const [at, setAt] = useState(""),
    [queryAt, setQueryAt] = useState("");
  const query = useQuery({
    queryKey: ["state", queryAt],
    enabled: Boolean(queryAt),
    queryFn: () =>
      request(
        `/replay/state?at=${encodeURIComponent(new Date(queryAt).toISOString())}`,
        stateView,
      ),
  });
  return (
    <>
      <PageHeading
        eyebrow="02 / TIME TRAVEL"
        title="A system, at a moment."
        description="Fold recorded events in canonical order to reconstruct the observed view."
      />
      <form
        className="panel"
        onSubmit={(event) => {
          event.preventDefault();
          setQueryAt(at);
        }}
      >
        <label>
          Point in time (your local timezone)
          <input
            type="datetime-local"
            required
            value={at}
            onChange={(event) => setAt(event.target.value)}
          />
        </label>
        <button>Reconstruct observed state →</button>
      </form>
      <QueryState
        loading={query.isFetching}
        error={query.error}
        retry={() => void query.refetch()}
      />
      <StateInspector value={query.data} />
    </>
  );
}
