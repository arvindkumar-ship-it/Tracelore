import { sha256 } from "./canonical.js";
import { randomUUID } from "node:crypto";
import { context, parseHeader, TRACE_HEADER } from "./context.js";
import type { Tracelore } from "./index.js";

interface RequestLike {
  headers: Record<string, string | string[] | undefined>;
  method: string;
  path?: string;
  route?: { path: string };
}
interface ResponseLike {
  statusCode: number;
  once(event: "finish", fn: () => void): void;
}

export function expressMiddleware(client: Tracelore) {
  return (
    request: RequestLike,
    response: ResponseLike,
    next: () => void,
  ): void => {
    if (
      (
        client.config.skipRoutes ?? ["/health", "/healthz", "/metrics"]
      ).includes(request.path ?? "")
    ) {
      next();
      return;
    }
    const header = request.headers[TRACE_HEADER];
    const incoming = parseHeader(Array.isArray(header) ? header[0] : header);
    const traceId = incoming?.[0] ?? randomUUID(),
      spanId = randomUUID();
    const startedAt = Date.now(),
      started = performance.now();
    response.once("finish", () =>
      client.record({
        type: "http.request",
        attributes: {
          method: request.method,
          route: request.route?.path ?? "unmatched",
          status_code: response.statusCode,
        },
        traceId,
        spanId,
        parentSpanId: incoming?.[1] ?? null,
        startedAt,
        durationMs: performance.now() - started,
        status: response.statusCode >= 500 ? "error" : "ok",
      }),
    );
    context.run({ traceId, spanId }, next);
  };
}

export function nextMiddleware(
  client: Tracelore,
  routeTemplate: string,
  handler: (request: Request) => Promise<Response>,
) {
  return async (request: Request): Promise<Response> => {
    const incoming = parseHeader(
      request.headers.get(TRACE_HEADER) ?? undefined,
    );
    const traceId = incoming?.[0] ?? randomUUID(),
      spanId = randomUUID();
    const startedAt = Date.now(),
      started = performance.now();
    let statusCode = 500;
    try {
      return await context.run({ traceId, spanId }, async () => {
        const response = await handler(request);
        statusCode = response.status;
        return response;
      });
    } finally {
      client.record({
        type: "http.request",
        attributes: {
          method: request.method,
          route: routeTemplate,
          status_code: statusCode,
        },
        traceId,
        spanId,
        parentSpanId: incoming?.[1] ?? null,
        startedAt,
        durationMs: performance.now() - started,
        status: statusCode >= 500 ? "error" : "ok",
      });
    }
  };
}

export function expressErrorMiddleware(client: Tracelore) {
  return (
    error: unknown,
    request: RequestLike,
    response: ResponseLike,
    next: (error: unknown) => void,
  ): void => {
    const current = context.getStore();
    if (current)
      client.record({
        type: "error",
        attributes: {
          exception_type: error instanceof Error ? error.name : "Error",
          message_hash: sha256(String(error)),
        },
        traceId: current.traceId,
        spanId: randomUUID(),
        parentSpanId: current.spanId,
        startedAt: Date.now(),
        durationMs: 0,
        status: "error",
      });
    next(error);
  };
}
