#!/usr/bin/env python3
"""
Set up Superset database connections to the data warehouse.

Creates per-tenant database connections with tenant-specific credentials
for true PostgreSQL permission-based isolation.

With schema-per-tenant architecture:
- Each connection is created within the tenant's schema context
- search_path is set to tenant_X, public before creating
- No tenant_id column needed - physical schema isolation

Usage:
    docker compose -f docker-compose-multitenant.yml exec superset python /app/docker/scripts/setup-warehouse-connection.py
"""

import sys
sys.path.insert(0, '/app/docker/pythonpath_dev')

from flask import g
from sqlalchemy import text

from superset import create_app, db
from keycloak_multi_tenant.metadata_isolation import tenant_context

app = create_app()

# Per-tenant warehouse configurations
# Each tenant gets their own database user that can ONLY access their schema
TENANT_WAREHOUSE_CONFIGS = [
    {
        "tenant_id": "demo",
        "database_name": "Demo Warehouse",
        "sqlalchemy_uri": "postgresql://tenant_demo_user:demo_secure_pass_123@warehouse:5432/datawarehouse",
    },
    {
        "tenant_id": "acme",
        "database_name": "Acme Warehouse",
        "sqlalchemy_uri": "postgresql://tenant_acme_user:acme_secure_pass_456@warehouse:5432/datawarehouse",
    },
]

# Common settings for all warehouse connections
COMMON_SETTINGS = {
    "expose_in_sqllab": True,
    "allow_run_async": True,
    "allow_ctas": False,
    "allow_cvas": False,
    "allow_dml": False,  # Read-only for safety
    "extra": """{
        "metadata_params": {},
        "engine_params": {},
        "metadata_cache_timeout": {},
        "schemas_allowed_for_file_upload": []
    }"""
}


def setup_warehouse_connections():
    """Create per-tenant warehouse database connections."""
    with app.app_context():
        from superset.models.core import Database

        # Remove any old shared connection
        old_shared = db.session.query(Database).filter_by(
            database_name="Tenant Data Warehouse"
        ).first()
        if old_shared:
            print("Removing old shared 'Tenant Data Warehouse' connection...")
            db.session.delete(old_shared)
            db.session.commit()

        for config in TENANT_WAREHOUSE_CONFIGS:
            tenant_id = config["tenant_id"]
            db_name = config["database_name"]

            # Set tenant context in Flask g for the schema routing
            g.tenant_id = tenant_id

            # Use tenant_context to set search_path for this tenant's schema
            with tenant_context(tenant_id):
                # Check if connection already exists in this tenant's schema
                existing = db.session.query(Database).filter_by(
                    database_name=db_name
                ).first()

                if existing:
                    print(f"Updating '{db_name}' in tenant_{tenant_id} schema...")
                    existing.sqlalchemy_uri = config["sqlalchemy_uri"]
                    existing.expose_in_sqllab = COMMON_SETTINGS["expose_in_sqllab"]
                    existing.allow_run_async = COMMON_SETTINGS["allow_run_async"]
                    existing.allow_ctas = COMMON_SETTINGS["allow_ctas"]
                    existing.allow_cvas = COMMON_SETTINGS["allow_cvas"]
                    existing.allow_dml = COMMON_SETTINGS["allow_dml"]
                    existing.extra = COMMON_SETTINGS["extra"]
                else:
                    print(f"Creating '{db_name}' in tenant_{tenant_id} schema...")
                    database = Database(
                        database_name=db_name,
                        sqlalchemy_uri=config["sqlalchemy_uri"],
                        expose_in_sqllab=COMMON_SETTINGS["expose_in_sqllab"],
                        allow_run_async=COMMON_SETTINGS["allow_run_async"],
                        allow_ctas=COMMON_SETTINGS["allow_ctas"],
                        allow_cvas=COMMON_SETTINGS["allow_cvas"],
                        allow_dml=COMMON_SETTINGS["allow_dml"],
                        extra=COMMON_SETTINGS["extra"],
                    )
                    db.session.add(database)

                db.session.commit()

        print()
        print("=" * 60)
        print("Per-Tenant Warehouse Connections Created")
        print("=" * 60)
        print()
        print("Architecture: Schema-Per-Tenant Isolation")
        print()
        for config in TENANT_WAREHOUSE_CONFIGS:
            print(f"  {config['database_name']}:")
            print(f"    Schema: tenant_{config['tenant_id']}")
            print(f"    User: {config['sqlalchemy_uri'].split('://')[1].split(':')[0]}")
            print(f"    Access: tenant_{config['tenant_id']} warehouse schema ONLY")
            print()
        print("Each tenant's connection is in their own metadata schema")
        print("Cross-tenant visibility is physically impossible")
        print("=" * 60)


if __name__ == "__main__":
    setup_warehouse_connections()
