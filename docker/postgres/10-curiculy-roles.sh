#!/bin/sh
# First-start setup for the Postgres container (docker-entrypoint-initdb.d).
# Runs once, as the postgres superuser, when the data directory is empty.
#
# Two roles keep families apart (see docs/6-planning/decision-records/data-tier.md):
#   curiculy_owner  owns the database and tables; runs migrations, startup
#                   upkeep and backups. BYPASSRLS so backups see every family.
#   curiculy_app    what the API connects as: owns nothing, cannot bypass
#                   row-level security, may only read and write rows.
set -eu

: "${CURICULY_OWNER_PASSWORD:?set CURICULY_OWNER_PASSWORD}"
: "${CURICULY_APP_PASSWORD:?set CURICULY_APP_PASSWORD}"
DB="${CURICULY_DB:-curiculy}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
    -v owner_pw="$CURICULY_OWNER_PASSWORD" -v app_pw="$CURICULY_APP_PASSWORD" -v db="$DB" <<'SQL'
CREATE ROLE curiculy_owner LOGIN BYPASSRLS CREATEDB PASSWORD :'owner_pw';
CREATE ROLE curiculy_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD :'app_pw';
CREATE DATABASE :"db" OWNER curiculy_owner;
SQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DB" -v db="$DB" <<'SQL'
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db" TO curiculy_app;
GRANT USAGE ON SCHEMA public TO curiculy_app;
ALTER DEFAULT PRIVILEGES FOR ROLE curiculy_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO curiculy_app;
ALTER DEFAULT PRIVILEGES FOR ROLE curiculy_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO curiculy_app;
SQL
