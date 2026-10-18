import assert from "node:assert/strict";
import { mkdtemp, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { Tracelore } from "../dist/index.js";
import { context } from "../dist/context.js";

test("durable shutdown preserves concurrent contexts and chain links", async () => {
  const directory = await mkdtemp(join(tmpdir(), "tracelore-node-test-"));
  try {
    const client = new Tracelore({
      apiKey: "test-only",
      service: "node",
      endpoint: "http://localhost/ingest",
      spoolDir: directory,
    });
    await Promise.all(
      Array.from({ length: 40 }, (_, index) =>
        context.run(
          { traceId: `trace-${index}`, spanId: `parent-${index}` },
          () =>
            client.span(
              "db.query",
              () => ({
                db_table: "test",
                operation: "select",
                query_hash: "0".repeat(64),
                rows: 1,
              }),
              async () => {
                await Promise.resolve();
              },
            ),
        ),
      ),
    );
    await client.shutdown();
    const recovered = [];
    await client.spool.drain(async (events) => {
      recovered.push(...events);
      return true;
    }, 1000);
    assert.equal(recovered.length, 40);
    recovered.sort((a, b) => a.sequence - b.sequence);
    for (const [index, event] of recovered.entries()) {
      assert.equal(event.sequence, index + 1);
      assert.equal(
        event.prev_event_hash,
        index ? recovered[index - 1].event_hash : "0".repeat(64),
      );
      assert.equal(
        event.parent_span_id,
        `parent-${event.trace_id.split("-")[1]}`,
      );
    }
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("instrumentation attribute failures preserve the application's original exception", async () => {
  const directory = await mkdtemp(join(tmpdir(), "tracelore-node-error-"));
  const client = new Tracelore({
    apiKey: "test-only",
    service: "node",
    endpoint: "http://localhost/ingest",
    spoolDir: directory,
  });
  try {
    const original = new Error("application failure");
    await assert.rejects(
      client.span(
        "db.query",
        () => {
          throw new Error("adapter failure");
        },
        async () => {
          throw original;
        },
      ),
      (error) => error === original,
    );
    await client.shutdown();
    assert.ok((await readdir(join(directory, "node"))).length);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test("invalid zero batch size fails before entering a flush loop", () => {
  assert.throws(
    () =>
      new Tracelore({
        apiKey: "test-only",
        service: "node",
        endpoint: "http://localhost/ingest",
        batchSize: 0,
      }),
    /batchSize/,
  );
});
