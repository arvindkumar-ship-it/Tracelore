"use client";
import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "@/lib/api";
import { stateView, traceView } from "@/lib/schemas";
import { Icon } from "./Icon";
import { QueryState } from "./QueryState";
import { StateInspector } from "./StateInspector";
import { TimelineCanvas } from "./timeline/TimelineCanvas";
import { ScrubBar } from "./timeline/ScrubBar";

export function TraceExplorer({
  traceId,
  jumpEvent,
}: {
  traceId: string;
  jumpEvent?: string;
}) {
  const query = useQuery({
    queryKey: ["trace", traceId],
    queryFn: () => request(`/replay/trace/${traceId}`, traceView),
  });
  const [selected, setSelected] = useState(""),
    [debounced, setDebounced] = useState("");
  const client = useQueryClient(),
    trace = query.data;
  const order = useMemo(
    () =>
      trace
        ? trace.spans.event_id
            .map((id, index) => ({ id, index }))
            .sort(
              (a, b) =>
                trace.spans.start_us[a.index] +
                  trace.spans.dur_us[a.index] -
                  trace.spans.start_us[b.index] -
                  trace.spans.dur_us[b.index] || a.index - b.index,
            )
        : [],
    [trace],
  );
  useEffect(() => {
    if (jumpEvent) setSelected(jumpEvent);
    else if (order.length) setSelected(order[0].id);
  }, [jumpEvent, order]);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(selected), 50);
    return () => clearTimeout(timer);
  }, [selected]);
  const state = useQuery({
    queryKey: ["trace-state", traceId, debounced],
    enabled: Boolean(debounced),
    queryFn: () =>
      request(
        `/replay/trace/${traceId}/state?event_id=${debounced}`,
        stateView,
      ),
    placeholderData: (previous) => previous,
  });
  const index = Math.max(
    0,
    order.findIndex((event) => event.id === selected),
  );
  useEffect(() => {
    for (const nearby of [order[index - 1], order[index + 1]])
      if (nearby)
        void client.prefetchQuery({
          queryKey: ["trace-state", traceId, nearby.id],
          queryFn: () =>
            request(
              `/replay/trace/${traceId}/state?event_id=${nearby.id}`,
              stateView,
            ),
        });
  }, [index, order, client, traceId]);
  if (!trace)
    return (
      <QueryState
        loading={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
    );
  return (
    <>
      <section className="panel trace-panel">
        <div className="section-heading">
          <div className="section-title">
            <Icon name="activity" size={17} />
            <h2>Trace timeline</h2>
            <span className="count">
              {trace.spans.id.length.toLocaleString()} spans
            </span>
          </div>
          <span className="badge">Deterministic replay</span>
        </div>
        {trace.spans.id.length ? (
          <>
            <TimelineCanvas
              trace={trace}
              selected={selected}
              onSelect={setSelected}
            />
            <ScrubBar
              count={order.length}
              index={index}
              onChange={(next) => {
                if (order[next]) setSelected(order[next].id);
              }}
            />
            <div className="trace-event-id mono">event {selected}</div>
          </>
        ) : (
          <div className="empty">
            <span className="empty-icon">
              <Icon name="activity" size={23} />
            </span>
            <h3>No spans in this trace</h3>
            <p>This trace has no recorded spans to replay.</p>
          </div>
        )}
      </section>
      <QueryState error={state.error} retry={() => void state.refetch()} />
      <StateInspector value={state.data} />
    </>
  );
}
