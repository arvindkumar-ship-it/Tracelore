CREATE TABLE projection_outbox (
    event_id uuid PRIMARY KEY, topic text NOT NULL, message_key text NOT NULL,
    body jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT,INSERT ON projection_outbox TO tracelore_app;
