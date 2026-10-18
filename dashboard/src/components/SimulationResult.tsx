import type { z } from "zod";
import { simulationView } from "@/lib/schemas";
import { percent, duration } from "@/lib/format";
import { Icon } from "./Icon";

export function SimulationResult({
  data,
  busy,
}: {
  data?: z.infer<typeof simulationView>;
  busy: boolean;
}) {
  return (
    <section className="panel simulation-result" aria-busy={busy}>
      <div className="section-heading">
        <h2>Projected outcome</h2>
        <span className="badge cyan">
          <Icon name="flask" size={12} />
          Simulated
        </span>
      </div>
      {data ? (
        <>
          <div className="simulation-verdict">
            <span className="eyebrow">Simulation assessment</span>
            <h3>{data.verdict}</h3>
          </div>
          <div className="simulation-bars">
            {["error_rate", "p95_ms", "p99_ms"].map((metric) => {
              const report = data!,
                before = report.original[metric],
                after = report.counterfactual[metric],
                maximum = Math.max(before, after, 0.001),
                format = metric === "error_rate" ? percent : duration;
              return (
                <div className="simulation-metric" key={metric}>
                  <h3>
                    {metric === "error_rate"
                      ? "Request error rate"
                      : metric === "p95_ms"
                        ? "p95 latency"
                        : "p99 latency"}
                  </h3>
                  {[
                    ["Recorded", before],
                    ["Simulated", after],
                  ].map(([label, value], index) => (
                    <div className="bar-row" key={String(label)}>
                      <span className="subtle">{label}</span>
                      <div className="bar-track">
                        <div
                          className={`bar-fill ${index ? "after" : ""}`}
                          style={{
                            width: `${(Number(value) / maximum) * 100}%`,
                          }}
                        />
                      </div>
                      <span className="mono">{format(Number(value))}</span>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
          <p className={data.unsimulatable_percent >= 20 ? "notice" : "subtle"}>
            {data.unsimulatable_percent.toFixed(1)}% of traces could not be
            simulated.
          </p>
          <div className="simulation-assumptions">
            <h3>Assumptions & limits</h3>
            <ul className="assumptions">
              {data.assumptions.map((value) => (
                <li key={value}>{value}</li>
              ))}
            </ul>
          </div>
          <div className="result-digest mono">
            result {data.result_digest.slice(0, 24)}…
          </div>
        </>
      ) : (
        <div className="empty simulation-empty">
          <span className="empty-icon">
            <Icon name="flask" size={26} />
          </span>
          <h3>
            {busy
              ? "Replaying the possibilities…"
              : "Your results will appear here."}
          </h3>
          <p>
            {busy
              ? "Applying your intervention to the recorded traces. The projected outcome will appear here."
              : "Choose an intervention and run a simulation to compare the recorded outcome with a possible one."}
          </p>
          <span className="hint">
            Every result includes its assumptions and evidence limits.
          </span>
        </div>
      )}
    </section>
  );
}
