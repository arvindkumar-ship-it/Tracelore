REVOKE UPDATE,DELETE ON stream_positions FROM tracelore_app;
CREATE TRIGGER positions_immutable BEFORE UPDATE OR DELETE ON stream_positions
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER positions_no_truncate BEFORE TRUNCATE ON stream_positions
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_mutation();
CREATE INDEX ON events(received_at);
