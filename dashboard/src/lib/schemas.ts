import { z } from "zod";
import type { components } from "./generated";

export const incident = z.object({
  id: z.string(),
  status: z.string(),
  opened_at: z.string(),
  closed_at: z.string().nullable(),
  start_event_id: z.string().nullable(),
  start_time: z.string(),
  services: z.array(z.string()),
  confidence: z.number(),
  signals: z.array(
    z
      .object({
        id: z.string(),
        kind: z.enum(["metric", "sequence"]),
        service: z.string(),
        route: z.string(),
        detected_at: z.string(),
        estimated_start: z.string(),
        confidence: z.number(),
        event_id: z.string().nullable().optional(),
        trace_id: z.string().nullable().optional(),
        metric: z.string().nullable().optional(),
        magnitude: z.number().optional(),
      })
      .passthrough(),
  ),
  updated_at: z.string(),
  version: z.number(),
  signal_count: z.number().optional(),
});
export const incidentPage = z.object({
  items: z.array(incident),
  next_cursor: z.string().nullable(),
});
export const stateView = z.object({
  scope: z.literal("observed"),
  digest: z.string(),
  state: z.record(z.unknown()),
});
export const traceView = z
  .object({
    scope: z.literal("observed"),
    trace_id: z.string(),
    digest: z.string(),
    dict: z.object({
      services: z.array(z.string()),
      types: z.array(z.string()),
    }),
    spans: z.object({
      id: z.array(z.string()),
      event_id: z.array(z.string()),
      parent: z.array(z.string().nullable()),
      start_us: z.array(z.number()),
      dur_us: z.array(z.number()),
      service_idx: z.array(z.number()),
      type_idx: z.array(z.number()),
      status: z.array(z.string()),
    }),
  })
  .superRefine((trace, context) => {
    const length = trace.spans.id.length;
    if (Object.values(trace.spans).some((column) => column.length !== length))
      context.addIssue({
        code: "custom",
        message: "Span columns have inconsistent lengths",
      });
  });
export const graphView = z.object({
  nodes: z.array(
    z.object({
      id: z.string(),
      anomalous: z.boolean(),
      root_candidate: z.boolean(),
    }),
  ),
  edges: z.array(
    z.object({
      source: z.string(),
      target: z.string(),
      calls: z.number(),
      propagation: z.boolean(),
    }),
  ),
});
export const evidence = z.object({
  id: z.string(),
  kind: z.string(),
  node: z.string(),
  text: z.string(),
  data: z.record(z.unknown()),
});
export const rcaView = z
  .object({
    incident_id: z.string(),
    source: z.string(),
    report: z.object({
      root_cause_node: z.string(),
      mechanism: z.string(),
      confidence: z.number(),
      evidence_ids: z.array(z.string()),
      suggested_fix: z.string(),
      insufficient_evidence: z.boolean(),
    }),
    bundle: z.object({
      candidates: z.array(
        z.object({
          node: z.string(),
          score: z.number(),
          parts: z.record(z.union([z.number(), z.boolean()])),
        }),
      ),
      evidence: z.array(evidence),
      similar_incidents: z.array(z.record(z.unknown())),
    }),
  })
  .nullable();
export const simulationView = z.object({
  mode: z.literal("simulated"),
  intervention: z.record(z.unknown()),
  original: z.record(z.number()),
  counterfactual: z.record(z.number()),
  verdict: z.string(),
  side_effects: z.record(z.number()),
  assumptions: z.array(z.string()),
  unsimulatable_count: z.number(),
  unsimulatable_percent: z.number(),
  input_digest: z.string(),
  result_digest: z.string(),
});
export const liveFrame = z.object({
  events_per_sec: z.number(),
  error_rate: z.number(),
  per_service: z.record(
    z.object({ count: z.number(), errors: z.number(), p95_ms: z.number() }),
  ),
  incidents: z.array(z.record(z.unknown())),
  incident_version: z.number(),
  heartbeat: z.string(),
});
export const settingsView = z.object({
  tiering_enabled: z.boolean(),
  hot_retention_days: z.number(),
  warm_retention_days: z.number(),
  lossy_sampling_enabled: z.boolean(),
  llm_enabled: z.boolean(),
  rag_enabled: z.boolean(),
  services: z.array(z.string()),
});
export const keyView = z.object({
  key_hash: z.string(),
  name: z.string(),
  created_at: z.string(),
  revoked_at: z.string().nullable(),
});
export type Incident = components["schemas"]["Incident"];
export type Trace = components["schemas"]["TraceView"];
export type State = components["schemas"]["StateView"];
export type Graph = components["schemas"]["GraphView"];
export type Rca = z.infer<typeof rcaView>;
