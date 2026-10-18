import type { Rca } from "@/lib/schemas";
import { Icon } from "./Icon";
export function EvidenceList({
  value,
  onSelect,
}: {
  value: NonNullable<Rca>;
  onSelect: (trace: string, event: string) => void;
}) {
  return (
    <div className="evidence-list">
      {value.bundle.evidence.length ? (
        value.bundle.evidence.map((item, index) => (
          <div className="evidence-item" key={item.id}>
            <span className="evidence-id" title={item.id}>
              {String(index + 1).padStart(2, "0")}
            </span>
            <div className="evidence-content">
              <div className="evidence-meta">
                <span className="badge">{item.kind}</span>
                <span className="mono">{item.node}</span>
              </div>
              <p>{item.text}</p>
              {item.kind === "metric" && Object.keys(item.data).length > 0 && (
                <details className="evidence-details">
                  <summary>Metric details</summary>
                  <dl>
                    {Object.entries(item.data).map(([key, value]) => (
                      <div key={key}>
                        <dt>{key.replaceAll("_", " ")}</dt>
                        <dd>
                          {typeof value === "number"
                            ? value.toFixed(2)
                            : String(value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </details>
              )}
              {typeof item.data.trace_id === "string" &&
                typeof item.data.event_id === "string" && (
                  <button
                    className="text-button evidence-action"
                    onClick={() =>
                      onSelect(
                        String(item.data.trace_id),
                        String(item.data.event_id),
                      )
                    }
                  >
                    View span
                    <Icon name="external" size={13} />
                  </button>
                )}
            </div>
          </div>
        ))
      ) : (
        <p className="subtle">
          No concrete evidence has been attached to this assessment yet.
        </p>
      )}
    </div>
  );
}
