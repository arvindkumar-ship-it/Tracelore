"use client";
import { useEffect, useRef, useState } from "react";
import type { State } from "@/lib/schemas";
export function StateInspector({ value }: { value: State | undefined }) {
  const [tab, setTab] = useState("endpoints");
  const previous = useRef<Record<string, unknown>>({});
  const state = value?.state ?? {};
  const content = state[tab];
  const rows =
    content && typeof content === "object" ? Object.entries(content) : [];
  useEffect(() => {
    previous.current = state;
  }, [value]);
  return (
    <div className="panel">
      <div
        className="actions"
        style={{ justifyContent: "space-between", marginBottom: 18 }}
      >
        <h2 style={{ margin: 0 }}>State inspector</h2>
        <span className="badge cyan">OBSERVED</span>
      </div>
      <p className="subtle">
        Recorded counters and hashed cache presence. Queue depth is an observed
        estimate.
      </p>
      <div className="state-tabs">
        {[
          "endpoints",
          "edges",
          "db_tables",
          "cache",
          "queues",
          "errors_by_type",
        ].map((name) => (
          <button
            className={`ghost ${tab === name ? "selected" : ""}`}
            key={name}
            onClick={() => setTab(name)}
          >
            {name.replaceAll("_", " ")}
          </button>
        ))}
      </div>
      {!value ? (
        <p>Move the event cursor to inspect its recorded prefix.</p>
      ) : rows.length ? (
        rows.slice(0, 100).map(([key, item]) => {
          const old = previous.current[tab] as
            Record<string, unknown> | undefined;
          const changed =
            old && JSON.stringify(old[key]) !== JSON.stringify(item);
          return (
            <div
              className={`inspector-row ${changed ? "changed" : ""}`}
              key={key}
            >
              <span className="mono">{key}</span>
              <span>
                {typeof item === "object"
                  ? Object.entries(item ?? {})
                      .filter(
                        ([name]) =>
                          name !== "histogram" && name !== "present_keys",
                      )
                      .map(([name, value]) => `${name}: ${value}`)
                      .join(" · ")
                  : String(item)}
              </span>
            </div>
          );
        })
      ) : (
        <p>No observations at this cursor.</p>
      )}
      {value && (
        <p className="hint mono" style={{ marginTop: 20 }}>
          digest {value.digest.slice(0, 24)}… · {String(state.event_count ?? 0)}{" "}
          events
        </p>
      )}
    </div>
  );
}
