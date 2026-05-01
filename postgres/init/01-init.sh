#!/usr/bin/env bash
# Creates the keycloak database inside the shared Postgres instance.
# Runs automatically on first boot via docker-entrypoint-initdb.d.
# POSTGRES_USER and POSTGRES_DB are already created by the Docker entrypoint
# before this script runs.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    CREATE DATABASE keycloak;
    GRANT ALL PRIVILEGES ON DATABASE keycloak TO "$POSTGRES_USER";
SQL
