# TODO: Add license header
"""
Tests for schema isolation utilities.
"""

from __future__ import annotations

import pytest


class TestSchemaUtilities:
    """Test schema naming utilities."""

    def test_get_tenant_schema(self, app_context):
        """get_tenant_schema should return correct schema name."""
        from superset.multitenancy.isolation import get_tenant_schema

        assert get_tenant_schema("demo") == "tenant_demo"
        assert get_tenant_schema("acme") == "tenant_acme"
        assert get_tenant_schema("my_company") == "tenant_my_company"

    def test_get_tenant_schema_sanitizes_input(self, app_context):
        """get_tenant_schema should sanitize input."""
        from superset.multitenancy.isolation import get_tenant_schema

        # Should strip non-alphanumeric characters
        assert get_tenant_schema("test-company") == "tenant_testcompany"
        assert get_tenant_schema("test.company") == "tenant_testcompany"

    def test_get_tenant_from_schema(self, app_context):
        """get_tenant_from_schema should extract slug from schema name."""
        from superset.multitenancy.isolation import get_tenant_from_schema

        assert get_tenant_from_schema("tenant_demo") == "demo"
        assert get_tenant_from_schema("tenant_acme") == "acme"
        assert get_tenant_from_schema("public") is None
        assert get_tenant_from_schema("other_schema") is None


class TestTenantAwareDatabaseConfig:
    """Test TenantAwareDatabaseConfig utilities."""

    def test_get_connection_string(self, app_context):
        """Should add search_path to connection string."""
        from superset.multitenancy.isolation import TenantAwareDatabaseConfig

        base_uri = "postgresql://user:pass@localhost/db"
        result = TenantAwareDatabaseConfig.get_connection_string(base_uri, "demo")

        assert "options=-csearch_path" in result
        assert "tenant_demo" in result

    def test_get_connection_string_with_existing_params(self, app_context):
        """Should append to existing query params."""
        from superset.multitenancy.isolation import TenantAwareDatabaseConfig

        base_uri = "postgresql://user:pass@localhost/db?sslmode=require"
        result = TenantAwareDatabaseConfig.get_connection_string(base_uri, "demo")

        assert "sslmode=require" in result
        assert "options=-csearch_path" in result

    def test_get_sqlalchemy_options(self, app_context):
        """Should return correct connect_args."""
        from superset.multitenancy.isolation import TenantAwareDatabaseConfig

        result = TenantAwareDatabaseConfig.get_sqlalchemy_options("acme")

        assert "options" in result
        assert "tenant_acme" in result["options"]
