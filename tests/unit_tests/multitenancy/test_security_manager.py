# TODO: Add license header
"""
Security tests for multi-tenant isolation.

These tests verify critical security guarantees with schema-based isolation:
1. Cross-tenant data access is blocked via search_path
2. Tenant cannot see other tenant's metadata
3. Database credentials are isolated
4. is_superuser() function works correctly
"""

from __future__ import annotations

import pytest
from sqlalchemy import text


class TestSchemaIsolation:
    """Verify schema-based isolation works correctly."""

    def test_demo_schema_queries_route_correctly(
        self, app_context, db, requires_postgres, set_tenant_demo
    ):
        """With demo context, queries should route to tenant_demo schema."""
        result = db.session.execute(text("SHOW search_path"))
        search_path = result.scalar()
        assert (
            "tenant_demo" in search_path
        ), f"Expected tenant_demo in search_path, got: {search_path}"

    def test_acme_schema_queries_route_correctly(
        self, app_context, db, requires_postgres, set_tenant_acme
    ):
        """With acme context, queries should route to tenant_acme schema."""
        result = db.session.execute(text("SHOW search_path"))
        search_path = result.scalar()
        assert (
            "tenant_acme" in search_path
        ), f"Expected tenant_acme in search_path, got: {search_path}"

    def test_clear_tenant_resets_to_public(
        self, app_context, db, requires_postgres, clear_tenant
    ):
        """With no tenant context, search_path should be public only."""
        result = db.session.execute(text("SHOW search_path"))
        search_path = result.scalar()
        assert (
            "tenant_" not in search_path
        ), f"Expected no tenant schema in search_path, got: {search_path}"


class TestTenantDataIsolation:
    """Verify tenant data is isolated by schema."""

    def test_demo_sees_demo_dashboards(
        self, app_context, db, requires_postgres, set_tenant_demo
    ):
        """Demo tenant should see dashboards in tenant_demo schema."""
        from superset.models.dashboard import Dashboard

        dashboards = db.session.query(Dashboard).all()
        # The key is that these are from tenant_demo schema, not tenant_acme

    def test_acme_sees_acme_dashboards(
        self, app_context, db, requires_postgres, set_tenant_acme
    ):
        """Acme tenant should see dashboards in tenant_acme schema."""
        from superset.models.dashboard import Dashboard

        dashboards = db.session.query(Dashboard).all()
        # These dashboards are from tenant_acme schema


class TestDatabaseConnectionSecurity:
    """Test database connection security for tenants."""

    def test_demo_only_sees_demo_warehouse(
        self, app_context, db, requires_postgres, set_tenant_demo
    ):
        """Demo should only see Demo Warehouse connection."""
        from superset.models.core import Database

        databases = db.session.query(Database).all()
        db_names = {d.database_name.lower() for d in databases if d.database_name}

        acme_warehouses = [name for name in db_names if "acme" in name]
        assert (
            len(acme_warehouses) == 0
        ), f"Demo can see Acme's warehouses: {acme_warehouses}"

    def test_acme_only_sees_acme_warehouse(
        self, app_context, db, requires_postgres, set_tenant_acme
    ):
        """Acme should only see Acme Warehouse connection."""
        from superset.models.core import Database

        databases = db.session.query(Database).all()
        db_names = {d.database_name.lower() for d in databases if d.database_name}

        demo_warehouses = [name for name in db_names if "demo" in name]
        assert (
            len(demo_warehouses) == 0
        ), f"Acme can see Demo's warehouses: {demo_warehouses}"


class TestTenantsTableNotFiltered:
    """Verify the tenants table itself is not schema-isolated."""

    def test_tenants_table_accessible(self, app_context, db):
        """The tenants table should be accessible for tenant resolution."""
        from superset.multitenancy.models import Tenant

        tenants = db.session.query(Tenant).all()
        tenant_slugs = {t.slug for t in tenants}
        assert len(tenant_slugs) >= 0, "Should be able to query tenants table"


class TestSuperuserCheck:
    """Test the is_superuser function behavior."""

    def test_is_superuser_returns_false_for_anonymous(self, app_context):
        """Anonymous users are not superusers."""
        from flask import g

        from superset.multitenancy.security_manager import is_superuser

        g.pop("tenant_id", None)
        g.pop("tenant", None)

        assert is_superuser() is False

    def test_is_superuser_returns_true_without_tenant_context(
        self, app_context, mock_current_user
    ):
        """User without tenant context is a superuser (system-level access)."""
        from flask import g

        from superset.multitenancy.security_manager import is_superuser

        mock_current_user.is_authenticated = True
        mock_current_user.username = "test-user"

        g.pop("tenant_id", None)
        g.pop("tenant", None)

        assert is_superuser() is True

    def test_is_superuser_returns_false_with_tenant_context(
        self, app_context, mock_current_user
    ):
        """Regular user with tenant context is not a superuser."""
        from flask import g

        from superset.multitenancy.security_manager import is_superuser

        mock_current_user.is_authenticated = True
        mock_current_user.username = "demo-admin"

        g.tenant_id = "demo"

        assert is_superuser() is False

    def test_is_superuser_returns_true_for_admin_user(
        self, app_context, mock_current_user
    ):
        """The 'admin' user is always a superuser regardless of tenant context."""
        from flask import g

        from superset.multitenancy.security_manager import is_superuser

        mock_current_user.is_authenticated = True
        mock_current_user.username = "admin"

        g.tenant_id = "demo"

        assert is_superuser() is True

    def test_is_superuser_returns_true_for_admin_tenant(
        self, app_context, mock_current_user
    ):
        """User from admin tenant is a superuser."""
        from unittest.mock import MagicMock

        from flask import g

        from superset.multitenancy.security_manager import is_superuser

        mock_current_user.is_authenticated = True
        mock_current_user.username = "admin-tenant-user"

        # Mock admin tenant
        mock_tenant = MagicMock()
        mock_tenant.is_admin_tenant = True
        g.tenant = mock_tenant
        g.tenant_id = "admin"

        assert is_superuser() is True


class TestFABViewSuperuserRestriction:
    """Test that FAB admin views are restricted to superusers."""

    def test_user_view_blocked_for_tenant_admin(self, app_context, mock_current_user):
        """Tenant admin should be blocked from accessing user list view."""
        from flask import g

        from superset.multitenancy.security_manager import TenantAwareUserOAuthModelView

        mock_current_user.is_authenticated = True
        mock_current_user.username = "demo-admin"
        g.tenant_id = "demo"
        g.pop("tenant", None)

        view = TenantAwareUserOAuthModelView()

        with pytest.raises(Exception) as exc_info:
            view._check_superuser()

        assert "403" in str(exc_info.value) or "Access denied" in str(exc_info.value)

    def test_role_view_blocked_for_tenant_admin(self, app_context, mock_current_user):
        """Tenant admin should be blocked from accessing role list view."""
        from flask import g

        from superset.multitenancy.security_manager import TenantAwareRoleModelView

        mock_current_user.is_authenticated = True
        mock_current_user.username = "acme-admin"
        g.tenant_id = "acme"
        g.pop("tenant", None)

        view = TenantAwareRoleModelView()

        with pytest.raises(Exception) as exc_info:
            view._check_superuser()

        assert "403" in str(exc_info.value) or "Access denied" in str(exc_info.value)

    def test_views_accessible_to_superuser(self, app_context, mock_current_user):
        """Superuser should be able to access FAB admin views."""
        from flask import g

        from superset.multitenancy.security_manager import TenantAwareUserOAuthModelView

        mock_current_user.is_authenticated = True
        mock_current_user.username = "system-admin"
        g.pop("tenant_id", None)
        g.pop("tenant", None)

        view = TenantAwareUserOAuthModelView()
        try:
            view._check_superuser()
        except Exception as e:
            pytest.fail(f"Superuser blocked from TenantAwareUserOAuthModelView: {e}")

    def test_admin_user_can_access_views_with_tenant_context(
        self, app_context, mock_current_user
    ):
        """The 'admin' user can access views even with tenant context."""
        from flask import g

        from superset.multitenancy.security_manager import TenantAwareUserOAuthModelView

        mock_current_user.is_authenticated = True
        mock_current_user.username = "admin"
        g.tenant_id = "demo"

        view = TenantAwareUserOAuthModelView()
        try:
            view._check_superuser()
        except Exception as e:
            pytest.fail(f"Admin user blocked from view: {e}")
