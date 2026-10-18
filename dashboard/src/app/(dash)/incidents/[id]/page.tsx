"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "@/lib/api";
import { incident, rcaView } from "@/lib/schemas";
import { percent } from "@/lib/format";
import { PageHeading, QueryState } from "@/components/QueryState";
import { EvidenceList } from "@/components/EvidenceList";
import { TraceExplorer } from "@/components/TraceExplorer";
export default function IncidentDetail() {
  const { id } = useParams<{ id: string }>(),
    client = useQueryClient();
  const detail = useQuery({
    queryKey: ["incidents", id],
    queryFn: () => request(`/incidents/${id}`, incident),
  });
  const rca = useQuery({
    queryKey: ["rca", id],
    queryFn: () => request(`/incidents/${id}/rca`, rcaView),
    refetchInterval: 15_000,
  });
  const [trace, setTrace] = useState(""),
    [event, setEvent] = useState(""),
    [showResolve, setShowResolve] = useState(false);
  const [node, setNode] = useState(""),
    [cause, setCause] = useState(""),
    [resolution, setResolution] = useState("");
  useEffect(() => {
    if (trace) return;
    const event = rca.data?.bundle.evidence.find(
      (item) => typeof item.data.trace_id === "string",
    );
    const traceId =
      event?.data.trace_id ??
      detail.data?.signals.find((signal) => signal.trace_id)?.trace_id;
    if (typeof traceId === "string") setTrace(traceId);
  }, [rca.data, detail.data, trace]);
  const resolve = useMutation({
    mutationFn: () =>
      request(`/incidents/${id}/resolve`, incident, {
        method: "POST",
        body: JSON.stringify({
          root_cause_node: node,
          root_cause: cause,
          resolution,
        }),
      }),
    onSuccess: () => {
      setShowResolve(false);
      void client.invalidateQueries({ queryKey: ["incidents"] });
    },
  });
  if (!detail.data)
    return (
      <QueryState
        loading={detail.isPending}
        error={detail.error}
        retry={() => void detail.refetch()}
      />
    );
  const item = detail.data;
  return (
    <>
      <Link className="subtle" href="/incidents">
        ← Incident stream
      </Link>
      <PageHeading
        eyebrow={`INC-${id.slice(0, 8).toUpperCase()} / ${item.status.toUpperCase()}`}
        title={item.services.join(" → ")}
        description={`First deviation: ${new Date(item.start_time).toUTCString()} · ${percent(item.confidence)} signal confidence`}
        action={
          <div className="actions">
            <Link href={`/counterfactual?incident=${id}`}>
              <button>Test a fix →</button>
            </Link>
            {item.status === "open" && (
              <button
                className="ghost"
                onClick={() => setShowResolve((value) => !value)}
              >
                Resolve
              </button>
            )}
          </div>
        }
      />
      {showResolve && (
        <form
          className="panel"
          onSubmit={(event) => {
            event.preventDefault();
            resolve.mutate();
          }}
        >
          <h2>Record the verified resolution</h2>
          <div className="form-grid">
            <label>
              Root cause node
              <input
                required
                value={node}
                placeholder="db:inventory"
                onChange={(event) => setNode(event.target.value)}
              />
            </label>
            <label>
              Root cause
              <input
                required
                value={cause}
                onChange={(event) => setCause(event.target.value)}
              />
            </label>
          </div>
          <label>
            Resolution
            <textarea
              required
              value={resolution}
              onChange={(event) => setResolution(event.target.value)}
            />
          </label>
          <button disabled={resolve.isPending}>Save resolution</button>
          {resolve.error && <p className="error">{resolve.error.message}</p>}
        </form>
      )}
      <div className="grid-two">
        <section className="panel">
          <div className="actions" style={{ justifyContent: "space-between" }}>
            <h2>Root-cause assessment</h2>
            <span className="badge cyan">
              SOURCE: {rca.data?.source.toUpperCase() ?? "PENDING"}
            </span>
          </div>
          {rca.data ? (
            <>
              <h2
                className="mono"
                style={{ color: "var(--lime)", marginTop: 24 }}
              >
                {rca.data.report.root_cause_node || "Insufficient evidence"}
              </h2>
              <p>{rca.data.report.mechanism}</p>
              <div className="notice">{rca.data.report.suggested_fix}</div>
              {rca.data.report.insufficient_evidence && (
                <p className="error">
                  Evidence is incomplete. This ranking needs further
                  investigation.
                </p>
              )}
            </>
          ) : (
            <p>
              Analysis runs after the incident has collected evidence for 60
              seconds.
            </p>
          )}
          <QueryState error={rca.error} retry={() => void rca.refetch()} />
        </section>
        <section className="panel">
          <h2>Evidence ledger</h2>
          {rca.data ? (
            <EvidenceList
              value={rca.data}
              onSelect={(trace, event) => {
                setTrace(trace);
                setEvent(event);
              }}
            />
          ) : (
            <p>Grounded evidence appears here when analysis completes.</p>
          )}
        </section>
      </div>
      {trace ? (
        <TraceExplorer traceId={trace} jumpEvent={event} />
      ) : (
        <section className="panel">
          <h2>Trace timeline</h2>
          <p>
            Select a concrete event from the evidence ledger to inspect its
            trace.
          </p>
        </section>
      )}
    </>
  );
}
