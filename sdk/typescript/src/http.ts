import { randomUUID } from "node:crypto";
import { context, TRACE_HEADER } from "./context.js";
import type { Tracelore } from "./index.js";

export async function tracedFetch(
  client: Tracelore,
  input: string | URL,
  init: RequestInit = {},
  timeoutMs: number | null = null,
): Promise<Response> {
  const parent = context.getStore(),
    traceId = parent?.traceId ?? randomUUID(),
    spanId = randomUUID();
  const url = new URL(input),
    headers = new Headers(init.headers);
  headers.set(TRACE_HEADER, `${traceId}:${spanId}`);
  const startedAt = Date.now(),
    started = performance.now();
  let statusCode: number | null = null;
  try {
    const signals = [
      init.signal,
      timeoutMs === null ? null : AbortSignal.timeout(timeoutMs),
    ].filter((signal): signal is AbortSignal => Boolean(signal));
    const response = await fetch(url, {
      ...init,
      headers,
      signal: signals.length ? AbortSignal.any(signals) : undefined,
    });
    statusCode = response.status;
    return response;
  } finally {
    client.record({
      type: "http.client",
      attributes: {
        method: init.method ?? "GET",
        host: url.hostname,
        downstream_service:
          client.config.serviceMap?.[url.hostname] ?? url.hostname,
        status_code: statusCode,
        timeout_ms: timeoutMs,
      },
      traceId,
      spanId,
      parentSpanId: parent?.spanId ?? null,
      startedAt,
      durationMs: performance.now() - started,
      status: statusCode === null || statusCode >= 500 ? "error" : "ok",
    });
  }
}
