import { randomUUID } from "node:crypto";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { canonicalJson, eventHash, sha256 } from "./canonical.js";
import { context } from "./context.js";
import {
  buildEvent,
  type Attributes,
  type SpanInput,
  type WireEvent,
} from "./event.js";
import { Spool } from "./spool.js";
export {
  expressMiddleware,
  expressErrorMiddleware,
  nextMiddleware,
} from "./middleware.js";
export { canonicalJson, eventHash } from "./canonical.js";
export { tracedFetch } from "./http.js";

export interface Config {
  apiKey: string;
  service: string;
  endpoint: string;
  instanceId?: string;
  batchSize?: number;
  flushIntervalMs?: number;
  maxBuffer?: number;
  spoolDir?: string;
  spoolMaxMb?: number;
  serviceMap?: Record<string, string>;
  skipRoutes?: string[];
}

export class Tracelore {
  private sequence = 0;
  private closed = false;
  private abort = new AbortController();
  private lastHash = "0".repeat(64);
  private queue: WireEvent[] = [];
  private timer?: ReturnType<typeof setInterval>;
  private flushing?: Promise<void>;
  private pendingSpool: Promise<void> = Promise.resolve();
  readonly streamId: string;
  readonly spool: Spool;
  constructor(readonly config: Config) {
    if (!config.apiKey || !config.service)
      throw new Error("service and apiKey are required");
    if (
      !Number.isInteger(config.batchSize ?? 50) ||
      (config.batchSize ?? 50) < 1 ||
      (config.batchSize ?? 50) > 1000
    )
      throw new Error("batchSize must be an integer between 1 and 1000");
    if (
      (config.flushIntervalMs ?? 100) < 10 ||
      (config.maxBuffer ?? 10000) < 1 ||
      (config.spoolMaxMb ?? 100) < 1
    )
      throw new Error(
        "flushIntervalMs, maxBuffer and spoolMaxMb must be positive",
      );
    new URL(config.endpoint);
    this.streamId = `${config.service}:${config.instanceId ?? randomUUID()}`;
    this.spool = new Spool(
      join(
        config.spoolDir ?? join(tmpdir(), "tracelore-spool-node"),
        config.service,
      ),
      (config.spoolMaxMb ?? 100) * 1024 * 1024,
    );
  }

  start(): void {
    if (this.closed) throw new Error("Create a new client after shutdown");
    if (this.timer) return;
    this.timer = setInterval(() => {
      void this.flush().catch((error) =>
        console.error(
          "tracelore_flush_failed",
          error instanceof Error ? error.name : "Error",
        ),
      );
    }, this.config.flushIntervalMs ?? 100);
    this.timer.unref();
  }

  record(input: SpanInput): void {
    try {
      const event = buildEvent(this.config.service, this.streamId, input);
      Object.assign(event, {
        sequence: ++this.sequence,
        prev_event_hash: this.lastHash,
      });
      this.lastHash = eventHash(event);
      const sealed = { ...event, event_hash: this.lastHash } as WireEvent;
      if (
        this.closed ||
        this.queue.length >= (this.config.maxBuffer ?? 10_000)
      ) {
        this.pendingSpool = this.pendingSpool.then(() =>
          this.spool.append([sealed]),
        );
      } else this.queue.push(sealed);
    } catch (error) {
      console.error(
        "tracelore_record_failed",
        error instanceof Error ? error.name : "Error",
      );
    }
  }

  async span<T>(
    type: string,
    attributes: () => Attributes,
    operation: () => Promise<T>,
  ): Promise<T> {
    const parent = context.getStore(),
      spanId = randomUUID(),
      traceId = parent?.traceId ?? randomUUID();
    const startedAt = Date.now(),
      started = performance.now();
    let status: "ok" | "error" = "ok";
    try {
      return await context.run({ traceId, spanId }, operation);
    } catch (error) {
      status = "error";
      this.record({
        type: "error",
        attributes: {
          exception_type: error instanceof Error ? error.name : "Error",
          message_hash: safeErrorHash(error),
        },
        traceId,
        spanId: randomUUID(),
        parentSpanId: spanId,
        startedAt: Date.now(),
        durationMs: 0,
        status,
      });
      throw error;
    } finally {
      try {
        this.record({
          type,
          attributes: attributes(),
          traceId,
          spanId,
          parentSpanId: parent?.spanId ?? null,
          startedAt,
          durationMs: performance.now() - started,
          status,
        });
      } catch (error) {
        console.error(
          "tracelore_span_failed",
          error instanceof Error ? error.name : "Error",
        );
      }
    }
  }

  async flush(): Promise<void> {
    await this.persistBuffer();
    if (this.flushing) return this.flushing;
    this.flushing = this.flushOnce().finally(() => {
      this.flushing = undefined;
    });
    return this.flushing;
  }

  private async persistBuffer(): Promise<void> {
    const events = this.queue.splice(0);
    if (events.length)
      this.pendingSpool = this.pendingSpool.then(async () => {
        for (
          let index = 0;
          index < events.length;
          index += this.config.batchSize ?? 50
        )
          await this.spool.append(
            events.slice(index, index + (this.config.batchSize ?? 50)),
          );
      });
    await this.pendingSpool;
  }

  private async flushOnce(): Promise<void> {
    await this.spool.drain(
      (batch) => this.send(batch),
      this.config.batchSize ?? 50,
    );
  }

  private async send(events: WireEvent[]): Promise<boolean> {
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const response = await fetch(this.config.endpoint, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            "x-api-key": this.config.apiKey,
          },
          body: canonicalJson({ batch_id: randomUUID(), events }),
          signal: AbortSignal.any([
            AbortSignal.timeout(2000),
            this.abort.signal,
          ]),
        });
        if (response.ok) {
          const result = (await response.json()) as {
            rejected: { event_id: string }[];
          };
          const rejected = new Set(
            result.rejected.map((item) => item.event_id),
          );
          await this.spool.reject(
            events.filter((event) => rejected.has(event.event_id)),
          );
          return true;
        }
        if (response.status !== 429 && response.status < 500) {
          await this.spool.reject(events);
          return true;
        }
      } catch (error) {
        console.warn(
          `tracelore_transport_retry attempt=${attempt} error=${error instanceof Error ? error.name : "Error"}`,
        );
      }
      if (this.closed) return false;
      if (attempt < 2) await delay([200, 800][attempt]);
    }
    return false;
  }

  async shutdown(): Promise<void> {
    if (this.closed) return;
    this.closed = true;
    if (this.timer) clearInterval(this.timer);
    await this.persistBuffer();
    this.abort.abort();
    await this.flushing;
  }
}

function safeErrorHash(error: unknown): string {
  try {
    return sha256(String(error));
  } catch {
    return sha256(error instanceof Error ? error.name : "Error");
  }
}
