import Link from "next/link";
import type { z } from "zod";
import { incident } from "@/lib/schemas";
import { percent, relative } from "@/lib/format";
export function IncidentTable({
  items,
}: {
  items: z.infer<typeof incident>[];
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Incident / service</th>
            <th>Confidence</th>
            <th>Status</th>
            <th>Signals</th>
            <th>Opened</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <Link href={`/incidents/${item.id}`} className="incident-title">
                  {item.services.join(" / ")}
                </Link>
                <div className="incident-sub mono">
                  INC-{item.id.slice(0, 8).toUpperCase()}
                </div>
              </td>
              <td>
                <span className="severity">
                  {item.confidence >= 0.9
                    ? "High"
                    : item.confidence >= 0.7
                      ? "Elevated"
                      : "Medium"}{" "}
                  <span className="subtle mono">
                    {percent(item.confidence)}
                  </span>
                </span>
              </td>
              <td>
                <span
                  className={`badge ${item.status === "open" ? "red" : "green"}`}
                >
                  {item.status === "open" ? "! OPEN" : "✓ RESOLVED"}
                </span>
              </td>
              <td className="mono">
                {item.signal_count ?? item.signals.length}
              </td>
              <td className="subtle">{relative(item.opened_at)}</td>
              <td>
                <Link
                  href={`/incidents/${item.id}`}
                  aria-label={`Open incident ${item.id}`}
                >
                  ↗
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
