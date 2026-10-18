CREATE TABLE metric_buckets (
    service text NOT NULL, route text NOT NULL, bucket_start timestamptz NOT NULL,
    count bigint NOT NULL, errors bigint NOT NULL, p50_ms double precision NOT NULL,
    p95_ms double precision NOT NULL, p99_ms double precision NOT NULL,
    PRIMARY KEY (service, route, bucket_start)
);
CREATE TABLE baseline_versions (
    version bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, trained_at timestamptz NOT NULL,
    active boolean NOT NULL DEFAULT false
);
CREATE UNIQUE INDEX one_active_baseline ON baseline_versions (active) WHERE active;
CREATE TABLE baselines (
    service text NOT NULL, route text NOT NULL, slot integer NOT NULL, metric text NOT NULL,
    median double precision NOT NULL, mad double precision NOT NULL, n integer NOT NULL,
    low double precision NOT NULL, high double precision NOT NULL, source text NOT NULL,
    version bigint NOT NULL REFERENCES baseline_versions(version),
    PRIMARY KEY (service, route, slot, metric, version)
);
CREATE TABLE sequence_models (
    route text NOT NULL, kind text NOT NULL, version bigint NOT NULL, blob jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (route, kind, version)
);
CREATE TABLE dependency_edges (
    caller text NOT NULL, callee text NOT NULL, kind text NOT NULL,
    first_seen timestamptz NOT NULL, last_seen timestamptz NOT NULL, call_count bigint NOT NULL,
    PRIMARY KEY (caller, callee, kind)
);
CREATE TABLE node_buckets (
    node_id text NOT NULL, bucket_start timestamptz NOT NULL, count bigint NOT NULL,
    errors bigint NOT NULL, p95_ms double precision NOT NULL,
    PRIMARY KEY (node_id, bucket_start)
);
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE past_incidents (
    id uuid PRIMARY KEY REFERENCES incidents(id), signature_text text NOT NULL,
    root_cause_node text NOT NULL, root_cause text NOT NULL, resolution text NOT NULL,
    services text[] NOT NULL, embedding vector(384), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON past_incidents USING hnsw (embedding vector_cosine_ops);
GRANT SELECT, INSERT, UPDATE, DELETE ON metric_buckets, baseline_versions, baselines,
    sequence_models, dependency_edges, node_buckets, past_incidents TO tracelore_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO tracelore_app;

