import { it, expect, vi } from "vitest";
import { incidentPage, traceView, simulationView } from "../src/lib/schemas";
import { reconnectDelay } from "../src/lib/ws";
it("accepts an empty incident response", () =>
  expect(incidentPage.parse({ items: [], next_cursor: null }).items).toEqual(
    [],
  ));
it("rejects a trace with mismatched column lengths", () =>
  expect(() =>
    traceView.parse({
      scope: "observed",
      trace_id: "x",
      digest: "x",
      dict: { services: [], types: [] },
      spans: {
        id: ["a"],
        event_id: [],
        parent: [],
        start_us: [],
        dur_us: [],
        service_idx: [],
        type_idx: [],
        status: [],
      },
    }),
  ).toThrow());
it("requires an honest simulated label", () =>
  expect(simulationView.safeParse({ mode: "real" }).success).toBe(false));
it("backs off reconnects and caps the timer", () => {
  vi.useFakeTimers();
  const callback = vi.fn();
  setTimeout(callback, reconnectDelay(4));
  vi.advanceTimersByTime(15999);
  expect(callback).not.toHaveBeenCalled();
  vi.advanceTimersByTime(1);
  expect(callback).toHaveBeenCalled();
  expect(reconnectDelay(100)).toBe(30000);
  vi.useRealTimers();
});
