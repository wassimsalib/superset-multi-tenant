# TODO: Add license header
"""
Multi-tenant authentication extension for Apache Superset.

This package provides tenant-based multi-tenancy with subdomain routing,
per-tenant OAuth client credentials, and full data isolation.

Features:
- Dynamic OAuth provider configuration per tenant
- Schema-based metadata isolation
- Per-tenant warehouse credentials for true security isolation
- Admin tenant concept for platform administrators
- Feature flag support (MULTI_TENANCY_ENABLED)

Usage:
    from superset.multitenancy import MultiTenantSecurityManager, init_multi_tenancy

    CUSTOM_SECURITY_MANAGER = MultiTenantSecurityManager

    def FLASK_APP_MUTATOR(app):
        init_multi_tenancy(app)

NOTE: This module uses lazy imports to avoid circular dependencies during
app initialization. The actual classes and functions are imported when first
accessed or during init_multi_tenancy().
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from flask import Flask

# These imports are safe - they don't trigger Superset's model chain
from superset.multitenancy.config import (
    DEFAULT_CONFIG,
    is_multi_tenancy_enabled,
    get_feature_flag_enabled,
)

# Security manager uses lazy proxy pattern - safe to import
from superset.multitenancy.security_manager import (
    MultiTenantSecurityManager,
    KeycloakMultiTenantSecurityManager,
    is_superuser,
    TenantAwareUserDBModelView,
    TenantAwareUserOAuthModelView,
    TenantAwareRoleModelView,
)

if TYPE_CHECKING:
    from superset.multitenancy.models import Tenant

logger = logging.getLogger(__name__)

__all__ = [
    # Core components
    "MultiTenantSecurityManager",
    "KeycloakMultiTenantSecurityManager",  # Legacy alias
    "Tenant",
    "TenantResolver",
    "tenant_resolver",
    "setup_tenant_middleware",
    "is_superuser",
    "TenantAwareUserDBModelView",
    "TenantAwareUserOAuthModelView",
    "TenantAwareRoleModelView",
    # Config
    "DEFAULT_CONFIG",
    "is_multi_tenancy_enabled",
    "get_feature_flag_enabled",
    # OAuth providers
    "OAuthProviderBase",
    "KeycloakOAuthProvider",
    "GenericOAuthProvider",
    "keycloak_client",
    "KeycloakMultiTenantClient",  # Legacy alias
    # Database isolation (convenience model)
    "get_tenant_schema",
    "get_tenant_from_schema",
    "setup_schema_isolation",
    "TenantAwareDatabaseConfig",
    "TenantSchemaManager",
    "TenantRLSManager",
    "create_tenant_database_uri",
    "get_tenant_schema_for_connection",
    "init_db_isolation",
    # Secure database access (per-tenant credentials)
    "TenantDatabaseManager",
    "TenantUserManager",
    "get_tenant_db_manager",
    "get_current_tenant_engine",
    "get_tenant_sqla_uri",
    "get_secure_tenant_engine",
    "execute_secure_query",
    "has_secure_warehouse_access",
    "get_warehouse_security_status",
    # Metadata isolation
    "get_current_tenant_id",
    "tenant_context",
    "setup_metadata_isolation",
    # RLS helpers
    "register_tenant_jinja_context",
    # Views
    "TenantModelView",
    "register_admin_views",
    # Initialization
    "init_multi_tenancy",
]

__version__ = "1.0.0"


def __getattr__(name: str) -> Any:
    """
    Lazy import handler for module attributes.

    This allows us to defer imports of modules that might trigger
    circular dependencies until they're actually needed.
    """
    # Tenant model
    if name == "Tenant":
        from superset.multitenancy.models import Tenant
        return Tenant

    # Tenant resolver
    if name in ("TenantResolver", "tenant_resolver"):
        from superset.multitenancy.tenant_resolver import TenantResolver, tenant_resolver
        if name == "TenantResolver":
            return TenantResolver
        return tenant_resolver

    # Middleware
    if name == "setup_tenant_middleware":
        from superset.multitenancy.middleware import setup_tenant_middleware
        return setup_tenant_middleware

    # RLS
    if name == "register_tenant_jinja_context":
        from superset.multitenancy.rls import register_tenant_jinja_context
        return register_tenant_jinja_context

    # OAuth providers
    if name in ("OAuthProviderBase", "KeycloakOAuthProvider", "GenericOAuthProvider"):
        from superset.multitenancy.oauth import (
            OAuthProviderBase,
            KeycloakOAuthProvider,
            GenericOAuthProvider,
        )
        return {"OAuthProviderBase": OAuthProviderBase,
                "KeycloakOAuthProvider": KeycloakOAuthProvider,
                "GenericOAuthProvider": GenericOAuthProvider}[name]

    if name in ("keycloak_client", "KeycloakMultiTenantClient"):
        from superset.multitenancy.oauth.keycloak import (
            keycloak_client,
            KeycloakMultiTenantClient,
        )
        if name == "keycloak_client":
            return keycloak_client
        return KeycloakMultiTenantClient

    # Isolation - schema
    if name in ("get_tenant_schema", "get_tenant_from_schema", "setup_schema_isolation",
                "TenantAwareDatabaseConfig", "TenantSchemaManager", "TenantRLSManager",
                "create_tenant_database_uri", "get_tenant_schema_for_connection",
                "init_db_isolation", "get_secure_tenant_engine", "execute_secure_query",
                "has_secure_warehouse_access", "get_warehouse_security_status"):
        from superset.multitenancy.isolation import (
            get_tenant_schema,
            get_tenant_from_schema,
            setup_schema_isolation,
            TenantAwareDatabaseConfig,
            TenantSchemaManager,
            TenantRLSManager,
            create_tenant_database_uri,
            get_tenant_schema_for_connection,
            init_db_isolation,
            get_secure_tenant_engine,
            execute_secure_query,
            has_secure_warehouse_access,
            get_warehouse_security_status,
        )
        return {
            "get_tenant_schema": get_tenant_schema,
            "get_tenant_from_schema": get_tenant_from_schema,
            "setup_schema_isolation": setup_schema_isolation,
            "TenantAwareDatabaseConfig": TenantAwareDatabaseConfig,
            "TenantSchemaManager": TenantSchemaManager,
            "TenantRLSManager": TenantRLSManager,
            "create_tenant_database_uri": create_tenant_database_uri,
            "get_tenant_schema_for_connection": get_tenant_schema_for_connection,
            "init_db_isolation": init_db_isolation,
            "get_secure_tenant_engine": get_secure_tenant_engine,
            "execute_secure_query": execute_secure_query,
            "has_secure_warehouse_access": has_secure_warehouse_access,
            "get_warehouse_security_status": get_warehouse_security_status,
        }[name]

    # Isolation - tenant database
    if name in ("TenantDatabaseManager", "TenantUserManager", "get_tenant_db_manager",
                "get_current_tenant_engine", "get_tenant_sqla_uri"):
        from superset.multitenancy.isolation import (
            TenantDatabaseManager,
            TenantUserManager,
            get_tenant_db_manager,
            get_current_tenant_engine,
            get_tenant_sqla_uri,
        )
        return {
            "TenantDatabaseManager": TenantDatabaseManager,
            "TenantUserManager": TenantUserManager,
            "get_tenant_db_manager": get_tenant_db_manager,
            "get_current_tenant_engine": get_current_tenant_engine,
            "get_tenant_sqla_uri": get_tenant_sqla_uri,
        }[name]

    # Isolation - metadata
    if name in ("get_current_tenant_id", "tenant_context", "setup_metadata_isolation"):
        from superset.multitenancy.isolation import (
            get_current_tenant_id,
            tenant_context,
            setup_metadata_isolation,
        )
        return {
            "get_current_tenant_id": get_current_tenant_id,
            "tenant_context": tenant_context,
            "setup_metadata_isolation": setup_metadata_isolation,
        }[name]

    # Views
    if name in ("TenantModelView", "register_admin_views"):
        from superset.multitenancy.views import TenantModelView, register_admin_views
        if name == "TenantModelView":
            return TenantModelView
        return register_admin_views

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def init_multi_tenancy(app: Flask) -> None:
    """
    Initialize all multi-tenancy components.

    Call this from FLASK_APP_MUTATOR in superset_config.py.

    Args:
        app: Flask application instance
    """
    # Check feature flag
    if not is_multi_tenancy_enabled() and not app.config.get("MULTI_TENANT_ENABLED"):
        logger.info("Multi-tenancy is disabled (feature flag off)")
        return

    # Lazy imports inside function to avoid circular dependencies
    from superset.multitenancy.middleware import setup_tenant_middleware
    from superset.multitenancy.rls import register_tenant_jinja_context
    from superset.multitenancy.isolation import setup_metadata_isolation, init_db_isolation
    from superset.multitenancy.views import register_admin_views

    # Set up components
    setup_tenant_middleware(app)
    register_tenant_jinja_context(app)
    setup_metadata_isolation(app)
    register_admin_views(app)
    init_db_isolation(app)

    # Register CLI commands
    from superset.multitenancy.commands import seed_tenants
    app.cli.add_command(seed_tenants, "seed-tenants")

    logger.info("Multi-tenancy initialized successfully")
