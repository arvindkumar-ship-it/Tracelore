REVOKE INSERT,UPDATE,DELETE ON archive_manifests FROM tracelore_app;
CREATE OR REPLACE FUNCTION drop_archived_partition(day date, expected_count bigint) RETURNS void
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
DECLARE partition_name text := 'events_' || to_char(day,'YYYYMMDD'); actual_count bigint;
BEGIN
    IF current_user<>'tracelore_owner' THEN RAISE EXCEPTION 'archive owner required'; END IF;
    LOCK TABLE events IN ACCESS EXCLUSIVE MODE;
    EXECUTE format('LOCK TABLE %I IN ACCESS EXCLUSIVE MODE',partition_name);
    EXECUTE format('SELECT count(*) FROM %I',partition_name) INTO actual_count;
    IF actual_count<>expected_count THEN RAISE EXCEPTION 'partition changed during verification'; END IF;
    EXECUTE format('DROP TABLE %I',partition_name);
END $$;
