#!/bin/bash
#
# Bootstrap the multi-tenant demo environment.
#
# This script sets up:
# 1. Tenant schemas for metadata isolation (tenant_demo, tenant_acme)
# 2. Keycloak realms and users for demo/acme tenants
# 3. Per-tenant warehouse database connections
# 4. Sample dashboards for each tenant
#
# Prerequisites:
#   docker compose -f docker-compose-multitenant.yml up -d
#
# Usage:
#   ./docker/scripts/demo-bootstrap.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_DIR/docker-compose-multitenant.yml"

cd "$PROJECT_DIR"

# Helper function to run docker compose with the correct file
dc() {
    docker compose -f "$COMPOSE_FILE" "$@"
}

echo ""
echo "============================================"
echo "Multi-Tenant Demo Bootstrap"
echo "============================================"
echo ""

# Wait for services to be ready
echo "[1/6] Waiting for services to be ready..."

# Wait for db
echo "  Waiting for database..."
until dc exec -T db pg_isready -U superset > /dev/null 2>&1; do
    sleep 1
done
echo "  ✓ Database ready"

# Wait for warehouse
echo "  Waiting for warehouse..."
until dc exec -T warehouse pg_isready -U warehouse_admin -d datawarehouse > /dev/null 2>&1; do
    sleep 1
done
echo "  ✓ Warehouse ready"

# Wait for superset
echo "  Waiting for Superset..."
until dc exec -T superset curl -sf http://localhost:8088/health > /dev/null 2>&1; do
    sleep 2
done
echo "  ✓ Superset ready"

# Wait for keycloak (check realms endpoint - health endpoint changed in v26)
echo "  Waiting for Keycloak..."
until curl -sf http://localhost:8180/realms/master > /dev/null 2>&1; do
    sleep 2
done
echo "  ✓ Keycloak ready"
echo ""

# Step 2: Setup tenant schemas for metadata isolation
echo "[2/6] Setting up tenant schemas for metadata isolation..."

TENANTS="demo acme"

for tenant in $TENANTS; do
    schema="tenant_${tenant}"

    dc exec -T db psql -U superset -d superset <<EOSQL
    -- Create tenant schema
    CREATE SCHEMA IF NOT EXISTS ${schema};

    -- Clone Superset metadata table structures from public to tenant schema
    -- Note: LIKE ... INCLUDING ALL includes constraints, indexes, defaults, etc.

    -- Core metadata tables
    CREATE TABLE IF NOT EXISTS ${schema}.dashboards (LIKE public.dashboards INCLUDING ALL);
    CREATE TABLE IF NOT EXISTS ${schema}.slices (LIKE public.slices INCLUDING ALL);
    CREATE TABLE IF NOT EXISTS ${schema}.tables (LIKE public.tables INCLUDING ALL);
    CREATE TABLE IF NOT EXISTS ${schema}.dbs (LIKE public.dbs INCLUDING ALL);
    CREATE TABLE IF NOT EXISTS ${schema}.saved_query (LIKE public.saved_query INCLUDING ALL);

    -- Related tables
    CREATE TABLE IF NOT EXISTS ${schema}.table_columns (LIKE public.table_columns INCLUDING ALL);
    CREATE TABLE IF NOT EXISTS ${schema}.sql_metrics (LIKE public.sql_metrics INCLUDING ALL);

    -- Junction tables (many-to-many relationships)
    CREATE TABLE IF NOT EXISTS ${schema}.dashboard_slices (LIKE public.dashboard_slices INCLUDING ALL);
    CREATE TABLE IF NOT EXISTS ${schema}.dashboard_user (LIKE public.dashboard_user INCLUDING ALL);
    CREATE TABLE IF NOT EXISTS ${schema}.sqlatable_user (LIKE public.sqlatable_user INCLUDING ALL);
    CREATE TABLE IF NOT EXISTS ${schema}.slice_user (LIKE public.slice_user INCLUDING ALL);

    -- SQL Lab query history
    CREATE TABLE IF NOT EXISTS ${schema}.query (LIKE public.query INCLUDING ALL);

    -- Additional metadata tables
    CREATE TABLE IF NOT EXISTS ${schema}.tab_state (LIKE public.tab_state INCLUDING ALL);
    CREATE TABLE IF NOT EXISTS ${schema}.table_schema (LIKE public.table_schema INCLUDING ALL);

    -- Grant permissions to superset user on the new schema
    GRANT ALL ON SCHEMA ${schema} TO superset;
    GRANT ALL ON ALL TABLES IN SCHEMA ${schema} TO superset;
    GRANT ALL ON ALL SEQUENCES IN SCHEMA ${schema} TO superset;

    -- Grant permissions to superset_app user (the app connects as this user)
    GRANT USAGE ON SCHEMA ${schema} TO superset_app;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ${schema} TO superset_app;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ${schema} TO superset_app;

    -- Set default privileges for future tables
    ALTER DEFAULT PRIVILEGES IN SCHEMA ${schema}
        GRANT ALL ON TABLES TO superset;
    ALTER DEFAULT PRIVILEGES IN SCHEMA ${schema}
        GRANT ALL ON SEQUENCES TO superset;
    ALTER DEFAULT PRIVILEGES IN SCHEMA ${schema}
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO superset_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA ${schema}
        GRANT USAGE, SELECT ON SEQUENCES TO superset_app;
EOSQL

    echo "  ✓ Created schema: ${schema}"
done

echo ""

# Step 3: Setup Keycloak
echo "[3/6] Configuring Keycloak realms and users..."
./docker/scripts/setup-keycloak.sh 2>&1 | grep -E "^(\[|✓|Demo|Acme|Keycloak)" | head -20
echo ""

# Step 4: Setup warehouse connections (with superuser)
echo "[4/6] Creating per-tenant warehouse connections..."
dc exec -T \
    -e DATABASE_APP_USER=superset \
    -e DATABASE_APP_PASSWORD=superset \
    superset python /app/docker/scripts/setup-warehouse-connection.py 2>&1 | grep -E "(Creating|✓|Demo|Acme)" | head -10
echo "  ✓ Warehouse connections created"
echo ""

# Step 5: Setup tenant dashboards (with superuser)
echo "[5/6] Creating tenant dashboards and charts..."
dc exec -T \
    -e DATABASE_APP_USER=superset \
    -e DATABASE_APP_PASSWORD=superset \
    superset python /app/docker/scripts/setup-tenant-dashboards.py 2>&1 | grep -E "(\[SUCCESS\]|Summary)" | head -5
echo "  ✓ Dashboards created"
echo ""

# Step 6: Verify schema isolation
echo "[6/6] Verifying schema isolation..."
dc exec -T db psql -U superset -d superset -c "
    SELECT schema_name
    FROM information_schema.schemata
    WHERE schema_name LIKE 'tenant_%'
    ORDER BY schema_name;
" | grep -E "tenant_" && echo "  ✓ Tenant schemas verified" || echo "  ✗ Schema verification failed"
echo ""

echo "============================================"
echo "Bootstrap Complete!"
echo "============================================"
echo ""
echo "Access the demo:"
echo ""
echo "  Demo Tenant:  http://demo.app.localhost"
echo "    Users: demo-admin/demo123, demo-user/demo123"
echo ""
echo "  Acme Tenant:  http://acme.app.localhost"
echo "    Users: acme-admin/acme123, acme-user/acme123"
echo ""
echo "  Keycloak:     http://localhost:8180 (admin/admin)"
echo ""
echo "Make sure /etc/hosts has:"
echo "  127.0.0.1 demo.app.localhost acme.app.localhost host.docker.internal"
echo ""
echo "Schema Isolation:"
echo "  Each tenant's metadata is in its own PostgreSQL schema:"
echo "    - tenant_demo: Demo tenant's dashboards, charts, datasets"
echo "    - tenant_acme: Acme tenant's dashboards, charts, datasets"
echo "    - public: Shared tables (users, roles, permissions)"
echo ""
echo "Run tests:"
echo "  docker compose -f docker-compose-multitenant.yml exec superset pytest /app/docker/pythonpath_dev/keycloak_multi_tenant/tests/ -v"
echo ""
