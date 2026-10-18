CREATE TABLE endpoint_registry (
    service text NOT NULL, route text NOT NULL, first_seen timestamptz NOT NULL,
    last_seen timestamptz NOT NULL, PRIMARY KEY(service,route)
);
INSERT INTO endpoint_registry
    SELECT service,attributes->>'route',min(timestamp),max(ended_at)
    FROM events WHERE type='http.request' GROUP BY service,attributes->>'route';
GRANT SELECT,INSERT,UPDATE ON endpoint_registry TO tracelore_app;
