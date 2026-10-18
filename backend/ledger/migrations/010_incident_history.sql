ALTER TABLE incidents ADD COLUMN signal_count bigint NOT NULL DEFAULT 0;
UPDATE incidents SET signal_count=jsonb_array_length(signals);
CREATE TABLE incident_signals (
    signal_id text PRIMARY KEY, incident_id uuid NOT NULL REFERENCES incidents(id),
    detected_at timestamptz NOT NULL, body jsonb NOT NULL
);
INSERT INTO incident_signals
    SELECT signal->>'id',i.id,(signal->>'detected_at')::timestamptz,signal
    FROM incidents i CROSS JOIN LATERAL jsonb_array_elements(i.signals) signal
    ON CONFLICT DO NOTHING;
CREATE INDEX ON incident_signals(incident_id,detected_at,signal_id);
GRANT SELECT,INSERT ON incident_signals TO tracelore_app;
