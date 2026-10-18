CREATE TABLE events (
    event_id uuid NOT NULL, trace_id uuid NOT NULL, span_id uuid NOT NULL,
    parent_span_id uuid, stream_id text NOT NULL, sequence bigint NOT NULL CHECK (sequence > 0),
    timestamp timestamptz NOT NULL, ended_at timestamptz NOT NULL,
    duration_ms double precision NOT NULL CHECK (duration_ms >= 0), service text NOT NULL,
    type text NOT NULL, status text NOT NULL CHECK (status IN ('ok', 'error')),
    attributes jsonb NOT NULL, payload_hash char(64) NOT NULL,
    prev_event_hash char(64) NOT NULL, event_hash char(64) NOT NULL,
    ingest_seq bigint GENERATED ALWAYS AS IDENTITY,
    received_at timestamptz NOT NULL DEFAULT now(), late boolean NOT NULL DEFAULT false,
    PRIMARY KEY (event_id, ended_at)
) PARTITION BY RANGE (ended_at);
CREATE INDEX ON events (trace_id, timestamp);
CREATE INDEX ON events (service, ended_at);
CREATE INDEX ON events (type, ended_at);
CREATE INDEX ON events (stream_id, sequence);
CREATE INDEX ON events (ended_at, stream_id, sequence);

CREATE FUNCTION forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'events is append-only' USING ERRCODE = '42501';
END $$;
CREATE TRIGGER events_immutable BEFORE UPDATE OR DELETE ON events
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER events_no_truncate BEFORE TRUNCATE ON events
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_mutation();

CREATE FUNCTION ensure_partition(day date) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE partition_name text := 'events_' || to_char(day, 'YYYYMMDD');
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext(partition_name));
    IF to_regclass(partition_name) IS NOT NULL THEN RETURN; END IF;
    EXECUTE format('CREATE TABLE %I PARTITION OF events FOR VALUES FROM (%L) TO (%L)',
                   partition_name, day::timestamptz, (day + 1)::timestamptz);
    EXECUTE format('CREATE TRIGGER partition_no_truncate BEFORE TRUNCATE ON %I '
                   'FOR EACH STATEMENT EXECUTE FUNCTION forbid_mutation()', partition_name);
    EXECUTE format('GRANT SELECT, INSERT ON %I TO tracelore_app', partition_name);
END $$;
REVOKE ALL ON FUNCTION ensure_partition(date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ensure_partition(date) TO tracelore_app;
GRANT SELECT, INSERT ON events TO tracelore_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO tracelore_app;

