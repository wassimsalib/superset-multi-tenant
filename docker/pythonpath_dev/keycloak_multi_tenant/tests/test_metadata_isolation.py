# TODO: Add Apache license header
"""
Tests for schema-based metadata isolation module.

These tests verify that:
1. Tenant schema routing works correctly via search_path
2. The tenant_context manager sets search_path correctly
3. Flask g.tenant_id is properly read for schema routing
4. Tenant schemas exist and have correct structure
"""

import pytest
from sqlalchemy import text


class TestTenantContext:
    """Test tenant context management functions."""

    def test_get_current_tenant_id_from_flask_g(self, app_context):
        """get_current_tenant_id should read from Flask g."""
        from flask import g

        from keycloak_multi_tenant.metadata_isolation import get_current_tenant_id

        # Not set
        if hasattr(g, "tenant_id"):
            delattr(g, "tenant_id")
        assert get_current_tenant_id() is None

        # Set it
        g.tenant_id = "flask_test"
        assert get_current_tenant_id() == "flask_test"

        # Cleanup
        delattr(g, "tenant_id")

    def test_get_current_tenant_id_returns_none_without_context(self, app_context):
        """Without request context, should return None."""
        from flask import g

        from keycloak_multi_tenant.metadata_isolation import get_current_tenant_id

        # Ensure no tenant_id set
        if hasattr(g, "tenant_id"):
            delattr(g, "tenant_id")

        result = get_current_tenant_id()
        assert result is None

    def test_get_tenant_schema(self, app_context):
        """get_tenant_schema should convert tenant_id to schema name."""
        from keycloak_multi_tenant.metadata_isolation import get_tenant_schema

        assert get_tenant_schema("demo") == "tenant_demo"
        assert get_tenant_schema("acme") == "tenant_acme"
        assert get_tenant_schema("my_tenant") == "tenant_my_tenant"


class TestSchemaRouting:
    """Test schema-based routing via search_path."""

    def test_tenant_context_sets_search_path(self, app_context, db, requires_postgres):
        """tenant_context manager should set search_path."""
        from keycloak_multi_tenant.metadata_isolation import tenant_context

        # Before: should be public (or default)
        result = db.session.execute(text("SHOW search_path"))
        before = result.scalar()

        with tenant_context("demo"):
            # Inside: should include tenant_demo
            result = db.session.execute(text("SHOW search_path"))
            inside = result.scalar()
            assert "tenant_demo" in inside, f"Expected tenant_demo in search_path, got: {inside}"
            assert "public" in inside, f"Expected public in search_path, got: {inside}"

        # After: should be reset to public
        result = db.session.execute(text("SHOW search_path"))
        after = result.scalar()
        assert "tenant_demo" not in after, f"Expected tenant_demo not in search_path after context, got: {after}"

    def test_tenant_context_isolates_queries(self, app_context, db, requires_postgres):
        """Queries inside tenant_context should route to tenant schema."""
        from keycloak_multi_tenant.metadata_isolation import tenant_context

        # Skip this test if tenant_demo schema doesn't exist
        result = db.session.execute(
            text("SELECT 1 FROM pg_namespace WHERE nspname = 'tenant_demo'")
        )
        if result.fetchone() is None:
            pytest.skip("tenant_demo schema not found - run bootstrap script first")

        with tenant_context("demo"):
            # Should be able to query tables in tenant_demo via search_path
            # Check that the dashboards table is accessible (it should exist in tenant schema)
            result = db.session.execute(text("SELECT COUNT(*) FROM dashboards"))
            count = result.scalar()
            # Just verify we can query - count can be 0 if no dashboards created yet
            assert count >= 0, "Should be able to query dashboards table via search_path"


class TestTenantSchemaExists:
    """Test that tenant schemas exist with correct structure."""

    def test_tenant_demo_schema_exists(self, app_context, db, requires_postgres):
        """tenant_demo schema should exist."""
        # Use pg_namespace instead of information_schema.schemata
        # because information_schema only shows schemas owned by current user
        result = db.session.execute(
            text("""
                SELECT nspname
                FROM pg_namespace
                WHERE nspname = 'tenant_demo'
            """)
        )
        assert result.fetchone() is not None, "tenant_demo schema should exist"

    def test_tenant_acme_schema_exists(self, app_context, db, requires_postgres):
        """tenant_acme schema should exist."""
        # Use pg_namespace instead of information_schema.schemata
        # because information_schema only shows schemas owned by current user
        result = db.session.execute(
            text("""
                SELECT nspname
                FROM pg_namespace
                WHERE nspname = 'tenant_acme'
            """)
        )
        assert result.fetchone() is not None, "tenant_acme schema should exist"


class TestTenantSchemaStructure:
    """Test that tenant schemas have correct table structure."""

    EXPECTED_TABLES = [
        "dashboards",
        "slices",
        "tables",
        "dbs",
        "saved_query",
        "table_columns",
        "sql_metrics",
        "dashboard_slices",
        "dashboard_user",
        "sqlatable_user",
        "slice_user",
    ]

    @pytest.mark.parametrize("table_name", EXPECTED_TABLES)
    def test_tenant_demo_has_table(self, app_context, db, requires_postgres, table_name):
        """tenant_demo schema should have all required tables."""
        # Use pg_class/pg_namespace instead of information_schema.tables
        # because information_schema only shows tables owned by current user
        result = db.session.execute(
            text("""
                SELECT c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'tenant_demo'
                AND c.relname = :table_name
                AND c.relkind = 'r'
            """),
            {"table_name": table_name}
        )
        assert result.fetchone() is not None, f"tenant_demo.{table_name} should exist"

    @pytest.mark.parametrize("table_name", EXPECTED_TABLES)
    def test_tenant_acme_has_table(self, app_context, db, requires_postgres, table_name):
        """tenant_acme schema should have all required tables."""
        # Use pg_class/pg_namespace instead of information_schema.tables
        # because information_schema only shows tables owned by current user
        result = db.session.execute(
            text("""
                SELECT c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'tenant_acme'
                AND c.relname = :table_name
                AND c.relkind = 'r'
            """),
            {"table_name": table_name}
        )
        assert result.fetchone() is not None, f"tenant_acme.{table_name} should exist"


class TestPublicSchemaShared:
    """Test that public schema has shared tables."""

    SHARED_TABLES = [
        "ab_user",
        "ab_role",
        "ab_permission",
        "ab_permission_view",
        "ab_user_role",
    ]

    @pytest.mark.parametrize("table_name", SHARED_TABLES)
    def test_public_has_shared_table(self, app_context, db, requires_postgres, table_name):
        """public schema should have shared Flask-AppBuilder tables."""
        result = db.session.execute(
            text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = :table_name
            """),
            {"table_name": table_name}
        )
        assert result.fetchone() is not None, f"public.{table_name} should exist"
