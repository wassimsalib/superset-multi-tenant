#!/bin/bash
#
# Set up a non-superuser role for the Superset application.
#
# This is CRITICAL for RLS (Row-Level Security) to work properly.
# Superusers bypass RLS by design, so the application must connect
# as a non-superuser for tenant isolation to be enforced.
#
# This script creates:
# - superset_app: Non-superuser role for application connections
#
# The 'superset' superuser is kept for migrations and admin operations.
#

set -e

echo "=== Setting up RLS application user ==="

# Create the non-superuser application role
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create non-superuser role for application
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'superset_app') THEN
            CREATE ROLE superset_app WITH LOGIN PASSWORD 'superset_app_secure_pwd';
            RAISE NOTICE 'Created role superset_app';
        ELSE
            RAISE NOTICE 'Role superset_app already exists';
        END IF;
    END
    \$\$;

    -- Grant CONNECT on database
    GRANT CONNECT ON DATABASE superset TO superset_app;

    -- Grant USAGE on public schema
    GRANT USAGE ON SCHEMA public TO superset_app;

    -- Grant permissions on ALL existing tables (including system tables like alembic_version)
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO superset_app;

    -- Grant permissions on ALL existing sequences
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO superset_app;

    -- Set default privileges for FUTURE tables created by superset user
    ALTER DEFAULT PRIVILEGES FOR ROLE superset IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO superset_app;

    -- Set default privileges for FUTURE sequences
    ALTER DEFAULT PRIVILEGES FOR ROLE superset IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO superset_app;

    -- CRITICAL: The superset_app user should NOT be able to bypass RLS
    -- RLS is enforced by default for non-superusers, but we make it explicit
    -- by NOT granting BYPASSRLS privilege

    RAISE NOTICE 'Granted permissions to superset_app';
EOSQL

echo "=== RLS application user setup complete ==="
echo "The application should connect as 'superset_app' for RLS enforcement."
echo "Migrations should run as 'superset' (superuser) to create tables."
