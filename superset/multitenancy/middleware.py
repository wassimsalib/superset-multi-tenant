# TODO: Add license header
"""
Flask middleware for tenant context management.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from flask import Flask, abort, g, redirect, request, session, url_for
from flask_login import current_user, logout_user
from sqlalchemy import text

from superset.multitenancy.config import is_multi_tenancy_enabled
from superset.multitenancy.security_manager import is_superuser
from superset.multitenancy.oauth.keycloak import KeycloakOAuthProvider
from superset.multitenancy.tenant_resolver import TenantResolver

if TYPE_CHECKING:
    from superset.multitenancy.models import Tenant

logger = logging.getLogger(__name__)


def is_public_endpoint(path: str, public_endpoints: list[str]) -> bool:
    """
    Check if the request path is a public endpoint.

    Args:
        path: Request path
        public_endpoints: List of public endpoint prefixes

    Returns:
        True if public, False otherwise
    """
    for endpoint in public_endpoints:
        if path.startswith(endpoint):
            return True
    return False


# URL patterns that require superuser access (tenant admins should NOT access these)
# User endpoints are filtered by tenant_id via TenantUserFilter in the API
SUPERUSER_ONLY_ENDPOINTS = [
    "/api/v1/security/roles",  # Role management API - global
    "/api/v1/security/user_registrations",  # User registrations API
    "/api/v1/role/",  # FAB Role API - global
    "/api/v1/group/",  # FAB Group API - global
    "/roles/",  # Role list view - global
    "/groups/",  # Group list view - global
    "/registrations/",  # User registrations view
]


def is_superuser_only_endpoint(path: str) -> bool:
    """
    Check if the request path requires superuser access.

    These endpoints expose user/role management which should be restricted
    to platform administrators only in a multi-tenant environment.

    Args:
        path: Request path

    Returns:
        True if superuser-only, False otherwise
    """
    for pattern in SUPERUSER_ONLY_ENDPOINTS:
        if path.startswith(pattern):
            return True
    return False


def setup_tenant_middleware(app: Flask) -> None:
    """
    Set up tenant resolution middleware.

    This middleware:
    1. Extracts tenant from subdomain
    2. Validates tenant exists and is active
    3. Configures OAuth provider for the tenant
    4. Stores tenant in Flask g context

    Args:
        app: Flask application instance
    """
    tenant_resolver = TenantResolver(app)
    keycloak_client = KeycloakOAuthProvider(app)

    # Get configuration
    public_endpoints = app.config.get(
        "MULTI_TENANT_PUBLIC_ENDPOINTS",
        [
            "/health",
            "/healthcheck",
            "/static/",
            "/api/v1/security/csrf_token",
            "/unknown-tenant",
        ],
    )

    tenant_not_found_url = app.config.get(
        "TENANT_NOT_FOUND_URL", "https://example.com/unknown-tenant"
    )

    @app.before_request
    def resolve_tenant() -> Optional[redirect]:
        """
        Resolve tenant before each request.

        Sets g.tenant for use throughout the request lifecycle.
        """
        # Check if multi-tenancy is enabled via feature flag
        if not is_multi_tenancy_enabled():
            g.tenant = None
            g.tenant_id = None
            return None

        # Handle logout
        if request.path in ["/logout/", "/logout"]:
            tenant = tenant_resolver.resolve_from_request(request)
            if tenant and current_user.is_authenticated:
                logger.info(
                    "Processing logout for tenant: %s", tenant.slug
                )

                logout_user()
                session.clear()

                post_logout_url = request.host_url.rstrip("/") + "/login/?logout=1"

                from superset.extensions import appbuilder

                logout_url = appbuilder.sm.get_keycloak_logout_url(
                    tenant, post_logout_url
                )
                logger.info("Redirecting to OAuth logout: %s", logout_url)
                return redirect(logout_url)
            else:
                logger.info("Standard logout (no tenant context)")
                g.tenant = None
                return None

        # Skip for public endpoints
        if is_public_endpoint(request.path, public_endpoints):
            logger.debug(
                "Skipping tenant resolution for public endpoint: %s", request.path
            )
            g.tenant = None
            return None

        # Skip for OAuth callback endpoints
        if "/oauth-authorized/" in request.path:
            logger.debug("Skipping tenant resolution for OAuth callback")
            return None

        # Resolve tenant from subdomain
        tenant = tenant_resolver.resolve_from_request(request)

        if not tenant:
            logger.warning(
                "No tenant found for host: %s, redirecting to not found URL",
                request.host,
            )
            return redirect(tenant_not_found_url)

        # Store tenant in request context
        g.tenant = tenant
        g.tenant_id = tenant.slug  # String slug - used for schema routing
        g.tenant_pk = tenant.id  # Integer PK

        # SECURITY: Check for superuser-only endpoints AFTER tenant context is set
        # Tenant admins must not access user/role management
        if is_superuser_only_endpoint(request.path):
            if current_user.is_authenticated and not is_superuser():
                logger.warning(
                    "Non-superuser '%s' (tenant: %s) attempted to access "
                    "protected endpoint: %s",
                    current_user.username,
                    tenant.slug,
                    request.path,
                )
                abort(
                    403,
                    description=(
                        "Access denied. User and role management is restricted to "
                        "platform administrators. Manage users in your identity provider."
                    ),
                )

        # Set PostgreSQL search_path for schema-based tenant isolation
        from superset import db
        from superset.multitenancy.isolation.schema_isolation import get_tenant_schema

        schema = get_tenant_schema(tenant.slug)
        db.session.execute(text(f"SET search_path = {schema}, public"))
        logger.debug("Set search_path to %s, public", schema)

        logger.debug(
            "Tenant context set: slug=%s, oauth_issuer=%s",
            tenant.slug,
            tenant.oauth_issuer,
        )

        # Register OAuth provider for this tenant
        _register_tenant_oauth_provider(app, tenant, keycloak_client)

        # Store tenant in session for OAuth callback
        session["tenant_id"] = tenant.slug

        # Debug logging
        logger.info(
            "Request path: %s, is_authenticated: %s",
            request.path,
            current_user.is_authenticated
            if hasattr(current_user, "is_authenticated")
            else "N/A",
        )

        # Auto-redirect to OAuth if user is not authenticated and accessing login page
        if request.path in ["/login/", "/login"]:
            # Check if this is a post-logout request
            if request.args.get("logout") or (
                request.referrer and "/logout" in request.referrer
            ):
                logger.info("Post-logout request, showing login page")
                return None

            if not current_user.is_authenticated:
                provider_name = keycloak_client.get_provider_name(tenant)
                logger.info(
                    "Redirecting unauthenticated user to OAuth login for tenant: %s, "
                    "provider: %s",
                    tenant.slug,
                    provider_name,
                )
                return redirect(url_for("AuthOAuthView.login", provider=provider_name))
            else:
                logger.info("User is already authenticated, not redirecting")

        return None

    @app.after_request
    def add_tenant_headers(response):
        """Add tenant information to response headers for debugging."""
        tenant_id = g.get("tenant_id")
        if tenant_id:
            response.headers["X-Tenant-ID"] = tenant_id
        return response

    @app.teardown_request
    def reset_search_path(exception=None):
        """Reset search_path at end of request to avoid connection pool contamination."""
        tenant_id = g.get("tenant_id")
        if tenant_id:
            try:
                from superset import db

                db.session.execute(text("SET search_path = public"))
            except Exception as e:
                logger.debug("Could not reset search_path: %s", e)

    logger.info("Tenant middleware initialized")


def _register_tenant_oauth_provider(
    app: Flask, tenant: Tenant, oauth_provider: KeycloakOAuthProvider
) -> None:
    """
    Register OAuth provider for the current tenant.

    Args:
        app: Flask application
        tenant: Current tenant object
        oauth_provider: OAuth provider for generating config
    """
    from superset.extensions import appbuilder

    provider_config = oauth_provider.get_oauth_provider_config(tenant)
    provider_name = provider_config["name"]

    if provider_name in getattr(appbuilder.sm, "oauth_remotes", {}):
        logger.debug("OAuth provider %s already registered", provider_name)
        return

    try:
        appbuilder.sm.register_oauth_provider(provider_config)
        logger.info("Registered OAuth provider for tenant: %s", tenant.slug)
    except Exception as e:
        logger.error(
            "Failed to register OAuth provider for tenant %s: %s",
            tenant.slug,
            str(e),
        )
        raise
