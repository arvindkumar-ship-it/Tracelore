"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { request } from "@/lib/api";
import { incident, rcaView } from "@/lib/schemas";
import { percent } from "@/lib/format";
import { PageHeading, QueryState } from "@/components/QueryState";
import { Icon } from "@/components/Icon";
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
      <Link className="back-link" href="/incidents">
        <Icon name="arrowLeft" size={14} />
        Incident stream
      </Link>
      <PageHeading
        eyebrow={`INC-${id.slice(0, 8).toUpperCase()}`}
        title={item.services.join(" / ") || "Incident investigation"}
        description={`First deviation · ${new Date(item.start_time).toUTCString()}`}
        action={
          <div className="actions">
            {item.status === "open" && (
              <button
                className="secondary"
                aria-expanded={showResolve}
                onClick={() => setShowResolve((value) => !value)}
              >
                <Icon name="check" size={16} />
                Resolve incident
              </button>
            )}
            <Link className="button" href={`/counterfactual?incident=${id}`}>
              <Icon name="flask" size={16} />
              Test a fix
              <Icon name="arrow" size={14} />
            </Link>
          </div>
        }
      />
      <div className="incident-summary">
        <span className={`badge ${item.status === "open" ? "amber" : "green"}`}>
          <span className="badge-dot" />
          {item.status === "open" ? "Open incident" : "Resolved"}
        </span>
        <span>
          <strong>{percent(item.confidence)}</strong> signal confidence
        </span>
        <span>
          <strong>{item.signal_count ?? item.signals.length}</strong> recorded
          signals
        </span>
        <span>
          <strong>{item.services.length}</strong> affected{" "}
          {item.services.length === 1 ? "service" : "services"}
        </span>
      </div>
      {showResolve && (
        <form
          className="panel resolution-form"
          onSubmit={(event) => {
            event.preventDefault();
            resolve.mutate();
          }}
        >
          <div className="section-heading">
            <div>
              <h2>Record the verified resolution</h2>
              <p>Capture what you found and how you fixed it.</p>
            </div>
            <button
              type="button"
              className="icon-button"
              aria-label="Close resolution form"
              onClick={() => setShowResolve(false)}
            >
              <Icon name="close" />
            </button>
          </div>
          <div className="form-grid">
            <label>
              Root cause node
              <input
                required
                maxLength={200}
                value={node}
                placeholder="db:inventory"
                onChange={(event) => setNode(event.target.value)}
              />
            </label>
            <label>
              Root cause
              <input
                required
                maxLength={1000}
                value={cause}
                placeholder="What caused the deviation?"
                onChange={(event) => setCause(event.target.value)}
              />
            </label>
          </div>
          <label>
            Resolution
            <textarea
              required
              maxLength={1000}
              value={resolution}
              placeholder="Describe the verified fix…"
              onChange={(event) => setResolution(event.target.value)}
            />
          </label>
          {resolve.error && (
            <p role="alert" className="error">
              {resolve.error.message}
            </p>
          )}
          <div className="form-actions">
            <button
              className="secondary"
              type="button"
              onClick={() => setShowResolve(false)}
            >
              Cancel
            </button>
            <button disabled={resolve.isPending}>
              {resolve.isPending ? "Saving…" : "Save resolution"}
              <Icon name="check" size={15} />
            </button>
          </div>
        </form>
      )}
      <div className="grid-two investigation-grid">
        <section className="panel assessment-panel">
          <div className="section-heading">
            <div className="section-title">
              <Icon name="graph" size={17} />
              <h2>Root-cause assessment</h2>
            </div>
            <span className="badge">
              {rca.data?.source ?? "Analysis pending"}
            </span>
          </div>
          {rca.data ? (
            <>
              <div className="root-cause">
                <div className="eyebrow">Leading root cause</div>
                <h3 className="mono">
                  {rca.data.report.root_cause_node || "Insufficient evidence"}
                </h3>
                <span className="root-confidence">
                  {percent(rca.data.report.confidence)} confidence
                </span>
              </div>
              <p className="assessment-mechanism">
                {rca.data.report.mechanism}
              </p>
              <div className="suggested-fix">
                <span className="section-kicker">
                  <Icon name="check" size={14} />
                  Suggested next step
                </span>
                <p>{rca.data.report.suggested_fix}</p>
              </div>
              {rca.data.report.insufficient_evidence && (
                <p className="notice">
                  Evidence is incomplete. This ranking needs further
                  investigation.
                </p>
              )}
            </>
          ) : (
            <div className="pending-analysis">
              <Icon name="clock" size={23} />
              <h3>Gathering the evidence</h3>
              <p>
                Analysis starts after the incident has collected evidence for 60
                seconds. This view updates automatically.
              </p>
            </div>
          )}
          <QueryState error={rca.error} retry={() => void rca.refetch()} />
        </section>
        <section className="panel evidence-panel">
          <div className="section-heading">
            <div className="section-title">
              <Icon name="layers" size={17} />
              <h2>Evidence ledger</h2>
            </div>
            {rca.data && (
              <span className="count">{rca.data.bundle.evidence.length}</span>
            )}
          </div>
          {rca.data ? (
            <EvidenceList
              value={rca.data}
              onSelect={(trace, event) => {
                setTrace(trace);
                setEvent(event);
              }}
            />
          ) : (
            <div className="pending-analysis">
              <Icon name="layers" size={23} />
              <h3>Evidence is on its way</h3>
              <p>Grounded evidence appears here when analysis completes.</p>
            </div>
          )}
        </section>
      </div>
      {trace ? (
        <TraceExplorer traceId={trace} jumpEvent={event} />
      ) : (
        <section className="panel">
          <div className="section-heading">
            <h2>Trace timeline</h2>
            <span className="badge">Recorded events</span>
          </div>
          <div className="empty">
            <span className="empty-icon">
              <Icon name="activity" size={24} />
            </span>
            <h3>Follow the evidence into a trace</h3>
            <p>
              Select a concrete event in the evidence ledger to inspect the
              request and replay its observed state.
            </p>
          </div>
        </section>
      )}
    </>
  );
}
