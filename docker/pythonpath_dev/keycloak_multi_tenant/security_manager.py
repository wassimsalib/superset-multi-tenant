# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""
Multi-tenant Keycloak Security Manager for Superset.

This module provides:
1. Multi-tenant OAuth authentication with Keycloak
2. Superuser-restricted FAB admin views for user/role management
3. Tenant-aware security context management

SECURITY: FAB admin views (Users, Roles) are restricted to superusers only.
Tenant admins should manage their users in Keycloak, not in Superset.
"""

import logging
from typing import Any, Optional

from flask import abort, g, redirect, request, session, url_for
from flask_appbuilder import expose
from flask_appbuilder.security.decorators import has_access
from flask_appbuilder.security.manager import AUTH_OAUTH
from flask_appbuilder.security.views import (
    RoleModelView,
    UserDBModelView,
    UserOAuthModelView,
)
from flask_login import current_user
from superset.security import SupersetSecurityManager

logger = logging.getLogger(__name__)


# =============================================================================
# Superuser Check Helper
# =============================================================================

def is_superuser() -> bool:
    """
    Check if the current user is a superuser (system admin).

    A superuser is defined as:
    1. A user without a tenant context (accessing from main domain), OR
    2. A user with the username 'admin' (built-in superuser)

    Regular tenant admins should NOT be considered superusers.
    They should manage their users in Keycloak, not in Superset.
    """
    if not current_user or not current_user.is_authenticated:
        return False

    # Check if there's no tenant context (system-level access)
    tenant_id = g.get("tenant_id")
    if not tenant_id:
        return True

    # Built-in admin user is always a superuser
    if current_user.username == "admin":
        return True

    return False


# =============================================================================
# Superuser-Restricted FAB View Classes
# =============================================================================
# These override Flask-AppBuilder's default admin views to add superuser checks.
# Tenant admins (e.g., acme-admin) should NOT be able to see users from other
# tenants. User management should be handled in Keycloak, not Superset.


class SuperuserRequiredMixin:
    """
    Mixin that adds superuser checks to all view methods.

    When a tenant admin tries to access these views, they get a 403 error
    with a message directing them to use Keycloak for user management.
    """

    def _check_superuser(self) -> None:
        """Check if user is superuser, abort with 403 if not."""
        if not is_superuser():
            logger.warning(
                "Non-superuser '%s' attempted to access FAB admin view: %s",
                current_user.username if current_user else "anonymous",
                self.__class__.__name__,
            )
            abort(
                403,
                description="Access denied. User management is handled in Keycloak. "
                "Contact your system administrator for access.",
            )


class TenantAwareUserDBModelView(SuperuserRequiredMixin, UserDBModelView):
    """
    User list view for database-authenticated users - SUPERUSER ONLY.

    Tenant admins should manage users in Keycloak, not Superset.
    This view is restricted to system administrators only.
    """

    @expose("/list/")
    @has_access
    def list(self):
        """List all users - SUPERUSER ONLY."""
        self._check_superuser()
        return super().list()

    @expose("/show/<pk>")
    @has_access
    def show(self, pk):
        """Show user details - SUPERUSER ONLY."""
        self._check_superuser()
        return super().show(pk)

    @expose("/add")
    @has_access
    def add(self):
        """Add new user - SUPERUSER ONLY."""
        self._check_superuser()
        return super().add()

    @expose("/edit/<pk>")
    @has_access
    def edit(self, pk):
        """Edit user - SUPERUSER ONLY."""
        self._check_superuser()
        return super().edit(pk)

    @expose("/delete/<pk>")
    @has_access
    def delete(self, pk):
        """Delete user - SUPERUSER ONLY."""
        self._check_superuser()
        return super().delete(pk)


class TenantAwareUserOAuthModelView(SuperuserRequiredMixin, UserOAuthModelView):
    """
    User list view for OAuth-authenticated users - SUPERUSER ONLY.

    This is the primary view used in multi-tenant setups since all
    users authenticate via Keycloak OAuth.
    """

    @expose("/list/")
    @has_access
    def list(self):
        """List all OAuth users - SUPERUSER ONLY."""
        self._check_superuser()
        return super().list()

    @expose("/show/<pk>")
    @has_access
    def show(self, pk):
        """Show OAuth user details - SUPERUSER ONLY."""
        self._check_superuser()
        return super().show(pk)

    @expose("/add")
    @has_access
    def add(self):
        """Add new OAuth user - SUPERUSER ONLY."""
        self._check_superuser()
        return super().add()

    @expose("/edit/<pk>")
    @has_access
    def edit(self, pk):
        """Edit OAuth user - SUPERUSER ONLY."""
        self._check_superuser()
        return super().edit(pk)

    @expose("/delete/<pk>")
    @has_access
    def delete(self, pk):
        """Delete OAuth user - SUPERUSER ONLY."""
        self._check_superuser()
        return super().delete(pk)


class TenantAwareRoleModelView(SuperuserRequiredMixin, RoleModelView):
    """
    Role management view - SUPERUSER ONLY.

    Roles are shared across all tenants (Admin, Alpha, Gamma, etc.).
    Only system administrators should be able to modify roles.
    """

    @expose("/list/")
    @has_access
    def list(self):
        """List all roles - SUPERUSER ONLY."""
        self._check_superuser()
        return super().list()

    @expose("/show/<pk>")
    @has_access
    def show(self, pk):
        """Show role details - SUPERUSER ONLY."""
        self._check_superuser()
        return super().show(pk)

    @expose("/add")
    @has_access
    def add(self):
        """Add new role - SUPERUSER ONLY."""
        self._check_superuser()
        return super().add()

    @expose("/edit/<pk>")
    @has_access
    def edit(self, pk):
        """Edit role - SUPERUSER ONLY."""
        self._check_superuser()
        return super().edit(pk)

    @expose("/delete/<pk>")
    @has_access
    def delete(self, pk):
        """Delete role - SUPERUSER ONLY."""
        self._check_superuser()
        return super().delete(pk)


class KeycloakMultiTenantSecurityManager(SupersetSecurityManager):
    """
    Custom Security Manager that handles multi-tenant Keycloak authentication.

    Features:
    - Dynamic OAuth provider configuration per tenant
    - Tenant context stored with user
    - Role mapping from Keycloak groups
    - Superuser-restricted FAB admin views (users, roles)

    SECURITY:
    - FAB user/role management views are restricted to superusers only
    - Tenant admins should manage users in Keycloak, not Superset
    - The 'admin' user and users without tenant context are superusers
    """

    # Override FAB view classes with tenant-aware superuser-restricted versions
    # These prevent tenant admins from seeing users from other tenants
    userdbmodelview = TenantAwareUserDBModelView
    useroauthmodelview = TenantAwareUserOAuthModelView
    rolemodelview = TenantAwareRoleModelView

    def __init__(self, appbuilder: Any):
        super().__init__(appbuilder)
        self._oauth_providers_cache: dict[str, Any] = {}

    def oauth_user_info(self, provider: str, response: Any = None) -> dict[str, Any]:
        """
        Extract user info from Keycloak OAuth response.

        Args:
            provider: OAuth provider name (includes tenant ID)
            response: OAuth response object

        Returns:
            Dictionary with user information including tenant context
        """
        try:
            logger.info("oauth_user_info called for provider: %s", provider)

            # Get userinfo from Keycloak
            if provider not in self.oauth_remotes:
                logger.error("Provider %s not found in oauth_remotes: %s", provider, list(self.oauth_remotes.keys()))
                return {}

            me = self.oauth_remotes[provider].userinfo()
            logger.info("Received userinfo from Keycloak: %s", me)

            # Get current tenant from request context or session
            tenant = g.get("tenant")
            if not tenant:
                # Try to get from session
                from flask import session
                tenant_id_str = session.get("tenant_id")
                if tenant_id_str:
                    from superset import db
                    from keycloak_multi_tenant.models import Tenant
                    tenant = db.session.query(Tenant).filter_by(tenant_id=tenant_id_str).first()

            tenant_id = tenant.id if tenant else None

            # Extract Keycloak groups for role mapping
            groups = me.get("groups", [])
            # Also check realm_access.roles and resource_access
            realm_roles = me.get("realm_access", {}).get("roles", [])
            groups.extend(realm_roles)

            user_info = {
                "username": me.get("preferred_username", me.get("sub")),
                "email": me.get("email", ""),
                "first_name": me.get("given_name", ""),
                "last_name": me.get("family_name", ""),
                "role_keys": groups,
                # Custom field for tenant association
                "tenant_id": tenant_id,
            }

            logger.info(
                "Extracted user info: username=%s, email=%s, tenant_id=%s",
                user_info["username"],
                user_info["email"],
                tenant_id,
            )

            return user_info
        except Exception as e:
            logger.exception("Error in oauth_user_info: %s", str(e))
            return {}

    def auth_user_oauth(self, userinfo: dict[str, Any]) -> Any:
        """
        Authenticate/create user from OAuth userinfo.

        Stores tenant_id in user's custom attributes for later filtering.

        Args:
            userinfo: Dictionary from oauth_user_info

        Returns:
            User object
        """
        logger.info("auth_user_oauth called with userinfo: %s", userinfo)

        # Extract tenant_id before calling parent
        tenant_id = userinfo.pop("tenant_id", None)
        logger.info("Extracted tenant_id: %s, remaining userinfo: %s", tenant_id, userinfo)

        try:
            # Let parent handle user creation/update
            user = super().auth_user_oauth(userinfo)
            logger.info("Parent auth_user_oauth returned user: %s (type: %s)", user, type(user))
        except Exception as e:
            logger.exception("Error in parent auth_user_oauth: %s", str(e))
            return None

        if user and tenant_id:
            # Store tenant association
            # Note: Superset doesn't have extra_attributes by default,
            # so we store it in session and use it for filtering
            session["user_tenant_id"] = tenant_id
            logger.info(
                "Associated user %s with tenant_id %s",
                user.username,
                tenant_id,
            )
        elif not user:
            logger.warning("auth_user_oauth: parent returned None user")

        return user

    def get_oauth_redirect_url(self, provider: str) -> str:
        """
        Get the OAuth callback URL.

        Ensures the redirect URL includes the tenant subdomain.

        Args:
            provider: OAuth provider name

        Returns:
            Callback URL string
        """
        return url_for(
            "AuthOAuthView.oauth_authorized",
            provider=provider,
            _external=True,
        )

    def get_current_tenant_id(self) -> Optional[int]:
        """
        Get the current user's tenant ID.

        Returns:
            Tenant ID or None if not set
        """
        # First check Flask g context (set by middleware)
        tenant = g.get("tenant")
        if tenant:
            return tenant.id

        # Fall back to session (set during auth)
        return session.get("user_tenant_id")

    def register_oauth_provider(self, provider_config: dict[str, Any]) -> None:
        """
        Register an OAuth provider dynamically.

        Args:
            provider_config: OAuth provider configuration dictionary
        """
        provider_name = provider_config["name"]

        # Skip if already registered
        if provider_name in self._oauth_providers_cache:
            logger.debug("OAuth provider %s already registered", provider_name)
            return

        logger.info("Registering OAuth provider: %s", provider_name)

        # Register with authlib
        remote_app_config = provider_config["remote_app"]

        self.appbuilder.sm.oauth_remotes[provider_name] = (
            self.appbuilder.sm.oauth.register(
                name=provider_name,
                client_id=remote_app_config["client_id"],
                client_secret=remote_app_config["client_secret"],
                server_metadata_url=remote_app_config["server_metadata_url"],
                client_kwargs=remote_app_config.get("client_kwargs", {}),
            )
        )

        # Update OAUTH_PROVIDERS config
        if not hasattr(self.appbuilder.app.config, "OAUTH_PROVIDERS"):
            self.appbuilder.app.config["OAUTH_PROVIDERS"] = []

        self.appbuilder.app.config["OAUTH_PROVIDERS"].append(provider_config)
        self._oauth_providers_cache[provider_name] = provider_config

        logger.info("Successfully registered OAuth provider: %s", provider_name)

    def get_oauth_login_url(self, tenant_provider: str) -> str:
        """
        Get the OAuth login URL for a specific tenant's provider.

        Args:
            tenant_provider: Provider name (e.g., "keycloak_customer1")

        Returns:
            Login URL string
        """
        return url_for("AuthOAuthView.login", provider=tenant_provider)

    def get_keycloak_logout_url(self, tenant: Any, post_logout_redirect: str) -> str:
        """
        Get the Keycloak logout URL for single sign-out.

        Args:
            tenant: Tenant object
            post_logout_redirect: URL to redirect to after Keycloak logout

        Returns:
            Keycloak logout URL
        """
        from flask import current_app
        import urllib.parse

        keycloak_base_url = current_app.config.get("KEYCLOAK_BASE_URL", "")
        logout_url = (
            f"{keycloak_base_url}/realms/{tenant.keycloak_realm}"
            f"/protocol/openid-connect/logout"
            f"?post_logout_redirect_uri={urllib.parse.quote(post_logout_redirect)}"
            f"&client_id={tenant.keycloak_client_id}"
        )
        return logout_url

    def get_schemas_accessible_by_user(
        self,
        database: Any,
        catalog: Optional[str],
        schemas: set[str],
        hierarchical: bool = True,
    ) -> set[str]:
        """
        Filter schemas accessible by the current user.

        For tenant users, only show their tenant's schema in warehouse databases.
        Superusers can see all schemas.

        This prevents tenants from seeing other tenant schema names in the
        warehouse database schema dropdown (e.g., when creating datasets).

        Args:
            database: The database connection object
            catalog: Optional catalog name
            schemas: Set of all schemas from the database
            hierarchical: Whether to check hierarchical permissions

        Returns:
            Filtered set of schema names
        """
        # Get tenant context
        tenant_id = g.get("tenant_id")

        # Superusers can see all schemas
        if is_superuser():
            return super().get_schemas_accessible_by_user(
                database, catalog, schemas, hierarchical
            )

        # For tenant users, filter to ONLY their tenant's schema
        if tenant_id:
            tenant_schema = f"tenant_{tenant_id}"

            # Only show the tenant's own schema - nothing else
            filtered = {schema for schema in schemas if schema == tenant_schema}

            logger.debug(
                "Filtered schemas for tenant %s: %s -> %s",
                tenant_id,
                schemas,
                filtered,
            )
            return filtered

        # No tenant context - use default behavior
        return super().get_schemas_accessible_by_user(
            database, catalog, schemas, hierarchical
        )
