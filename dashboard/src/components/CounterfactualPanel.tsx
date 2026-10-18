"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { request } from "@/lib/api";
import { simulationView } from "@/lib/schemas";
import { percent, duration } from "@/lib/format";
const interventionSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("timeout"),
    caller: z.string().min(1),
    callee: z.string().min(1),
    new_timeout_ms: z.number().int().positive().max(300000),
  }),
  z.object({
    type: z.literal("cache_hit_rate"),
    service: z.string().min(1),
    route: z.string().min(1),
    target_hit_rate: z.number().min(0).max(1),
  }),
  z.object({
    type: z.literal("latency_scale"),
    node: z.string().min(1),
    factor: z.number().min(0.05).max(5),
  }),
]);
export function CounterfactualPanel({ incidentId }: { incidentId?: string }) {
  const [type, setType] = useState("latency_scale"),
    [node, setNode] = useState(""),
    [factor, setFactor] = useState("0.5");
  const [caller, setCaller] = useState(""),
    [callee, setCallee] = useState(""),
    [timeout, setTimeout] = useState("2000");
  const [service, setService] = useState(""),
    [route, setRoute] = useState(""),
    [hitRate, setHitRate] = useState("0.9");
  const [start, setStart] = useState(""),
    [end, setEnd] = useState(""),
    [validation, setValidation] = useState("");
  const mutation = useMutation({
    mutationFn: (intervention: z.infer<typeof interventionSchema>) =>
      request("/counterfactual", simulationView, {
        method: "POST",
        body: JSON.stringify({
          ...(incidentId
            ? { incident_id: incidentId }
            : {
                window: {
                  start: new Date(start).toISOString(),
                  end: new Date(end).toISOString(),
                },
              }),
          intervention,
        }),
      }),
  });
  return (
    <div className="grid-two">
      <form
        className="panel"
        onSubmit={(event) => {
          event.preventDefault();
          setValidation("");
          const value =
            type === "timeout"
              ? { type, caller, callee, new_timeout_ms: Number(timeout) }
              : type === "cache_hit_rate"
                ? { type, service, route, target_hit_rate: Number(hitRate) }
                : { type, node, factor: Number(factor) };
          const result = interventionSchema.safeParse(value);
          if (!result.success) {
            setValidation(
              result.error.issues.map((item) => item.message).join(", "),
            );
            return;
          }
          mutation.mutate(result.data);
        }}
      >
        <h2>Choose an intervention</h2>
        <p className="subtle">Recorded span trees · Up to 10,000 events</p>
        <label>
          Intervention
          <select
            value={type}
            onChange={(event) => setType(event.target.value)}
          >
            <option value="latency_scale">Scale node latency</option>
            <option value="timeout">Change an edge timeout</option>
            <option value="cache_hit_rate">Improve cache hit rate</option>
          </select>
        </label>
        {type === "latency_scale" && (
          <>
            <label>
              Node
              <input
                required
                placeholder="db:inventory or svc:payments"
                value={node}
                onChange={(event) => setNode(event.target.value)}
              />
            </label>
            <label>
              Latency multiplier
              <input
                type="number"
                step="0.05"
                min="0.05"
                max="5"
                value={factor}
                onChange={(event) => setFactor(event.target.value)}
              />
            </label>
          </>
        )}
        {type === "timeout" && (
          <>
            <div className="form-grid">
              <label>
                Caller service
                <input
                  required
                  value={caller}
                  onChange={(event) => setCaller(event.target.value)}
                />
              </label>
              <label>
                Callee service
                <input
                  required
                  value={callee}
                  onChange={(event) => setCallee(event.target.value)}
                />
              </label>
            </div>
            <label>
              New timeout (ms)
              <input
                type="number"
                min="1"
                max="300000"
                value={timeout}
                onChange={(event) => setTimeout(event.target.value)}
              />
            </label>
          </>
        )}
        {type === "cache_hit_rate" && (
          <>
            <div className="form-grid">
              <label>
                Service
                <input
                  required
                  value={service}
                  onChange={(event) => setService(event.target.value)}
                />
              </label>
              <label>
                Route template
                <input
                  required
                  value={route}
                  onChange={(event) => setRoute(event.target.value)}
                />
              </label>
            </div>
            <label>
              Target hit rate (0–1)
              <input
                type="number"
                min="0"
                max="1"
                step="0.01"
                value={hitRate}
                onChange={(event) => setHitRate(event.target.value)}
              />
            </label>
          </>
        )}
        {incidentId ? (
          <p className="notice mono">
            Incident {incidentId.slice(0, 8)} · recorded incident window
          </p>
        ) : (
          <div className="form-grid">
            <label>
              Window start (local)
              <input
                type="datetime-local"
                required
                value={start}
                onChange={(event) => setStart(event.target.value)}
              />
            </label>
            <label>
              Window end (local)
              <input
                type="datetime-local"
                required
                value={end}
                onChange={(event) => setEnd(event.target.value)}
              />
            </label>
          </div>
        )}
        {validation && (
          <p role="alert" className="error">
            {validation}
          </p>
        )}
        {mutation.error && (
          <p role="alert" className="error">
            {mutation.error.message}
          </p>
        )}
        <button disabled={mutation.isPending}>
          {mutation.isPending
            ? "Simulating recorded traces…"
            : "Run deterministic simulation →"}
        </button>
      </form>
      <section className="panel">
        <div className="actions" style={{ justifyContent: "space-between" }}>
          <h2>Projected outcome</h2>
          <span className="badge cyan">SIMULATED</span>
        </div>
        {mutation.data ? (
          <>
            <h2 style={{ marginTop: 26, color: "var(--lime)" }}>
              {mutation.data.verdict}
            </h2>
            <div className="simulation-bars">
              {["error_rate", "p95_ms", "p99_ms"].map((metric) => {
                const report = mutation.data!,
                  before = report.original[metric],
                  after = report.counterfactual[metric],
                  maximum = Math.max(before, after, 0.001);
                const format = metric === "error_rate" ? percent : duration;
                return (
                  <div key={metric} style={{ marginBottom: 22 }}>
                    <span className="metric-label">
                      {metric.replaceAll("_", " ")}
                    </span>
                    {[
                      ["Recorded", before],
                      ["Simulated", after],
                    ].map(([label, value], index) => (
                      <div className="bar-row" key={String(label)}>
                        <span className="subtle">{label}</span>
                        <div className="bar-track">
                          <div
                            className={`bar-fill ${index ? "after" : ""}`}
                            style={{
                              width: `${(Number(value) / maximum) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="mono">{format(Number(value))}</span>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
            <p
              className={
                mutation.data.unsimulatable_percent >= 20 ? "error" : "subtle"
              }
            >
              {mutation.data.unsimulatable_percent.toFixed(1)}% of traces could
              not be simulated.
            </p>
            <h3>Assumptions</h3>
            <ul className="assumptions">
              {mutation.data.assumptions.map((value) => (
                <li key={value}>{value}</li>
              ))}
            </ul>
            <p className="hint mono">
              result {mutation.data.result_digest.slice(0, 24)}…
            </p>
          </>
        ) : (
          <div className="empty">
            <div className="orbit">◎</div>
            <h2>Test the hypothesis.</h2>
            <p>
              Compare a recorded outcome with a deterministic simulation. The
              result includes its assumptions and evidence limits.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
