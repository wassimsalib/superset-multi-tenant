#!/usr/bin/env python3
"""
Create template dashboards and charts for tenants.

This script creates:
1. Datasets pointing to each tenant's warehouse tables
2. Common template charts (sales trends, revenue breakdown, etc.)
3. A dashboard containing these charts
4. [Acme only] A unique visual to demonstrate metadata isolation

With schema-per-tenant architecture:
- Each tenant's metadata is created in their own schema
- search_path is set to tenant_X, public before creating objects
- No tenant_id column needed - physical schema isolation

Usage:
    docker compose -f docker-compose-multitenant.yml exec superset python /app/docker/scripts/setup-tenant-dashboards.py

To create for a specific tenant only:
    docker compose -f docker-compose-multitenant.yml exec superset python /app/docker/scripts/setup-tenant-dashboards.py --tenant demo
"""

import argparse
import json
import sys
sys.path.insert(0, '/app/docker/pythonpath_dev')

from flask import g

from superset import create_app, db
from keycloak_multi_tenant.metadata_isolation import tenant_context

app = create_app()


# Template definitions - reusable across tenants
# Each tenant gets these same charts, but pointing to their own data

TEMPLATE_DATASETS = [
    {
        "table_name": "sales",
        "schema": None,  # Will be set to tenant_{tenant_id}
        "description": "Sales transactions data",
    },
    {
        "table_name": "customers",
        "schema": None,
        "description": "Customer information",
    },
    {
        "table_name": "monthly_metrics",
        "schema": None,
        "description": "Monthly aggregated metrics",
    },
]

# Chart definitions - viz_type and params
TEMPLATE_CHARTS = [
    {
        "slice_name": "Sales Trend",
        "viz_type": "echarts_timeseries_line",
        "description": "Monthly sales over time",
        "dataset": "sales",
        "params": {
            "datasource": None,  # Set dynamically
            "viz_type": "echarts_timeseries_line",
            "x_axis": "sale_date",
            "time_grain_sqla": "P1M",
            "metrics": [{"label": "Total Sales", "expressionType": "SQL", "sqlExpression": "SUM(total_amount)"}],
            "groupby": [],
            "row_limit": 10000,
            "truncate_metric": True,
            "show_legend": True,
            "legendType": "scroll",
            "legendOrientation": "top",
            "x_axis_title": "Month",
            "y_axis_title": "Revenue ($)",
            "rich_tooltip": True,
            "tooltipTimeFormat": "%B %Y",
        },
    },
    {
        "slice_name": "Revenue by Region",
        "viz_type": "pie",
        "description": "Sales distribution across regions",
        "dataset": "sales",
        "params": {
            "datasource": None,
            "viz_type": "pie",
            "metric": {"label": "Total Revenue", "expressionType": "SQL", "sqlExpression": "SUM(total_amount)"},
            "groupby": ["region"],
            "row_limit": 100,
            "sort_by_metric": True,
            "color_scheme": "supersetColors",
            "show_legend": True,
            "show_labels": True,
            "label_type": "key_percent",
            "number_format": "$,.0f",
            "donut": False,
            "innerRadius": 30,
            "outerRadius": 80,
        },
    },
    {
        "slice_name": "Total Revenue",
        "viz_type": "big_number_total",
        "description": "Total revenue KPI",
        "dataset": "monthly_metrics",
        "params": {
            "datasource": None,
            "viz_type": "big_number_total",
            "metric": {"label": "Total Revenue", "expressionType": "SQL", "sqlExpression": "SUM(total_revenue)"},
            "subheader": "All Time Revenue",
            "y_axis_format": "$,.0f",
            "header_font_size": 0.5,
            "subheader_font_size": 0.2,
        },
    },
    {
        "slice_name": "Customers by Industry",
        "viz_type": "echarts_timeseries_bar",
        "description": "Customer count by industry",
        "dataset": "customers",
        "params": {
            "datasource": None,
            "viz_type": "dist_bar",
            "metrics": [{"label": "Customer Count", "expressionType": "SQL", "sqlExpression": "COUNT(*)"}],
            "groupby": ["industry"],
            "row_limit": 50,
            "color_scheme": "supersetColors",
            "show_legend": False,
            "y_axis_format": ",d",
            "x_axis_label": "Industry",
            "y_axis_label": "Customers",
            "bar_stacked": False,
            "order_desc": True,
        },
    },
    {
        "slice_name": "Monthly Orders",
        "viz_type": "big_number_total",
        "description": "Total orders KPI",
        "dataset": "monthly_metrics",
        "params": {
            "datasource": None,
            "viz_type": "big_number_total",
            "metric": {"label": "Total Orders", "expressionType": "SQL", "sqlExpression": "SUM(total_orders)"},
            "subheader": "All Time Orders",
            "y_axis_format": ",d",
            "header_font_size": 0.5,
            "subheader_font_size": 0.2,
        },
    },
]

# Dashboard layout (positions for a 12-column grid)
DASHBOARD_LAYOUT = {
    "Sales Trend": {"col": 0, "row": 0, "size_x": 8, "size_y": 4},
    "Revenue by Region": {"col": 8, "row": 0, "size_x": 4, "size_y": 4},
    "Total Revenue": {"col": 0, "row": 4, "size_x": 4, "size_y": 2},
    "Monthly Orders": {"col": 4, "row": 4, "size_x": 4, "size_y": 2},
    "Customers by Industry": {"col": 0, "row": 6, "size_x": 12, "size_y": 4},
}

# Acme-only unique chart
ACME_UNIQUE_CHART = {
    "slice_name": "🦅 Acme Executive Summary",
    "viz_type": "big_number_total",
    "description": "Acme-exclusive executive summary - demonstrates metadata isolation",
    "dataset": "monthly_metrics",
    "params": {
        "datasource": None,
        "viz_type": "big_number_total",
        "metric": {"label": "Avg Order Value", "expressionType": "SQL", "sqlExpression": "AVG(avg_order_value)"},
        "subheader": "Average Order Value (Acme Exclusive)",
        "y_axis_format": "$,.2f",
        "header_font_size": 0.5,
        "subheader_font_size": 0.15,
    },
}


def get_or_create_dataset(database, table_name, schema, description, tenant_id):
    """Get existing or create new dataset."""
    from superset.connectors.sqla.models import SqlaTable

    existing = db.session.query(SqlaTable).filter_by(
        database_id=database.id,
        table_name=table_name,
        schema=schema,
    ).first()

    if existing:
        print(f"  [EXISTS] Dataset: {schema}.{table_name}")
        return existing

    dataset = SqlaTable(
        table_name=table_name,
        schema=schema,
        database=database,
        description=description,
    )

    db.session.add(dataset)
    db.session.flush()  # Get ID

    # Fetch columns from database
    try:
        dataset.fetch_metadata()
    except Exception as e:
        print(f"  [WARN] Could not fetch metadata for {table_name}: {e}")

    print(f"  [CREATED] Dataset: {schema}.{table_name}")
    return dataset


def get_or_create_chart(slice_name, viz_type, params, dataset, description, tenant_id):
    """Get existing or create new chart."""
    from superset.models.slice import Slice

    # Charts are tenant-specific - include tenant in the name
    tenant_slice_name = f"{slice_name} ({tenant_id})"

    existing = db.session.query(Slice).filter_by(
        slice_name=tenant_slice_name,
    ).first()

    if existing:
        print(f"  [EXISTS] Chart: {tenant_slice_name}")
        return existing

    slice_name = tenant_slice_name  # Use tenant-specific name

    # Set datasource in params
    params = params.copy()
    params["datasource"] = f"{dataset.id}__table"

    chart = Slice(
        slice_name=slice_name,
        viz_type=viz_type,
        datasource_type="table",
        datasource_id=dataset.id,
        params=json.dumps(params),
        description=description,
    )

    db.session.add(chart)
    db.session.flush()

    print(f"  [CREATED] Chart: {slice_name}")
    return chart


def create_dashboard(title, charts, layout, tenant_id, slug_suffix="overview"):
    """Create a dashboard with the given charts."""
    from superset.models.dashboard import Dashboard

    slug = f"{tenant_id}-{slug_suffix}"

    existing = db.session.query(Dashboard).filter_by(slug=slug).first()

    if existing:
        print(f"  [EXISTS] Dashboard: {title} (slug: {slug})")
        return existing

    # Build position JSON for the dashboard
    # Superset uses a specific format for dashboard layouts
    position_json = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]},
        "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID", "meta": {"text": title}},
    }

    # Add charts to layout
    row_id = 0
    for chart in charts:
        # Remove tenant suffix to match layout keys (e.g., "Sales Trend (demo)" -> "Sales Trend")
        base_name = chart.slice_name.rsplit(" (", 1)[0] if " (" in chart.slice_name else chart.slice_name
        chart_layout = layout.get(base_name, {})
        if not chart_layout:
            chart_layout = {"col": 0, "row": row_id, "size_x": 6, "size_y": 4}
            row_id += 4

        chart_id = f"CHART-{chart.id}"
        row_container_id = f"ROW-{chart.id}"

        position_json[chart_id] = {
            "type": "CHART",
            "id": chart_id,
            "children": [],
            "parents": ["ROOT_ID", "GRID_ID", row_container_id],
            "meta": {
                "width": chart_layout.get("size_x", 6),
                "height": chart_layout.get("size_y", 4) * 8,  # Convert to pixels roughly
                "chartId": chart.id,
                "sliceName": chart.slice_name,
            },
        }

        if row_container_id not in position_json:
            position_json[row_container_id] = {
                "type": "ROW",
                "id": row_container_id,
                "children": [],
                "parents": ["ROOT_ID", "GRID_ID"],
                "meta": {"background": "BACKGROUND_TRANSPARENT"},
            }
            position_json["GRID_ID"]["children"].append(row_container_id)

        position_json[row_container_id]["children"].append(chart_id)

    dashboard = Dashboard(
        dashboard_title=title,
        slug=slug,
        position_json=json.dumps(position_json),
        published=True,
    )

    # Link charts
    dashboard.slices = charts

    db.session.add(dashboard)
    db.session.flush()

    print(f"  [CREATED] Dashboard: {title}")
    return dashboard


def setup_tenant_dashboards(tenant_id):
    """Create datasets, charts, and dashboard for a tenant."""
    from superset.models.core import Database
    from keycloak_multi_tenant.models import Tenant

    print(f"\n{'='*60}")
    print(f"Setting up dashboards for tenant: {tenant_id}")
    print(f"{'='*60}")

    # Set tenant context in Flask g
    g.tenant_id = tenant_id

    # Use tenant_context to set search_path for this tenant's schema
    with tenant_context(tenant_id):
        print(f"[SCHEMA] Set search_path = tenant_{tenant_id}, public")

        # Verify tenant exists (for Keycloak integration)
        # Note: Tenant table is in public schema, still accessible
        tenant = db.session.query(Tenant).filter_by(tenant_id=tenant_id).first()
        if not tenant:
            print(f"[ERROR] Tenant '{tenant_id}' not found in database")
            return False

        # Find the tenant's warehouse database connection
        db_name = f"{tenant_id.title()} Warehouse"
        database = db.session.query(Database).filter_by(database_name=db_name).first()

        if not database:
            # Try alternate naming
            database = db.session.query(Database).filter(
                Database.database_name.ilike(f"%{tenant_id}%warehouse%")
            ).first()

        if not database:
            print(f"[ERROR] Database connection '{db_name}' not found")
            print("  Run setup-warehouse-connection.py first")
            return False

        print(f"Using database: {database.database_name}")

        schema = f"tenant_{tenant_id}"
        datasets = {}
        charts = []

        # Step 1: Create datasets
        print("\n[Datasets]")
        for ds_config in TEMPLATE_DATASETS:
            dataset = get_or_create_dataset(
                database=database,
                table_name=ds_config["table_name"],
                schema=schema,
                description=ds_config["description"],
                tenant_id=tenant_id,
            )
            datasets[ds_config["table_name"]] = dataset

        # Step 2: Create charts
        print("\n[Charts]")
        for chart_config in TEMPLATE_CHARTS:
            dataset = datasets.get(chart_config["dataset"])
            if not dataset:
                print(f"  [SKIP] Chart '{chart_config['slice_name']}' - missing dataset")
                continue

            chart = get_or_create_chart(
                slice_name=chart_config["slice_name"],
                viz_type=chart_config["viz_type"],
                params=chart_config["params"],
                dataset=dataset,
                description=chart_config["description"],
                tenant_id=tenant_id,
            )
            charts.append(chart)

        # Step 3: Create dashboard
        print("\n[Dashboard]")
        dashboard = create_dashboard(
            title=f"{tenant_id.title()} Business Overview",
            charts=charts,
            layout=DASHBOARD_LAYOUT,
            tenant_id=tenant_id,
        )

        # Step 4: Acme-only unique chart
        if tenant_id == "acme":
            print("\n[Acme Exclusive]")
            dataset = datasets.get(ACME_UNIQUE_CHART["dataset"])
            if dataset:
                acme_chart = get_or_create_chart(
                    slice_name=ACME_UNIQUE_CHART["slice_name"],
                    viz_type=ACME_UNIQUE_CHART["viz_type"],
                    params=ACME_UNIQUE_CHART["params"],
                    dataset=dataset,
                    description=ACME_UNIQUE_CHART["description"],
                    tenant_id=tenant_id,
                )

                # Create Acme-exclusive dashboard
                acme_dashboard = create_dashboard(
                    title="🦅 Acme Executive Dashboard",
                    charts=[acme_chart],
                    layout={"🦅 Acme Executive Summary": {"col": 0, "row": 0, "size_x": 12, "size_y": 4}},
                    tenant_id=tenant_id,
                    slug_suffix="executive",
                )

        db.session.commit()
        print(f"\n[SUCCESS] Tenant '{tenant_id}' dashboards created!")
        return True


def main():
    parser = argparse.ArgumentParser(description="Create tenant dashboards")
    parser.add_argument(
        "--tenant",
        type=str,
        help="Specific tenant ID (default: all tenants)",
    )
    args = parser.parse_args()

    with app.app_context():
        from keycloak_multi_tenant.models import Tenant

        if args.tenant:
            tenants = [args.tenant]
        else:
            # Get all active tenants
            all_tenants = db.session.query(Tenant).filter_by(is_active=True).all()
            tenants = [t.tenant_id for t in all_tenants]

        print("=" * 60)
        print("Tenant Dashboard Setup")
        print("=" * 60)
        print(f"Tenants to process: {', '.join(tenants)}")

        success_count = 0
        for tenant_id in tenants:
            if setup_tenant_dashboards(tenant_id):
                success_count += 1

        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"Processed: {len(tenants)} tenant(s)")
        print(f"Successful: {success_count}")
        print(f"Failed: {len(tenants) - success_count}")

        if success_count > 0:
            print("\nTemplate charts created for all tenants:")
            for chart in TEMPLATE_CHARTS:
                print(f"  - {chart['slice_name']}")

            print("\nAcme-exclusive content:")
            print(f"  - {ACME_UNIQUE_CHART['slice_name']}")
            print("  - 🦅 Acme Executive Dashboard")

        print("=" * 60)


if __name__ == "__main__":
    main()
