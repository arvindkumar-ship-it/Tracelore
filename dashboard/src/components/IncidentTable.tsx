import Link from "next/link";
import type { z } from "zod";
import { incident } from "@/lib/schemas";
import { percent, relative } from "@/lib/format";
import { Icon } from "./Icon";

export function IncidentTable({
  items,
}: {
  items: z.infer<typeof incident>[];
}) {
  return (
    <div className="table-wrap">
      <table className="incident-table">
        <caption className="sr-only">
          Incident stream with affected services, signal confidence, status, and
          opening time
        </caption>
        <thead>
          <tr>
            <th>Incident / service</th>
            <th>Confidence</th>
            <th>Status</th>
            <th className="numeric">Signals</th>
            <th>Opened</th>
            <th>
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td className="incident-main-cell">
                <Link href={`/incidents/${item.id}`} className="incident-title">
                  {item.services.join(" / ") || "Unassigned service"}
                </Link>
                <div className="incident-sub mono">
                  INC-{item.id.slice(0, 8).toUpperCase()}
                </div>
              </td>
              <td data-label="Confidence">
                <span className="confidence">
                  <span className="confidence-bars" aria-hidden="true">
                    {[0, 1, 2, 3, 4].map((n) => (
                      <i
                        key={n}
                        className={
                          item.confidence >= (n + 1) / 5 ? "filled" : ""
                        }
                      />
                    ))}
                  </span>
                  <span>{percent(item.confidence)}</span>
                </span>
                <span className="sr-only">
                  {item.confidence >= 0.9
                    ? "High"
                    : item.confidence >= 0.7
                      ? "Elevated"
                      : "Medium"}
                </span>
              </td>
              <td data-label="Status">
                <span
                  className={`badge ${item.status === "open" ? "amber" : "green"}`}
                >
                  <span className="badge-dot" />
                  {item.status === "open" ? "Open" : "Resolved"}
                </span>
              </td>
              <td className="numeric" data-label="Signals">
                {item.signal_count ?? item.signals.length}
              </td>
              <td data-label="Opened" className="subtle">
                <time
                  dateTime={item.opened_at}
                  title={new Date(item.opened_at).toUTCString()}
                >
                  {relative(item.opened_at)}
                </time>
              </td>
              <td className="incident-row-action">
                <Link
                  className="icon-button"
                  href={`/incidents/${item.id}`}
                  aria-label={`Open incident ${item.id}`}
                >
                  <Icon name="arrow" size={16} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
