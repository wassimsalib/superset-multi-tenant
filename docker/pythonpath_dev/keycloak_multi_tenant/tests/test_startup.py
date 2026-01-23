# TODO: Add Apache license header
"""
Startup and setup verification tests.

These tests verify that the multi-tenant system is properly configured:
1. Required tables exist
2. Migrations have run
3. Tenants are configured
4. Tenant schemas exist (schema-based isolation)

Run these first to verify basic setup before running other tests.
"""

import pytest
from sqlalchemy import text


class TestDatabaseSetup:
    """Verify database is properly configured."""

    def test_database_connection(self, app_context, db):
        """Verify we can connect to the database."""
        result = db.session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    def test_is_postgresql(self, app_context, db):
        """Verify we're running on PostgreSQL (required for schema isolation)."""
        dialect = db.engine.dialect.name
        assert dialect == "postgresql", f"Expected PostgreSQL, got {dialect}"

    def test_tenants_table_exists(self, app_context, db):
        """Verify tenants table was created by migration."""
        result = db.session.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'tenants'
                )
            """)
        )
        assert result.scalar(), "tenants table not found - run migrations"


class TestTenantsConfigured:
    """Verify tenants are properly configured."""

    def test_demo_tenant_exists(self, app_context, db):
        """Verify demo tenant is configured."""
        from keycloak_multi_tenant.models import Tenant

        tenant = db.session.query(Tenant).filter_by(tenant_id="demo").first()
        assert tenant is not None, "Demo tenant not found - run setup-keycloak.sh"
        assert tenant.is_active, "Demo tenant is not active"

    def test_acme_tenant_exists(self, app_context, db):
        """Verify acme tenant is configured."""
        from keycloak_multi_tenant.models import Tenant

        tenant = db.session.query(Tenant).filter_by(tenant_id="acme").first()
        assert tenant is not None, "Acme tenant not found - run setup-keycloak.sh"
        assert tenant.is_active, "Acme tenant is not active"

    def test_tenants_have_keycloak_config(self, app_context, db):
        """Verify tenants have Keycloak configuration."""
        from keycloak_multi_tenant.models import Tenant

        tenants = db.session.query(Tenant).filter_by(is_active=True).all()

        for tenant in tenants:
            assert tenant.keycloak_realm, f"{tenant.tenant_id} missing keycloak_realm"
            assert tenant.keycloak_client_id, f"{tenant.tenant_id} missing keycloak_client_id"
            assert tenant.keycloak_client_secret, f"{tenant.tenant_id} missing keycloak_client_secret"


class TestTenantSchemasExist:
    """Verify tenant schemas are created (schema-based isolation)."""

    def test_tenant_demo_schema_exists(self, app_context, db, requires_postgres):
        """Verify tenant_demo schema exists."""
        # Use pg_namespace instead of information_schema.schemata
        # because information_schema only shows schemas owned by current user
        result = db.session.execute(
            text("""
                SELECT nspname
                FROM pg_namespace
                WHERE nspname = 'tenant_demo'
            """)
        )
        assert result.fetchone() is not None, "tenant_demo schema not found - run migrations"

    def test_tenant_acme_schema_exists(self, app_context, db, requires_postgres):
        """Verify tenant_acme schema exists."""
        # Use pg_namespace instead of information_schema.schemata
        # because information_schema only shows schemas owned by current user
        result = db.session.execute(
            text("""
                SELECT nspname
                FROM pg_namespace
                WHERE nspname = 'tenant_acme'
            """)
        )
        assert result.fetchone() is not None, "tenant_acme schema not found - run migrations"


class TestWarehouseConnections:
    """Verify warehouse database connections are configured."""

    def test_demo_warehouse_exists(self, app_context, db, set_tenant_demo):
        """Verify Demo Warehouse connection exists in demo tenant schema."""
        result = db.session.execute(
            text("""
                SELECT database_name
                FROM dbs
                WHERE LOWER(database_name) LIKE '%demo%warehouse%'
            """)
        )
        row = result.fetchone()
        assert row is not None, "Demo Warehouse not found - run setup-warehouse-connection.py"

    def test_acme_warehouse_exists(self, app_context, db, set_tenant_acme):
        """Verify Acme Warehouse connection exists in acme tenant schema."""
        result = db.session.execute(
            text("""
                SELECT database_name
                FROM dbs
                WHERE LOWER(database_name) LIKE '%acme%warehouse%'
            """)
        )
        row = result.fetchone()
        assert row is not None, "Acme Warehouse not found - run setup-warehouse-connection.py"


class TestDashboardsExist:
    """Verify tenant dashboards are created."""

    def test_demo_has_dashboards(self, app_context, db, requires_postgres, set_tenant_demo):
        """Verify demo tenant has dashboards."""
        from superset.models.dashboard import Dashboard

        count = db.session.query(Dashboard).count()
        assert count > 0, "Demo has no dashboards - run setup-tenant-dashboards.py"

    def test_acme_has_dashboards(self, app_context, db, requires_postgres, set_tenant_acme):
        """Verify acme tenant has dashboards."""
        from superset.models.dashboard import Dashboard

        count = db.session.query(Dashboard).count()
        assert count > 0, "Acme has no dashboards - run setup-tenant-dashboards.py"

    def test_acme_has_exclusive_dashboard(self, app_context, db, requires_postgres, set_tenant_acme):
        """Verify Acme has the exclusive executive dashboard."""
        from superset.models.dashboard import Dashboard

        executive = db.session.query(Dashboard).filter(
            Dashboard.dashboard_title.ilike("%executive%")
        ).first()
        assert executive is not None, "Acme missing Executive Dashboard"


class TestModuleImports:
    """Verify all required modules can be imported."""

    def test_import_metadata_isolation(self):
        """Can import metadata_isolation module."""
        from keycloak_multi_tenant.metadata_isolation import (
            get_current_tenant_id,
            get_tenant_schema,
            setup_metadata_isolation,
            tenant_context,
        )

    def test_import_middleware(self):
        """Can import middleware module."""
        from keycloak_multi_tenant.middleware import setup_tenant_middleware

    def test_import_models(self):
        """Can import Tenant model."""
        from keycloak_multi_tenant.models import Tenant

    def test_import_tenant_resolver(self):
        """Can import tenant resolver."""
        from keycloak_multi_tenant.tenant_resolver import TenantResolver

    def test_import_keycloak_client(self):
        """Can import Keycloak client."""
        from keycloak_multi_tenant.keycloak_client import KeycloakMultiTenantClient
