"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { request } from "@/lib/api";
import { simulationView } from "@/lib/schemas";
import { Icon } from "./Icon";
import { SimulationResult } from "./SimulationResult";
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
    <div className="simulation-layout">
      <form
        className="panel intervention-form"
        onSubmit={(event) => {
          event.preventDefault();
          setValidation("");
          if (!incidentId && new Date(end) <= new Date(start)) {
            setValidation("Choose an end time after the window start.");
            return;
          }
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
        <div className="section-heading">
          <div className="section-title">
            <Icon name="flask" size={17} />
            <h2>Configure a simulation</h2>
          </div>
        </div>
        <p className="form-intro">One change. The same recorded traces.</p>
        <div className="form-step">
          <span>1</span>
          <h3>Choose an intervention</h3>
        </div>
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
            <p className="field-help">
              A multiplier of 0.5 tests a node at half its recorded latency.
            </p>
          </>
        )}
        {type === "timeout" && (
          <>
            <div className="form-grid">
              <label>
                Caller service
                <input
                  required
                  placeholder="svc:checkout"
                  value={caller}
                  onChange={(event) => setCaller(event.target.value)}
                />
              </label>
              <label>
                Callee service
                <input
                  required
                  placeholder="svc:payments"
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
            <p className="field-help">
              Change the timeout for this dependency edge.
            </p>
          </>
        )}
        {type === "cache_hit_rate" && (
          <>
            <div className="form-grid">
              <label>
                Service
                <input
                  required
                  placeholder="catalog"
                  value={service}
                  onChange={(event) => setService(event.target.value)}
                />
              </label>
              <label>
                Route template
                <input
                  required
                  placeholder="/products/{id}"
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
            <p className="field-help">
              A hit rate of 0.9 represents a 90% cache hit rate.
            </p>
          </>
        )}
        <div className="form-section">
          <div className="form-step">
            <span>2</span>
            <h3>Select the recorded window</h3>
          </div>
          {incidentId ? (
            <div className="incident-window">
              <Icon name="clock" size={16} />
              <div>
                <strong>Incident {incidentId.slice(0, 8)}</strong>
                <span>Using the recorded incident window</span>
              </div>
            </div>
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
        </div>
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
        <div className="form-actions">
          <button disabled={mutation.isPending}>
            {mutation.isPending
              ? "Simulating recorded traces…"
              : "Run simulation"}
            <Icon name="arrow" size={15} />
          </button>
        </div>
        <p className="form-footnote">
          <Icon name="shield" size={13} />
          Recorded span trees · Up to 10,000 events
        </p>
      </form>
      <SimulationResult data={mutation.data} busy={mutation.isPending} />
    </div>
  );
}
