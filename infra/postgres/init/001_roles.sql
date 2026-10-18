\getenv owner_password TRACELORE_OWNER_PASSWORD
\getenv app_password TRACELORE_APP_PASSWORD
CREATE ROLE tracelore_owner LOGIN PASSWORD :'owner_password';
CREATE ROLE tracelore_app LOGIN PASSWORD :'app_password';
ALTER DATABASE tracelore OWNER TO tracelore_owner;
GRANT CONNECT ON DATABASE tracelore TO tracelore_app;
GRANT USAGE,CREATE ON SCHEMA public TO tracelore_owner;
GRANT USAGE ON SCHEMA public TO tracelore_app;
CREATE EXTENSION IF NOT EXISTS vector;
