"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { request } from "@/lib/api";
import { stateView } from "@/lib/schemas";
import { StateInspector } from "@/components/StateInspector";
import { PageHeading, QueryState } from "@/components/QueryState";
import { Icon } from "@/components/Icon";
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
        eyebrow="Historical replay"
        title="Observed state"
        description="Go back to a moment in time. Reconstruct your system from the events it recorded."
      />
      <form
        className="panel replay-form"
        onSubmit={(event) => {
          event.preventDefault();
          setQueryAt(at);
        }}
      >
        <div className="replay-form-intro">
          <span className="section-icon">
            <Icon name="clock" size={21} />
          </span>
          <div>
            <h2>Choose a point in time</h2>
            <p>Events are replayed in their recorded order.</p>
          </div>
        </div>
        <div className="replay-controls">
          <label>
            Point in time (your local timezone)
            <input
              type="datetime-local"
              required
              value={at}
              onChange={(event) => setAt(event.target.value)}
            />
          </label>
          <button disabled={query.isFetching}>
            {query.isFetching ? "Reconstructing…" : "Reconstruct state"}
            <Icon name="arrow" size={15} />
          </button>
        </div>
      </form>
      <QueryState
        loading={query.isFetching}
        error={query.error}
        retry={() => void query.refetch()}
      />
      <StateInspector value={query.data} context="timestamp" />
      <div className="page-note">
        <Icon name="shield" size={15} />
        <p>
          This view reflects recorded observations. Hashed cache presence and
          queue estimates describe what the system observed at that moment.
        </p>
      </div>
    </>
  );
}
