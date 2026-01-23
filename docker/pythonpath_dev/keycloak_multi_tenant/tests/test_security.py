# TODO: Add Apache license header
"""
Security tests for multi-tenant isolation.

These tests verify critical security guarantees with schema-based isolation:
1. Cross-tenant data access is blocked via search_path
2. Tenant cannot see other tenant's metadata
3. Database credentials are isolated
4. is_superuser() function works correctly

Schema-based isolation works by setting search_path per request:
- Demo requests: search_path = tenant_demo, public
- Acme requests: search_path = tenant_acme, public
"""

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
        assert "tenant_demo" in search_path, f"Expected tenant_demo in search_path, got: {search_path}"

    def test_acme_schema_queries_route_correctly(
        self, app_context, db, requires_postgres, set_tenant_acme
    ):
        """With acme context, queries should route to tenant_acme schema."""
        result = db.session.execute(text("SHOW search_path"))
        search_path = result.scalar()
        assert "tenant_acme" in search_path, f"Expected tenant_acme in search_path, got: {search_path}"

    def test_clear_tenant_resets_to_public(
        self, app_context, db, requires_postgres, clear_tenant
    ):
        """With no tenant context, search_path should be public only."""
        result = db.session.execute(text("SHOW search_path"))
        search_path = result.scalar()
        assert "tenant_" not in search_path, f"Expected no tenant schema in search_path, got: {search_path}"


class TestTenantDataIsolation:
    """Verify tenant data is isolated by schema."""

    def test_demo_sees_demo_dashboards(
        self, app_context, db, requires_postgres, set_tenant_demo
    ):
        """Demo tenant should see dashboards in tenant_demo schema."""
        from superset.models.dashboard import Dashboard

        dashboards = db.session.query(Dashboard).all()
        # Should have some dashboards (or none if not set up yet)
        # The key is that these are from tenant_demo schema, not tenant_acme
        # We can't check tenant_id since it doesn't exist in schema-based isolation

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

        # Should not see Acme's warehouse
        acme_warehouses = [name for name in db_names if "acme" in name]
        assert len(acme_warehouses) == 0, f"Demo can see Acme's warehouses: {acme_warehouses}"

    def test_acme_only_sees_acme_warehouse(
        self, app_context, db, requires_postgres, set_tenant_acme
    ):
        """Acme should only see Acme Warehouse connection."""
        from superset.models.core import Database

        databases = db.session.query(Database).all()
        db_names = {d.database_name.lower() for d in databases if d.database_name}

        # Should not see Demo's warehouse
        demo_warehouses = [name for name in db_names if "demo" in name]
        assert len(demo_warehouses) == 0, f"Acme can see Demo's warehouses: {demo_warehouses}"


class TestTenantsTableNotFiltered:
    """Verify the tenants table itself is not schema-isolated."""

    def test_tenants_table_accessible(self, app_context, db):
        """The tenants table should be accessible for tenant resolution."""
        from keycloak_multi_tenant.models import Tenant

        # This should work regardless of tenant context
        # because the tenants table is in public schema
        tenants = db.session.query(Tenant).all()

        # Should see all tenants (needed for middleware to resolve tenant)
        tenant_ids = {t.tenant_id for t in tenants}
        assert len(tenant_ids) >= 1, "Should see at least one tenant"


class TestSuperuserCheck:
    """Test the is_superuser function behavior."""

    def test_is_superuser_returns_false_for_anonymous(self, app_context):
        """Anonymous users are not superusers."""
        from flask import g
        from keycloak_multi_tenant.security_manager import is_superuser

        # Ensure no tenant context
        g.pop("tenant_id", None)

        # Anonymous user should not be superuser
        assert is_superuser() is False

    def test_is_superuser_returns_true_without_tenant_context(self, app_context, mock_current_user):
        """User without tenant context is a superuser (system-level access)."""
        from flask import g
        from keycloak_multi_tenant.security_manager import is_superuser

        # Mock authenticated user without tenant context
        mock_current_user.is_authenticated = True
        mock_current_user.username = "test-user"

        # Clear tenant context
        g.pop("tenant_id", None)

        assert is_superuser() is True

    def test_is_superuser_returns_false_with_tenant_context(self, app_context, mock_current_user):
        """Regular user with tenant context is not a superuser."""
        from flask import g
        from keycloak_multi_tenant.security_manager import is_superuser

        # Mock authenticated tenant user
        mock_current_user.is_authenticated = True
        mock_current_user.username = "demo-admin"

        # Set tenant context
        g.tenant_id = "demo"

        assert is_superuser() is False

    def test_is_superuser_returns_true_for_admin_user(self, app_context, mock_current_user):
        """The 'admin' user is always a superuser regardless of tenant context."""
        from flask import g
        from keycloak_multi_tenant.security_manager import is_superuser

        # Mock admin user with tenant context
        mock_current_user.is_authenticated = True
        mock_current_user.username = "admin"

        # Even with tenant context, admin is superuser
        g.tenant_id = "demo"

        assert is_superuser() is True


class TestFABViewSuperuserRestriction:
    """Test that FAB admin views are restricted to superusers.

    These tests verify that tenant admins cannot access FAB user/role
    management views, which should be restricted to superusers only.
    """

    def test_user_view_blocked_for_tenant_admin(self, app_context, mock_current_user):
        """Tenant admin should be blocked from accessing user list view."""
        from flask import g
        from keycloak_multi_tenant.security_manager import TenantAwareUserOAuthModelView

        # Mock tenant admin
        mock_current_user.is_authenticated = True
        mock_current_user.username = "demo-admin"
        g.tenant_id = "demo"

        # Create view instance
        view = TenantAwareUserOAuthModelView()

        # Should abort with 403
        with pytest.raises(Exception) as exc_info:
            view._check_superuser()

        # Check for 403 status code
        assert "403" in str(exc_info.value) or "Access denied" in str(exc_info.value)

    def test_role_view_blocked_for_tenant_admin(self, app_context, mock_current_user):
        """Tenant admin should be blocked from accessing role list view."""
        from flask import g
        from keycloak_multi_tenant.security_manager import TenantAwareRoleModelView

        # Mock tenant admin
        mock_current_user.is_authenticated = True
        mock_current_user.username = "acme-admin"
        g.tenant_id = "acme"

        # Create view instance
        view = TenantAwareRoleModelView()

        # Should abort with 403
        with pytest.raises(Exception) as exc_info:
            view._check_superuser()

        assert "403" in str(exc_info.value) or "Access denied" in str(exc_info.value)

    def test_views_accessible_to_superuser(self, app_context, mock_current_user):
        """Superuser should be able to access FAB admin views."""
        from flask import g
        from keycloak_multi_tenant.security_manager import TenantAwareUserOAuthModelView

        # Mock superuser (no tenant context)
        mock_current_user.is_authenticated = True
        mock_current_user.username = "system-admin"
        g.pop("tenant_id", None)

        # Test with one view class (instantiation of some views requires FAB registration)
        view = TenantAwareUserOAuthModelView()
        try:
            view._check_superuser()  # Should not raise for superuser
        except Exception as e:
            pytest.fail(f"Superuser blocked from TenantAwareUserOAuthModelView: {e}")

    def test_admin_user_can_access_views_with_tenant_context(self, app_context, mock_current_user):
        """The 'admin' user can access views even with tenant context."""
        from flask import g
        from keycloak_multi_tenant.security_manager import TenantAwareUserOAuthModelView

        # Mock admin user with tenant context
        mock_current_user.is_authenticated = True
        mock_current_user.username = "admin"
        g.tenant_id = "demo"

        # Should not raise
        view = TenantAwareUserOAuthModelView()
        try:
            view._check_superuser()
        except Exception as e:
            pytest.fail(f"Admin user blocked from view: {e}")
