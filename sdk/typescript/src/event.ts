import { randomUUID } from "node:crypto";
import { sha256 } from "./canonical.js";

export const required: Record<string, string[]> = {
  "http.request": ["method", "route", "status_code"],
  "http.client": [
    "method",
    "host",
    "downstream_service",
    "status_code",
    "timeout_ms",
  ],
  "db.query": ["operation", "db_table", "query_hash", "rows"],
  "cache.get": ["key_hash", "hit"],
  "cache.set": ["key_hash"],
  "cache.delete": ["key_hash"],
  "queue.publish": ["queue", "message_hash"],
  "queue.consume": ["queue", "message_hash"],
  error: ["exception_type", "message_hash"],
};
export type Attributes = Record<string, string | number | boolean | null>;
export type WireEvent = Record<string, unknown> & {
  event_id: string;
  event_hash: string;
  stream_id: string;
  sequence: number;
};
export interface SpanInput {
  type: string;
  attributes: Attributes;
  traceId: string;
  spanId: string;
  parentSpanId: string | null;
  payload?: string | Uint8Array;
  startedAt: number;
  durationMs: number;
  status: "ok" | "error";
}

function timestamp(micros: number): string {
  const whole = Math.floor(micros / 1000);
  return `${new Date(whole).toISOString().slice(0, 19)}.${String(((micros % 1_000_000) + 1_000_000) % 1_000_000).padStart(6, "0")}Z`;
}

export function buildEvent(
  service: string,
  streamId: string,
  input: SpanInput,
): Record<string, unknown> {
  const keys = required[input.type];
  if (
    !keys ||
    Object.keys(input.attributes).sort().join("|") !==
      [...keys].sort().join("|")
  )
    throw new TypeError("invalid attributes");
  if (!Number.isFinite(input.durationMs) || input.durationMs < 0)
    throw new TypeError("invalid duration");
  const duration = Math.round(input.durationMs * 1000) / 1000;
  return {
    event_id: randomUUID(),
    trace_id: input.traceId,
    span_id: input.spanId,
    parent_span_id: input.parentSpanId,
    stream_id: streamId,
    timestamp: timestamp(input.startedAt * 1000),
    ended_at: timestamp(input.startedAt * 1000 + Math.round(duration * 1000)),
    duration_ms: duration,
    service,
    type: input.type,
    status: input.status,
    attributes: input.attributes,
    payload_hash: sha256(input.payload ?? ""),
  };
}
