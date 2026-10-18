"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { request } from "@/lib/api";
import { keyView, settingsView } from "@/lib/schemas";
import { PageHeading, QueryState } from "@/components/QueryState";
export default function SettingsPage() {
  const client = useQueryClient(),
    [name, setName] = useState(""),
    [newKey, setNewKey] = useState(""),
    [copied, setCopied] = useState(false);
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: () => request("/settings", settingsView),
  });
  const keys = useQuery({
    queryKey: ["keys"],
    queryFn: () => request("/settings/keys", z.array(keyView)),
  });
  const create = useMutation({
    mutationFn: () =>
      request(
        "/settings/keys",
        z.object({ key: z.string(), name: z.string() }),
        { method: "POST", body: JSON.stringify({ name }) },
      ),
    onSuccess: (value) => {
      setNewKey(value.key);
      setName("");
      setCopied(false);
      void client.invalidateQueries({ queryKey: ["keys"] });
    },
  });
  const revoke = useMutation({
    mutationFn: (hash: string) =>
      request(`/settings/keys/${hash}`, keyView, { method: "DELETE" }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["keys"] }),
  });
  const sampling = useMutation({
    mutationFn: (enabled: boolean) =>
      request("/settings/sampling", z.object({ enabled: z.boolean() }), {
        method: "PUT",
        body: JSON.stringify({ enabled }),
      }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["settings"] }),
  });
  return (
    <>
      <PageHeading
        eyebrow="05 / WORKSPACE"
        title="Connect. Retain. Verify."
        description="Manage ingestion credentials and inspect the operational configuration."
      />
      <div className="grid-two">
        <section className="panel">
          <h2>Ingestion API keys</h2>
          <p className="subtle">
            SDK credentials are separate from dashboard access. New keys are
            shown once.
          </p>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              create.mutate();
            }}
            className="form-grid"
          >
            <label>
              Key name
              <input
                value={name}
                required
                maxLength={100}
                placeholder="Checkout production"
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <div style={{ paddingTop: 25 }}>
              <button disabled={create.isPending}>Create key</button>
            </div>
          </form>
          {newKey && (
            <div className="notice">
              <p style={{ color: "inherit" }}>
                Copy this key now, then store it as TRACELORE_API_KEY.
              </p>
              <pre>{newKey}</pre>
              <div className="actions">
                <button
                  className="ghost"
                  onClick={() => {
                    void navigator.clipboard
                      .writeText(newKey)
                      .then(() => setCopied(true));
                  }}
                >
                  {copied ? "Copied" : "Copy key"}
                </button>
                <button className="ghost" onClick={() => setNewKey("")}>
                  Dismiss
                </button>
              </div>
            </div>
          )}
          <QueryState
            loading={keys.isPending}
            error={keys.error ?? create.error ?? revoke.error}
            retry={() => void keys.refetch()}
          />
          {keys.data?.map((key) => (
            <div className="inspector-row" key={key.key_hash}>
              <div>
                <b>{key.name}</b>
                <div className="subtle mono">{key.key_hash.slice(0, 16)}…</div>
              </div>
              {key.revoked_at ? (
                <span className="badge">REVOKED</span>
              ) : (
                <button
                  className="ghost"
                  disabled={revoke.isPending}
                  onClick={() => revoke.mutate(key.key_hash)}
                >
                  Revoke
                </button>
              )}
            </div>
          ))}
          <p className="hint" style={{ marginTop: 18 }}>
            Ingest authentication caches successful keys for up to 60 seconds
            after revocation.
          </p>
        </section>
        <section className="panel">
          <h2>Retention & analysis</h2>
          <QueryState
            loading={settings.isPending}
            error={settings.error}
            retry={() => void settings.refetch()}
          />
          {settings.data && (
            <>
              {!settings.data.tiering_enabled && (
                <p className="notice">
                  Archival is disabled. Configured thresholds apply after
                  ENABLE_TIERING is enabled; the hot ledger is retained in the
                  meantime.
                </p>
              )}
              <div className="inspector-row">
                <span>Hot ledger</span>
                <b>{settings.data.hot_retention_days} days</b>
              </div>
              <div className="inspector-row">
                <span>Warm archives</span>
                <b>{settings.data.warm_retention_days} days</b>
              </div>
              <div className="inspector-row">
                <span>LLM reports</span>
                <b>{settings.data.llm_enabled ? "Enabled" : "Rules only"}</b>
              </div>
              <div className="inspector-row">
                <span>Semantic retrieval</span>
                <b>{settings.data.rag_enabled ? "Enabled" : "Disabled"}</b>
              </div>
              <div className="divider" />
              <label>
                <input
                  type="checkbox"
                  style={{ width: "auto", display: "inline", marginRight: 10 }}
                  checked={settings.data.lossy_sampling_enabled}
                  onChange={(event) => sampling.mutate(event.target.checked)}
                  disabled={sampling.isPending}
                />
                Enable optional summarized analytics
              </label>
              <p className="error" style={{ fontSize: 11 }}>
                Summaries represent clusters of similar traces and cannot be
                replayed. Lossless archives remain the replay source.
              </p>
              {sampling.error && (
                <p className="error">{sampling.error.message}</p>
              )}
            </>
          )}
        </section>
      </div>
      <section className="panel" id="sdk-setup">
        <h2>Instrument a FastAPI service</h2>
        <p>
          Install sdk/python, set TRACELORE_API_KEY, TRACELORE_SERVICE, and
          TRACELORE_ENDPOINT, then attach the ASGI middleware.
        </p>
        <pre>{`from tracelore import Tracelore, load_config\nfrom tracelore.integrations.fastapi import TraceloreMiddleware\n\nclient = Tracelore(load_config())\nclient.start()\napp.add_middleware(TraceloreMiddleware, client=client)\n# Call client.shutdown() in the application's lifespan teardown.`}</pre>
        <p className="subtle">
          Enable HTTP, asyncpg/SQLAlchemy and Redis adapters to reconstruct
          dependency paths. SDK events contain hashes and metadata rather than
          request bodies or SQL.
        </p>
      </section>
    </>
  );
}
