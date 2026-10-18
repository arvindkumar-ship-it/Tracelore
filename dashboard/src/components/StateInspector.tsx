"use client";
import { useEffect, useRef, useState } from "react";
import type { State } from "@/lib/schemas";
import { Icon } from "./Icon";
const tabs = [
  "endpoints",
  "edges",
  "db_tables",
  "cache",
  "queues",
  "errors_by_type",
];
export function StateInspector({
  value,
  context = "cursor",
}: {
  value: State | undefined;
  context?: "cursor" | "timestamp";
}) {
  const [tab, setTab] = useState("endpoints");
  const previous = useRef<Record<string, unknown>>({});
  const state = value?.state ?? {},
    content = state[tab];
  const rows =
    content && typeof content === "object" ? Object.entries(content) : [];
  useEffect(() => {
    previous.current = state;
  }, [value]);
  return (
    <section className="panel state-inspector">
      <div className="section-heading">
        <div className="section-title">
          <Icon name="eye" size={17} />
          <h2>State inspector</h2>
        </div>
        <span className="badge cyan">
          <Icon name="eye" size={12} />
          Observed
        </span>
      </div>
      <p className="inspector-description">
        Recorded counters and hashed cache presence. Queue depth is an observed
        estimate.
      </p>
      <div
        className="state-tabs"
        role="tablist"
        aria-label="Observed state categories"
      >
        {tabs.map((name, index) => (
          <button
            role="tab"
            id={`state-tab-${name}`}
            aria-selected={tab === name}
            aria-controls="state-tab-content"
            tabIndex={tab === name ? 0 : -1}
            key={name}
            onClick={() => setTab(name)}
            onKeyDown={(event) => {
              const next =
                event.key === "ArrowRight"
                  ? (index + 1) % tabs.length
                  : event.key === "ArrowLeft"
                    ? (index + tabs.length - 1) % tabs.length
                    : event.key === "Home"
                      ? 0
                      : event.key === "End"
                        ? tabs.length - 1
                        : -1;
              if (next < 0) return;
              event.preventDefault();
              setTab(tabs[next]);
              document.getElementById(`state-tab-${tabs[next]}`)?.focus();
            }}
          >
            {name === "db_tables"
              ? "Database tables"
              : name === "errors_by_type"
                ? "Error types"
                : name.charAt(0).toUpperCase() + name.slice(1)}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id="state-tab-content"
        aria-labelledby={`state-tab-${tab}`}
        tabIndex={0}
      >
        {!value ? (
          <div className="empty inspector-empty">
            <span className="empty-icon">
              <Icon name="clock" size={23} />
            </span>
            <h3>
              {context === "timestamp"
                ? "Your system, at a moment in time"
                : "Explore a recorded moment"}
            </h3>
            <p>
              {context === "timestamp"
                ? "Choose a timestamp above to reconstruct the observed state and explore its recorded observations."
                : "Move the event cursor to inspect the state recorded up to that event."}
            </p>
          </div>
        ) : rows.length ? (
          <div className="inspector-records">
            {rows.slice(0, 100).map(([key, item]) => {
              const old = previous.current[tab] as
                Record<string, unknown> | undefined;
              const changed =
                old && JSON.stringify(old[key]) !== JSON.stringify(item);
              return (
                <div
                  className={`inspector-row ${changed ? "changed" : ""}`}
                  key={key}
                >
                  <span className="mono inspector-key">{key}</span>
                  <span className="inspector-value">
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
            })}
            {rows.length > 100 && (
              <p className="hint">
                Showing the first 100 of {rows.length.toLocaleString()}{" "}
                observations.
              </p>
            )}
          </div>
        ) : (
          <div className="empty inspector-empty">
            <Icon name="layers" size={22} />
            <h3>No observations in this category</h3>
            <p>
              There are no recorded {tab.replaceAll("_", " ")} at the selected
              moment. Try another category or point in time.
            </p>
          </div>
        )}
      </div>
      {value && (
        <div className="inspector-footer">
          <span className="mono">digest {value.digest.slice(0, 24)}…</span>
          <span>{String(state.event_count ?? 0)} events</span>
        </div>
      )}
    </section>
  );
}
