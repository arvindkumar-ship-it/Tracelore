CREATE TABLE runtime_settings (key text PRIMARY KEY, value jsonb NOT NULL);
CREATE TABLE trace_summaries (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, day date NOT NULL,
    representative_trace uuid NOT NULL, trace_count bigint NOT NULL, quantiles jsonb NOT NULL,
    mode text NOT NULL DEFAULT 'summarized' CHECK (mode='summarized')
);
GRANT SELECT,INSERT,UPDATE,DELETE ON runtime_settings,trace_summaries TO tracelore_app;
GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO tracelore_app;
