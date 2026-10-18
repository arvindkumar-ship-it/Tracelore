CREATE TABLE inventory (item_id integer PRIMARY KEY, stock integer NOT NULL);
INSERT INTO inventory SELECT generate_series(1,100),1000000;
GRANT SELECT,UPDATE ON inventory TO tracelore_app;
