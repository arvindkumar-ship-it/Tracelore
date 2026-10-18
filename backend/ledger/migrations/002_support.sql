CREATE TABLE api_keys (
    key_hash text PRIMARY KEY, name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), revoked_at timestamptz
);
CREATE TABLE chain_findings (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, stream_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('gap','break')), from_sequence bigint NOT NULL,
    to_sequence bigint NOT NULL, found_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (stream_id, kind, from_sequence, to_sequence)
);
CREATE TABLE stream_positions (
    stream_id text NOT NULL, sequence bigint NOT NULL, event_id uuid NOT NULL,
    event_hash text NOT NULL, ended_at timestamptz NOT NULL,
    PRIMARY KEY (stream_id, sequence), UNIQUE (event_id)
);
CREATE TABLE event_outbox (
    event_id uuid PRIMARY KEY, stream_id text NOT NULL, body jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), published_at timestamptz
);
CREATE INDEX ON event_outbox (created_at) WHERE published_at IS NULL;
CREATE TABLE snapshots (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, cut_ended_at timestamptz NOT NULL,
    cut_stream_id text NOT NULL, cut_sequence bigint NOT NULL, event_count bigint NOT NULL,
    state jsonb NOT NULL, digest text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(cut_ended_at, cut_stream_id, cut_sequence)
);
CREATE TABLE incidents (
    id uuid PRIMARY KEY, status text NOT NULL CHECK (status IN ('open','resolved')),
    opened_at timestamptz NOT NULL, closed_at timestamptz, start_event_id uuid,
    start_time timestamptz NOT NULL, services text[] NOT NULL, confidence double precision NOT NULL,
    signals jsonb NOT NULL, updated_at timestamptz NOT NULL, version bigint NOT NULL DEFAULT 1
);
CREATE INDEX ON incidents (status, opened_at DESC, id);
CREATE TABLE incident_changes (
    version bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id uuid NOT NULL REFERENCES incidents(id), body jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE rca_reports (
    incident_id uuid NOT NULL REFERENCES incidents(id), version integer NOT NULL,
    report jsonb NOT NULL, source text NOT NULL CHECK (source IN ('llm','rules')),
    created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (incident_id, version)
);
CREATE TABLE archive_manifests (
    day date PRIMARY KEY, object_key text NOT NULL, manifest jsonb NOT NULL,
    verified_at timestamptz NOT NULL, archived_at timestamptz,
    cold boolean NOT NULL DEFAULT false
);
GRANT SELECT, INSERT, UPDATE, DELETE ON api_keys, chain_findings, snapshots,
    stream_positions, event_outbox, incidents, incident_changes, rca_reports, archive_manifests TO tracelore_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO tracelore_app;

