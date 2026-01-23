#!/bin/bash
#
# Set up the non-superuser application role for RLS enforcement.
#
# This script can be run on an existing database to create the superset_app user.
# The init script (01-setup-rls-user.sh) only runs on fresh database initialization.
#
# RELATIONSHIP TO 01-setup-rls-user.sh:
#   - docker/docker-entrypoint-initdb.d/01-setup-rls-user.sh runs automatically
#     ONLY on fresh PostgreSQL database initialization (first-time container start)
#   - This script (setup-rls-user.sh) is for MANUAL re-runs on existing databases
#     where the init script has already executed or was skipped
#   - Both scripts create the same superset_app user with identical permissions
#
# Usage:
#   ./docker/scripts/setup-rls-user.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_DIR/docker-compose-multitenant.yml"

echo "=== Setting up RLS application user ==="

# Run SQL commands via docker compose exec
docker compose -f "$COMPOSE_FILE" exec -T db psql -U superset -d superset <<-EOSQL
    -- Create non-superuser role for application
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'superset_app') THEN
            CREATE ROLE superset_app WITH LOGIN PASSWORD 'superset_app_secure_pwd';
            RAISE NOTICE 'Created role superset_app';
        ELSE
            -- Update password if role exists
            ALTER ROLE superset_app WITH PASSWORD 'superset_app_secure_pwd';
            RAISE NOTICE 'Role superset_app already exists - updated password';
        END IF;
    END
    \$\$;

    -- Grant CONNECT on database
    GRANT CONNECT ON DATABASE superset TO superset_app;

    -- Grant USAGE on public schema
    GRANT USAGE ON SCHEMA public TO superset_app;

    -- Grant permissions on ALL existing tables
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO superset_app;

    -- Grant permissions on ALL existing sequences
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO superset_app;

    -- Set default privileges for FUTURE tables created by superset user
    ALTER DEFAULT PRIVILEGES FOR ROLE superset IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO superset_app;

    -- Set default privileges for FUTURE sequences
    ALTER DEFAULT PRIVILEGES FOR ROLE superset IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO superset_app;

    -- Verify the user was created correctly
    SELECT rolname, rolsuper, rolcreaterole, rolcreatedb
    FROM pg_roles
    WHERE rolname = 'superset_app';
EOSQL

echo ""
echo "=== RLS application user setup complete ==="
echo ""
echo "IMPORTANT: Restart the Superset container to use the new credentials:"
echo "  docker compose -f docker-compose-multitenant.yml restart superset"
echo ""
