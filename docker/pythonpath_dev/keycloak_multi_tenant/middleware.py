# TODO: Add Apache license header
"""
Flask middleware for tenant context management.
"""

import logging
from typing import Optional

from flask import Flask, g, redirect, request, session, url_for
from flask_login import current_user, logout_user

from sqlalchemy import text

from keycloak_multi_tenant.keycloak_client import KeycloakMultiTenantClient
from keycloak_multi_tenant.tenant_resolver import TenantResolver

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
    keycloak_client = KeycloakMultiTenantClient(app)

    # Get configuration
    public_endpoints = app.config.get(
        "MULTI_TENANT_PUBLIC_ENDPOINTS",
        [
            "/health",
            "/healthcheck",
            "/static/",
            "/api/v1/security/csrf_token",
            "/unknown-tenant",  # Avoid redirect loop for tenant-not-found page
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
        # Handle Keycloak single logout
        if request.path in ["/logout/", "/logout"]:
            tenant = tenant_resolver.resolve_from_request(request)
            if tenant and current_user.is_authenticated:
                logger.info("Processing Keycloak single logout for tenant: %s", tenant.tenant_id)

                # First logout from Superset
                logout_user()
                session.clear()

                # Build post-logout redirect URL (back to login page with logout flag)
                # Use the base login URL without provider for post-logout
                post_logout_url = request.host_url.rstrip("/") + "/login/?logout=1"

                # Get Keycloak logout URL
                from superset.extensions import appbuilder
                keycloak_logout_url = appbuilder.sm.get_keycloak_logout_url(
                    tenant, post_logout_url
                )
                logger.info("Redirecting to Keycloak logout: %s", keycloak_logout_url)
                return redirect(keycloak_logout_url)
            else:
                # No tenant or not authenticated, just logout normally
                logger.info("Standard logout (no Keycloak SSO)")
                g.tenant = None
                return None

        # Skip for public endpoints
        if is_public_endpoint(request.path, public_endpoints):
            logger.debug("Skipping tenant resolution for public endpoint: %s", request.path)
            g.tenant = None
            return None

        # Skip for OAuth callback endpoints
        if "/oauth-authorized/" in request.path:
            logger.debug("Skipping tenant resolution for OAuth callback")
            # Tenant should already be in session from initial request
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
        # Store both the object and primitive values to avoid detached session issues
        g.tenant = tenant
        g.tenant_id = tenant.tenant_id  # String subdomain - used for schema routing
        g.tenant_pk = tenant.id  # Integer PK - kept for potential future use

        # Set PostgreSQL search_path for schema-based tenant isolation
        # This routes all queries to the tenant's schema first, then public
        from superset import db
        schema = f"tenant_{tenant.tenant_id}"
        db.session.execute(text(f"SET search_path = {schema}, public"))
        logger.debug("Set search_path to %s, public", schema)

        logger.debug(
            "Tenant context set: tenant_id=%s, realm=%s",
            tenant.tenant_id,
            tenant.keycloak_realm,
        )

        # Register OAuth provider for this tenant
        _register_tenant_oauth_provider(app, tenant, keycloak_client)

        # Store tenant in session for OAuth callback
        session["tenant_id"] = tenant.tenant_id

        # Debug logging
        logger.info(
            "Request path: %s, is_authenticated: %s",
            request.path,
            current_user.is_authenticated if hasattr(current_user, 'is_authenticated') else 'N/A',
        )

        # Auto-redirect to OAuth if user is not authenticated and accessing login page
        # Skip auto-redirect if coming from logout (allow showing login page)
        if request.path in ["/login/", "/login"]:
            # Check if this is a post-logout request (don't auto-redirect)
            if request.args.get("logout") or request.referrer and "/logout" in request.referrer:
                logger.info("Post-logout request, showing login page")
                return None

            if not current_user.is_authenticated:
                provider_name = f"keycloak_{tenant.tenant_id}"
                logger.info(
                    "Redirecting unauthenticated user to OAuth login for tenant: %s, provider: %s",
                    tenant.tenant_id,
                    provider_name,
                )
                return redirect(url_for("AuthOAuthView.login", provider=provider_name))
            else:
                logger.info("User is already authenticated, not redirecting")

        return None

    @app.after_request
    def add_tenant_headers(response):
        """Add tenant information to response headers for debugging."""
        # Use g.tenant_id (primitive string) to avoid SQLAlchemy lazy load issues
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
                # Session might already be closed/invalidated
                logger.debug("Could not reset search_path: %s", e)

    logger.info("Tenant middleware initialized")


def _register_tenant_oauth_provider(
    app: Flask, tenant: "Tenant", keycloak_client: KeycloakMultiTenantClient
) -> None:
    """
    Register OAuth provider for the current tenant.

    Args:
        app: Flask application
        tenant: Current tenant object
        keycloak_client: Keycloak client for generating OAuth config
    """
    from superset.extensions import appbuilder

    # Generate OAuth config for tenant
    provider_config = keycloak_client.get_oauth_provider_config(tenant)
    provider_name = provider_config["name"]

    # Check if already registered
    if provider_name in getattr(appbuilder.sm, "oauth_remotes", {}):
        logger.debug("OAuth provider %s already registered", provider_name)
        return

    # Register the provider
    try:
        appbuilder.sm.register_oauth_provider(provider_config)
        logger.info(
            "Registered OAuth provider for tenant: %s", tenant.tenant_id
        )
    except Exception as e:
        logger.error(
            "Failed to register OAuth provider for tenant %s: %s",
            tenant.tenant_id,
            str(e),
        )
        raise
