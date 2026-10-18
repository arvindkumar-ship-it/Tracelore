import { describe, it, expect } from "vitest";
import { layout } from "../src/components/timeline/layout";
import { buildGrid, hitTest } from "../src/components/timeline/hitTest";
import type { Trace } from "../src/lib/schemas";
function trace(count = 4): Trace {
  const ids = Array.from({ length: count }, (_, index) => `span-${index}`);
  return {
    scope: "observed",
    trace_id: "fixture",
    digest: "fixture",
    dict: { services: ["gateway"], types: ["http.request"] },
    spans: {
      id: ids,
      event_id: ids,
      parent: ids.map((_, index) => (index === 0 ? null : ids[0])),
      start_us: ids.map((_, index) => (index === 0 ? 0 : index)),
      dur_us: ids.map((_, index) => (index === 0 ? count * 2 : 10)),
      service_idx: ids.map(() => 0),
      type_idx: ids.map(() => 0),
      status: ids.map(() => "ok"),
    },
  };
}
describe("timeline packing", () => {
  it("places children below parents and overlapping siblings on separate lanes", () => {
    const spans = layout(trace());
    expect(spans[1].row).toBeGreaterThan(spans[0].row);
    expect(new Set(spans.map((span) => span.row)).size).toBe(4);
  });
  it("lays out and spatially indexes 10,000 spans", () => {
    const spans = layout(trace(10000));
    expect(spans).toHaveLength(10000);
    const grid = buildGrid(spans, 0, 20000),
      target = spans[4000];
    expect(hitTest(grid, target.row, target.start + 1)?.index).toBe(
      target.index,
    );
    expect(hitTest(grid, 99999, 0)).toBeUndefined();
  });
  it("handles orphan parents", () => {
    const value = trace();
    value.spans.parent[2] = "missing";
    expect(layout(value)).toHaveLength(4);
  });
});
