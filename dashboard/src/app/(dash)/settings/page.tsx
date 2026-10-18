"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { request } from "@/lib/api";
import { keyView, settingsView } from "@/lib/schemas";
import { NewKeyNotice } from "@/components/NewKeyNotice";
import { SDKSetup } from "@/components/SDKSetup";
import { Icon } from "@/components/Icon";
import { PageHeading, QueryState } from "@/components/QueryState";
export default function SettingsPage() {
  const client = useQueryClient(),
    [name, setName] = useState(""),
    [newKey, setNewKey] = useState(""),
    [confirmRevoke, setConfirmRevoke] = useState("");
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
      void client.invalidateQueries({ queryKey: ["keys"] });
    },
  });
  const revoke = useMutation({
    mutationFn: (hash: string) =>
      request(`/settings/keys/${hash}`, keyView, { method: "DELETE" }),
    onSuccess: () => {
      setConfirmRevoke("");
      void client.invalidateQueries({ queryKey: ["keys"] });
    },
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
        eyebrow="Workspace preferences"
        title="Settings"
        description="Connect your services, manage access, and keep your observatory running the way you need."
      />
      <nav className="settings-jump" aria-label="Settings sections">
        <a href="#ingestion-keys">Ingestion keys</a>
        <a href="#retention">Retention & analysis</a>
        <a href="#sdk-setup">Instrumentation</a>
      </nav>
      <section className="settings-section" id="ingestion-keys">
        <div className="settings-intro">
          <span className="section-icon">
            <Icon name="key" size={20} />
          </span>
          <h2>Ingestion API keys</h2>
          <p>Credentials for your SDKs, separate from dashboard access.</p>
        </div>
        <div className="panel settings-content">
          <div className="section-heading">
            <h3>Manage API keys</h3>
            <span className="badge">SDK access</span>
          </div>
          <p className="subtle">
            Give each service a named key. New keys are shown only once.
          </p>
          <form
            className="key-create-form"
            onSubmit={(event) => {
              event.preventDefault();
              create.mutate();
            }}
          >
            <label>
              Key name
              <input
                value={name}
                required
                maxLength={100}
                placeholder="e.g. Checkout production"
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <button disabled={create.isPending}>
              <Icon name="plus" size={15} />
              {create.isPending ? "Creating…" : "Create key"}
            </button>
          </form>
          {newKey && (
            <NewKeyNotice
              key={newKey}
              value={newKey}
              onDismiss={() => setNewKey("")}
            />
          )}
          <QueryState
            loading={keys.isPending}
            error={keys.error}
            retry={() => void keys.refetch()}
          />
          {create.error && (
            <p role="alert" className="error">
              {create.error.message}
            </p>
          )}
          {revoke.error && (
            <p role="alert" className="error">
              {revoke.error.message}
            </p>
          )}
          <div className="key-list">
            {keys.data?.map((key) => (
              <div className="key-row" key={key.key_hash}>
                <div className="key-identity">
                  <Icon name="key" size={16} />
                  <div>
                    <strong>{key.name}</strong>
                    <span className="mono">{key.key_hash.slice(0, 16)}…</span>
                  </div>
                </div>
                <div className="key-row-actions">
                  {key.revoked_at ? (
                    <span className="badge">Revoked</span>
                  ) : confirmRevoke === key.key_hash ? (
                    <div className="revoke-confirm">
                      <span>Revoke this key?</span>
                      <button
                        className="text-button compact"
                        onClick={() => setConfirmRevoke("")}
                      >
                        Cancel
                      </button>
                      <button
                        className="danger compact"
                        disabled={revoke.isPending}
                        onClick={() => revoke.mutate(key.key_hash)}
                      >
                        {revoke.isPending ? "Revoking…" : "Confirm revoke"}
                      </button>
                    </div>
                  ) : (
                    <>
                      <span className="badge green">
                        <span className="badge-dot" />
                        Active
                      </span>
                      <button
                        className="text-button compact revoke-button"
                        onClick={() => setConfirmRevoke(key.key_hash)}
                      >
                        Revoke
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
          {keys.data?.length === 0 && (
            <div className="key-empty">
              <Icon name="key" size={20} />
              <p>Create your first API key to connect a service.</p>
            </div>
          )}
          <p className="settings-footnote">
            <Icon name="info" size={14} />
            Successful keys may remain cached for up to 60 seconds after
            revocation.
          </p>
        </div>
      </section>
      <section className="settings-section" id="retention">
        <div className="settings-intro">
          <span className="section-icon">
            <Icon name="database" size={20} />
          </span>
          <h2>Retention & analysis</h2>
          <p>How your recorded history is retained and analyzed.</p>
        </div>
        <div className="panel settings-content">
          <h3>Operational configuration</h3>
          <QueryState
            loading={settings.isPending}
            error={settings.error}
            retry={() => void settings.refetch()}
          />
          {settings.data && (
            <>
              {!settings.data.tiering_enabled && (
                <div className="notice">
                  Archival is disabled. Retention thresholds apply after{" "}
                  <code>ENABLE_TIERING</code> is enabled. The hot ledger is
                  retained in the meantime.
                </div>
              )}
              <dl className="config-list">
                <div>
                  <dt>Hot ledger retention</dt>
                  <dd>{settings.data.hot_retention_days} days</dd>
                </div>
                <div>
                  <dt>Warm archive retention</dt>
                  <dd>{settings.data.warm_retention_days} days</dd>
                </div>
                <div>
                  <dt>LLM reports</dt>
                  <dd>
                    <span className="badge">
                      {settings.data.llm_enabled ? "Enabled" : "Rules only"}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt>Semantic retrieval</dt>
                  <dd>
                    <span className="badge">
                      {settings.data.rag_enabled ? "Enabled" : "Disabled"}
                    </span>
                  </dd>
                </div>
              </dl>
              <div className="sampling-setting">
                <div>
                  <label htmlFor="sampling">Summarized analytics</label>
                  <p>Optional summaries group similar traces for analysis.</p>
                </div>
                <span className="switch">
                  <input
                    id="sampling"
                    type="checkbox"
                    role="switch"
                    checked={settings.data.lossy_sampling_enabled}
                    onChange={(event) => sampling.mutate(event.target.checked)}
                    disabled={sampling.isPending}
                  />
                  <span className="switch-track" />
                </span>
              </div>
              <p className="hint">
                Summaries cannot be replayed. Lossless archives remain the
                source for replay.
              </p>
              {sampling.error && (
                <p role="alert" className="error">
                  {sampling.error.message}
                </p>
              )}
            </>
          )}
        </div>
      </section>
      <SDKSetup services={settings.data?.services ?? []} />
    </>
  );
}
