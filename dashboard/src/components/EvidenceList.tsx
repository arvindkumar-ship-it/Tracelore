import type { Rca } from "@/lib/schemas";
export function EvidenceList({
  value,
  onSelect,
}: {
  value: NonNullable<Rca>;
  onSelect: (trace: string, event: string) => void;
}) {
  return (
    <div>
      {value.bundle.evidence.map((item) => (
        <div className="evidence-item" key={item.id}>
          <span className="evidence-id">{item.id}</span>
          <div>
            <span className="subtle mono">
              {item.kind.toUpperCase()} / {item.node}
            </span>
            <p>{item.text}</p>
            {item.kind === "metric" && (
              <span className="subtle">
                {Object.entries(item.data)
                  .map(
                    ([key, value]) =>
                      `${key}: ${typeof value === "number" ? value.toFixed(2) : String(value)}`,
                  )
                  .join(" · ")}
              </span>
            )}
          </div>
          {typeof item.data.trace_id === "string" &&
            typeof item.data.event_id === "string" && (
              <button
                className="ghost"
                onClick={() =>
                  onSelect(
                    String(item.data.trace_id),
                    String(item.data.event_id),
                  )
                }
              >
                View span ↗
              </button>
            )}
        </div>
      ))}
    </div>
  );
}
