# TODO: Add license header
"""
Tests for the TenantResolver.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestTenantResolver:
    """Test the TenantResolver class."""

    def test_extract_subdomain_basic(self, app_context, app):
        """Should extract subdomain from host."""
        from superset.multitenancy.tenant_resolver import TenantResolver

        app.config["MULTI_TENANT_BASE_DOMAIN"] = "app.example.com"
        resolver = TenantResolver(app)

        result = resolver._extract_subdomain("customer1.app.example.com")
        assert result == "customer1"

    def test_extract_subdomain_with_port(self, app_context, app):
        """Should extract subdomain even with port."""
        from superset.multitenancy.tenant_resolver import TenantResolver

        app.config["MULTI_TENANT_BASE_DOMAIN"] = "app.example.com"
        resolver = TenantResolver(app)

        result = resolver._extract_subdomain("customer1.app.example.com:8088")
        assert result == "customer1"

    def test_extract_subdomain_no_subdomain(self, app_context, app):
        """Should return None when no subdomain."""
        from superset.multitenancy.tenant_resolver import TenantResolver

        app.config["MULTI_TENANT_BASE_DOMAIN"] = "app.example.com"
        resolver = TenantResolver(app)

        result = resolver._extract_subdomain("app.example.com")
        assert result is None

    def test_extract_subdomain_different_domain(self, app_context, app):
        """Should return None for different domain."""
        from superset.multitenancy.tenant_resolver import TenantResolver

        app.config["MULTI_TENANT_BASE_DOMAIN"] = "app.example.com"
        resolver = TenantResolver(app)

        result = resolver._extract_subdomain("other.domain.com")
        assert result is None

    def test_extract_subdomain_localhost(self, app_context, app):
        """Should work with localhost-based domain."""
        from superset.multitenancy.tenant_resolver import TenantResolver

        app.config["MULTI_TENANT_BASE_DOMAIN"] = "app.localhost"
        resolver = TenantResolver(app)

        result = resolver._extract_subdomain("demo.app.localhost:8088")
        assert result == "demo"

    def test_resolve_from_request(self, app_context, app, db):
        """Should resolve tenant from request."""
        from superset.multitenancy.models import Tenant
        from superset.multitenancy.tenant_resolver import TenantResolver

        # Create a test tenant
        tenant = Tenant(
            slug="testcustomer",
            name="Test Customer",
            oauth_issuer="http://keycloak:8080/realms/test",
            client_id="superset",
            client_secret="test",
        )
        db.session.add(tenant)
        db.session.commit()

        app.config["MULTI_TENANT_BASE_DOMAIN"] = "app.example.com"
        resolver = TenantResolver(app)

        # Mock request
        mock_request = MagicMock()
        mock_request.host = "testcustomer.app.example.com"

        result = resolver.resolve_from_request(mock_request)
        assert result is not None
        assert result.slug == "testcustomer"

        # Cleanup
        db.session.delete(tenant)
        db.session.commit()

    def test_resolve_from_request_inactive_tenant(self, app_context, app, db):
        """Should not resolve inactive tenant."""
        from superset.multitenancy.models import Tenant
        from superset.multitenancy.tenant_resolver import TenantResolver

        # Create an inactive tenant
        tenant = Tenant(
            slug="inactive",
            name="Inactive",
            oauth_issuer="http://keycloak:8080/realms/inactive",
            client_id="superset",
            client_secret="test",
            is_active=False,
        )
        db.session.add(tenant)
        db.session.commit()

        app.config["MULTI_TENANT_BASE_DOMAIN"] = "app.example.com"
        resolver = TenantResolver(app)

        mock_request = MagicMock()
        mock_request.host = "inactive.app.example.com"

        result = resolver.resolve_from_request(mock_request)
        assert result is None

        # Cleanup
        db.session.delete(tenant)
        db.session.commit()
