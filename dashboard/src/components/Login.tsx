"use client";
import { useState } from "react";
import { z } from "zod";
import { request } from "@/lib/api";
import { Brand } from "./Brand";
import { Icon } from "./Icon";

export function Login({ onSuccess }: { onSuccess: () => void }) {
  const [secret, setSecret] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <div className="login">
      <div className="login-top">
        <Brand />
        <span>System observatory</span>
      </div>
      <div className="login-layout">
        <section className="login-story">
          <div className="eyebrow">Clarity, when it matters.</div>
          <h1>
            Every incident.
            <br />A clearer picture.
          </h1>
          <p>
            Follow the evidence from the first deviation to the fix. Understand
            what happened, and what comes next.
          </p>
          <div className="login-capabilities">
            <div>
              <Icon name="activity" />
              <span>
                <strong>Find the first signal</strong>
                <span>Spot deviations across your services.</span>
              </span>
            </div>
            <div>
              <Icon name="graph" />
              <span>
                <strong>Follow the evidence</strong>
                <span>Trace the path back to its root cause.</span>
              </span>
            </div>
            <div>
              <Icon name="flask" />
              <span>
                <strong>Test your next move</strong>
                <span>Replay history. Explore a fix before you ship.</span>
              </span>
            </div>
          </div>
          <div className="login-note">
            <Icon name="shield" size={16} />
            Recorded facts. Repeatable answers.
          </div>
        </section>
        <form
          className="login-card"
          onSubmit={async (event) => {
            event.preventDefault();
            setBusy(true);
            setError("");
            try {
              const result = await request(
                "/auth/token",
                z.object({
                  access_token: z.string(),
                  expires_at: z.string(),
                  token_type: z.string(),
                }),
                { method: "POST", body: JSON.stringify({ secret }) },
              );
              sessionStorage.setItem("tracelore.token", result.access_token);
              setSecret("");
              onSuccess();
            } catch (error) {
              setError(
                error instanceof Error ? error.message : "Unable to sign in",
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          <span className="login-lock">
            <Icon name="key" size={22} />
          </span>
          <h2>Welcome to your workspace</h2>
          <p>Sign in to open your system observatory.</p>
          <label htmlFor="dashboard-secret">Dashboard secret</label>
          <input
            id="dashboard-secret"
            type="password"
            placeholder="Enter your dashboard secret"
            autoComplete="current-password"
            aria-invalid={!!error}
            aria-describedby={error ? "login-error" : "login-help"}
            required
            value={secret}
            onChange={(event) => setSecret(event.target.value)}
          />
          {error && (
            <p id="login-error" role="alert" className="error">
              {error}
            </p>
          )}
          <button disabled={busy}>
            {busy ? "Connecting…" : "Open observatory"}
            <Icon name="arrow" size={16} />
          </button>
          <p id="login-help" className="login-help">
            Use the secret generated during setup. Your session stays in this
            browser tab.
          </p>
          <div className="login-card-footer">
            <Icon name="shield" size={14} />
            Secure dashboard access
          </div>
        </form>
      </div>
      <div className="login-footer">
        <span>© {new Date().getFullYear()} Tracelore</span>
        <span>Observed state. Evidence. Understanding.</span>
      </div>
    </div>
  );
}
