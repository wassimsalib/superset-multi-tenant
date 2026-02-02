#!/bin/bash
#
# Start Multi-Tenant Superset Environment
#
# This script:
# 1. Starts Docker containers (superset, keycloak, warehouse)
# 2. Waits for services to be healthy
# 3. Creates warehouse schemas per tenant
# 4. Seeds sample data per tenant
# 5. Creates warehouse connections via Superset API
# 6. Creates example datasets and dashboards
#
# Usage: ./start-multitenant.sh [--fresh]
#   --fresh: Tear down and rebuild everything from scratch

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose-multitenant.yml"
TENANTS=("demo" "acme")
SUPERSET_URL="http://localhost:8088"
WAREHOUSE_HOST="mt-warehouse"
WAREHOUSE_PORT=5432
WAREHOUSE_DB="warehouse"
WAREHOUSE_USER="warehouse"
WAREHOUSE_PASSWORD="warehouse"

# Parse arguments
FRESH_START=false
for arg in "$@"; do
    case $arg in
        --fresh)
            FRESH_START=true
            shift
            ;;
    esac
done

log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] ✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] ⚠${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ✗${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "$COMPOSE_FILE" ]; then
    log_error "Cannot find $COMPOSE_FILE. Run this script from superset-multi-tenant directory."
    exit 1
fi

# Fresh start - tear down everything
if [ "$FRESH_START" = true ]; then
    log "Fresh start requested - tearing down existing environment..."
    docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true
    log_success "Environment torn down"
fi

# Start containers
log "Starting Docker containers..."
docker compose -f "$COMPOSE_FILE" up -d

# Wait for services to be healthy
wait_for_service() {
    local service=$1
    local max_attempts=${2:-60}
    local attempt=0

    log "Waiting for $service to be healthy..."
    while [ $attempt -lt $max_attempts ]; do
        if docker compose -f "$COMPOSE_FILE" ps "$service" 2>/dev/null | grep -q "healthy"; then
            log_success "$service is healthy"
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done
    log_error "$service failed to become healthy after $max_attempts attempts"
    return 1
}

wait_for_service "superset" 90
wait_for_service "db" 30

# Wait for Superset to be fully ready (API responding)
log "Waiting for Superset API to be ready..."
for i in {1..30}; do
    if curl -s -o /dev/null -w "%{http_code}" "$SUPERSET_URL/health" | grep -q "200"; then
        log_success "Superset API is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        log_error "Superset API failed to respond"
        exit 1
    fi
    sleep 2
done

# Get CSRF token and login to get session cookie
get_auth_cookies() {
    local tenant=$1
    local tenant_url="http://${tenant}.app.localhost:8088"

    # For admin operations, we use the base URL with admin credentials
    # Get login page to extract CSRF token
    local csrf_response=$(curl -s -c /tmp/superset_cookies_${tenant}.txt "${tenant_url}/login/" 2>/dev/null || true)
    local csrf_token=$(echo "$csrf_response" | grep -oP 'name="csrf_token"[^>]*value="\K[^"]+' 2>/dev/null || true)

    if [ -z "$csrf_token" ]; then
        # Try alternative CSRF extraction
        csrf_token=$(curl -s -c /tmp/superset_cookies_${tenant}.txt "${tenant_url}/api/v1/security/csrf_token/" 2>/dev/null | jq -r '.result' 2>/dev/null || true)
    fi

    echo "$csrf_token"
}

# Create warehouse schemas and seed data using Docker exec
setup_warehouse() {
    log "Setting up warehouse schemas and sample data..."

    docker exec mt-warehouse psql -U warehouse -d warehouse -c "
    -- Create schemas for each tenant
    CREATE SCHEMA IF NOT EXISTS demo;
    CREATE SCHEMA IF NOT EXISTS acme;

    -- Grant usage to warehouse user
    GRANT ALL ON SCHEMA demo TO warehouse;
    GRANT ALL ON SCHEMA acme TO warehouse;

    -- Create sample tables for DEMO tenant
    DROP TABLE IF EXISTS demo.sales_summary CASCADE;
    CREATE TABLE demo.sales_summary (
        id SERIAL PRIMARY KEY,
        date DATE NOT NULL,
        category VARCHAR(50) NOT NULL,
        region VARCHAR(50) NOT NULL,
        revenue DECIMAL(12,2) NOT NULL,
        units_sold INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    );

    -- Insert sample data for DEMO
    INSERT INTO demo.sales_summary (date, category, region, revenue, units_sold) VALUES
    ('2024-01-01', 'Electronics', 'North', 15000.00, 150),
    ('2024-01-01', 'Electronics', 'South', 12000.00, 120),
    ('2024-01-01', 'Clothing', 'North', 8000.00, 200),
    ('2024-01-01', 'Clothing', 'South', 7500.00, 190),
    ('2024-01-02', 'Electronics', 'North', 16500.00, 165),
    ('2024-01-02', 'Electronics', 'South', 13200.00, 132),
    ('2024-01-02', 'Clothing', 'North', 8800.00, 220),
    ('2024-01-02', 'Clothing', 'South', 8250.00, 206),
    ('2024-01-03', 'Electronics', 'North', 14000.00, 140),
    ('2024-01-03', 'Electronics', 'South', 11500.00, 115),
    ('2024-01-03', 'Clothing', 'North', 7200.00, 180),
    ('2024-01-03', 'Clothing', 'South', 6900.00, 173);

    -- Create sample tables for ACME tenant
    DROP TABLE IF EXISTS acme.orders CASCADE;
    CREATE TABLE acme.orders (
        id SERIAL PRIMARY KEY,
        order_date DATE NOT NULL,
        customer_id INTEGER NOT NULL,
        product_name VARCHAR(100) NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price DECIMAL(10,2) NOT NULL,
        total_amount DECIMAL(12,2) NOT NULL,
        status VARCHAR(20) DEFAULT 'completed',
        created_at TIMESTAMP DEFAULT NOW()
    );

    -- Insert sample data for ACME
    INSERT INTO acme.orders (order_date, customer_id, product_name, quantity, unit_price, total_amount, status) VALUES
    ('2024-01-01', 101, 'Widget Pro', 5, 29.99, 149.95, 'completed'),
    ('2024-01-01', 102, 'Gadget Plus', 3, 49.99, 149.97, 'completed'),
    ('2024-01-01', 103, 'Widget Pro', 10, 29.99, 299.90, 'completed'),
    ('2024-01-02', 101, 'Gadget Plus', 2, 49.99, 99.98, 'shipped'),
    ('2024-01-02', 104, 'Widget Pro', 8, 29.99, 239.92, 'completed'),
    ('2024-01-02', 105, 'Super Gizmo', 1, 199.99, 199.99, 'completed'),
    ('2024-01-03', 102, 'Widget Pro', 15, 29.99, 449.85, 'shipped'),
    ('2024-01-03', 103, 'Super Gizmo', 2, 199.99, 399.98, 'pending'),
    ('2024-01-03', 106, 'Gadget Plus', 5, 49.99, 249.95, 'completed');

    -- Grant permissions on all tables
    GRANT ALL ON ALL TABLES IN SCHEMA demo TO warehouse;
    GRANT ALL ON ALL TABLES IN SCHEMA acme TO warehouse;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA demo TO warehouse;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA acme TO warehouse;
    "

    log_success "Warehouse schemas and sample data created"
}

# Create warehouse database connection for a tenant
create_warehouse_connection() {
    local tenant=$1
    local display_name="${tenant^}"  # Capitalize first letter
    local connection_name="${display_name} Warehouse"
    local tenant_url="http://${tenant}.app.localhost:8088"

    log "Creating warehouse connection for $tenant..."

    # Build the SQLAlchemy URI for the warehouse
    # Note: Using 'mt-warehouse' which is the Docker service name
    local sqlalchemy_uri="postgresql://warehouse:warehouse@mt-warehouse:5432/warehouse"

    # Create database connection via Superset API
    # This requires an authenticated session on the tenant subdomain
    local response=$(curl -s -X POST "${tenant_url}/api/v1/database/" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${ADMIN_TOKEN:-}" \
        -d "{
            \"database_name\": \"${connection_name}\",
            \"sqlalchemy_uri\": \"${sqlalchemy_uri}\",
            \"expose_in_sqllab\": false,
            \"allow_ctas\": false,
            \"allow_cvas\": false,
            \"allow_dml\": false,
            \"allow_run_async\": false,
            \"extra\": \"{\\\"schemas_allowed_for_csv_upload\\\": [\\\"${tenant}\\\"], \\\"metadata_params\\\": {}, \\\"engine_params\\\": {}}\",
            \"impersonate_user\": false
        }" 2>/dev/null)

    if echo "$response" | grep -q '"id"'; then
        log_success "Warehouse connection created for $tenant"
    else
        log_warn "Could not create warehouse connection via API for $tenant (may need manual setup)"
        log "  Response: $response"
    fi
}

# Setup function that runs inside Superset container
setup_tenant_content() {
    log "Setting up tenant content via Superset container..."

    docker exec superset-multi-tenant-superset-1 python << 'PYTHON_SCRIPT'
import os
import sys
sys.path.insert(0, '/app/pythonpath')

# Set up Flask app context
from superset.app import create_app
app = create_app()

with app.app_context():
    from superset.extensions import db
    from superset.models.core import Database
    from superset.connectors.sqla.models import SqlaTable
    from superset.models.slice import Slice
    from superset.models.dashboard import Dashboard
    from superset_multitenancy.context import tenant_context
    from superset_multitenancy.tenants import tenant_database_exists
    import json

    tenants = [
        {
            "slug": "demo",
            "display_name": "Demo Corporation",
            "schema": "demo",
            "table": "sales_summary",
            "chart_name": "Sales by Category",
            "dashboard_name": "Demo Sales Dashboard"
        },
        {
            "slug": "acme",
            "display_name": "ACME Inc",
            "schema": "acme",
            "table": "orders",
            "chart_name": "Orders Overview",
            "dashboard_name": "ACME Orders Dashboard"
        }
    ]

    for tenant in tenants:
        slug = tenant["slug"]

        if not tenant_database_exists(slug):
            print(f"[{slug}] Tenant database not provisioned, skipping")
            continue

        print(f"[{slug}] Setting up tenant content...")

        with tenant_context(slug):
            # Check if warehouse connection exists, create if not
            connection_name = f"{tenant['display_name']} Warehouse"
            warehouse = db.session.query(Database).filter_by(
                database_name=connection_name
            ).first()

            if not warehouse:
                print(f"[{slug}] Creating warehouse connection: {connection_name}")
                warehouse = Database(
                    database_name=connection_name,
                    sqlalchemy_uri="postgresql://warehouse:warehouse@mt-warehouse:5432/warehouse",
                    expose_in_sqllab=False,
                    allow_ctas=False,
                    allow_cvas=False,
                    allow_dml=False,
                    extra=json.dumps({
                        "schemas_allowed_for_file_upload": [tenant["schema"]],
                        "metadata_params": {},
                        "engine_params": {}
                    })
                )
                db.session.add(warehouse)
                db.session.commit()
                print(f"[{slug}] ✓ Warehouse connection created (ID: {warehouse.id})")
            else:
                print(f"[{slug}] Warehouse connection already exists (ID: {warehouse.id})")

            # Check if dataset exists, create if not
            dataset = db.session.query(SqlaTable).filter_by(
                database_id=warehouse.id,
                table_name=tenant["table"],
                schema=tenant["schema"]
            ).first()

            if not dataset:
                print(f"[{slug}] Creating dataset: {tenant['table']}")
                dataset = SqlaTable(
                    database_id=warehouse.id,
                    table_name=tenant["table"],
                    schema=tenant["schema"]
                )
                db.session.add(dataset)
                db.session.commit()

                # Fetch column metadata
                try:
                    dataset.fetch_metadata()
                    db.session.commit()
                    print(f"[{slug}] ✓ Dataset created with metadata (ID: {dataset.id})")
                except Exception as e:
                    print(f"[{slug}] Dataset created but metadata fetch failed: {e}")
            else:
                print(f"[{slug}] Dataset already exists (ID: {dataset.id})")

            # Check if chart exists, create if not
            chart = db.session.query(Slice).filter_by(
                slice_name=tenant["chart_name"]
            ).first()

            if not chart:
                print(f"[{slug}] Creating chart: {tenant['chart_name']}")

                # Build chart params based on tenant
                if slug == "demo":
                    params = {
                        "datasource": f"{dataset.id}__table",
                        "viz_type": "echarts_timeseries_bar",
                        "metrics": [{"label": "Revenue", "expressionType": "SIMPLE", "column": {"column_name": "revenue"}, "aggregate": "SUM"}],
                        "groupby": ["category"],
                        "time_grain_sqla": "P1D",
                        "adhoc_filters": [],
                        "row_limit": 1000
                    }
                else:
                    params = {
                        "datasource": f"{dataset.id}__table",
                        "viz_type": "table",
                        "metrics": [{"label": "Total Amount", "expressionType": "SIMPLE", "column": {"column_name": "total_amount"}, "aggregate": "SUM"}],
                        "groupby": ["product_name", "status"],
                        "adhoc_filters": [],
                        "row_limit": 100
                    }

                chart = Slice(
                    slice_name=tenant["chart_name"],
                    datasource_id=dataset.id,
                    datasource_type="table",
                    viz_type=params["viz_type"],
                    params=json.dumps(params)
                )
                db.session.add(chart)
                db.session.commit()
                print(f"[{slug}] ✓ Chart created (ID: {chart.id})")
            else:
                print(f"[{slug}] Chart already exists (ID: {chart.id})")

            # Check if dashboard exists, create if not
            dashboard = db.session.query(Dashboard).filter_by(
                dashboard_title=tenant["dashboard_name"]
            ).first()

            if not dashboard:
                print(f"[{slug}] Creating dashboard: {tenant['dashboard_name']}")

                # Build layout
                chart_key = f"CHART-{chart.id}"
                position_json = {
                    "ROOT_ID": {"id": "ROOT_ID", "type": "ROOT", "children": ["GRID_ID"]},
                    "GRID_ID": {"id": "GRID_ID", "type": "GRID", "parents": ["ROOT_ID"], "children": ["ROW-0"]},
                    "ROW-0": {
                        "id": "ROW-0",
                        "type": "ROW",
                        "parents": ["ROOT_ID", "GRID_ID"],
                        "children": [chart_key],
                        "meta": {"background": "BACKGROUND_TRANSPARENT"}
                    },
                    chart_key: {
                        "id": chart_key,
                        "type": "CHART",
                        "parents": ["ROOT_ID", "GRID_ID", "ROW-0"],
                        "children": [],
                        "meta": {
                            "chartId": chart.id,
                            "width": 12,
                            "height": 50,
                            "sliceName": chart.slice_name
                        }
                    },
                    "DASHBOARD_VERSION_KEY": "v2"
                }

                json_metadata = {
                    "timed_refresh_immune_slices": [],
                    "expanded_slices": {},
                    "refresh_frequency": 0,
                    "default_filters": "{}",
                    "color_scheme": None,
                    "cross_filters_enabled": False,
                    "native_filter_configuration": []
                }

                dashboard = Dashboard(
                    dashboard_title=tenant["dashboard_name"],
                    position_json=json.dumps(position_json),
                    json_metadata=json.dumps(json_metadata),
                    published=True
                )
                dashboard.slices = [chart]
                db.session.add(dashboard)
                db.session.commit()
                print(f"[{slug}] ✓ Dashboard created (ID: {dashboard.id})")
            else:
                print(f"[{slug}] Dashboard already exists (ID: {dashboard.id})")

            print(f"[{slug}] ✓ Tenant setup complete")

print("\n=== All tenant content setup complete ===")
PYTHON_SCRIPT

    log_success "Tenant content setup complete"
}

# Main execution
log "========================================"
log "Starting Multi-Tenant Superset Setup"
log "========================================"

setup_warehouse
setup_tenant_content

log ""
log "========================================"
log_success "Multi-Tenant Setup Complete!"
log "========================================"
log ""
log "Access your tenants at:"
for tenant in "${TENANTS[@]}"; do
    log "  - http://${tenant}.app.localhost:8088"
done
log ""
log "Platform Admin (DB auth - works on all tenant subdomains):"
log "  admin / admin"
log ""
log "Tenant Viewers (Keycloak OAuth):"
log "  demo-user, acme-user (authenticate via Keycloak)"
log ""
log "Each tenant has:"
log "  - Isolated metadata database (superset_{tenant})"
log "  - Warehouse connection ({Tenant} Warehouse)"
log "  - Sample dataset and dashboard"
log ""
