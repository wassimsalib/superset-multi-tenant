# TODO: Add license header
"""
Multi-tenant Security Manager for Superset.

This module provides:
1. Multi-tenant OAuth authentication
2. Superuser-restricted FAB admin views for user/role management
3. Tenant-aware security context management
4. Admin tenant privilege checks

SECURITY: FAB admin views (Users, Roles) are restricted to superusers only.
Tenant admins should manage their users in their OAuth provider, not in Superset.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import quote

from flask import abort, g, session, url_for
from flask_appbuilder import expose
from flask_appbuilder.api import BaseApi, safe
from flask_appbuilder.models.filters import BaseFilter
from flask_appbuilder.security.decorators import has_access, protect
from flask_appbuilder.security.sqla.models import User
from flask_appbuilder.security.views import (
    RoleModelView,
    UserDBModelView,
    UserOAuthModelView,
)
from flask_login import current_user
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

# Import SupersetSecurityManager and API classes
from superset.security import SupersetSecurityManager
from superset.security.manager import SupersetRoleApi, SupersetUserApi

# Import models at module level to avoid per-request import overhead
from superset.extensions import db
from superset.multitenancy.models import Tenant, UserTenant

logger = logging.getLogger(__name__)


# =============================================================================
# Superuser Check Helper
# =============================================================================


def is_superuser() -> bool:
    """
    Check if the current user is a superuser (system admin).

    A superuser is defined as:
    1. A user from an admin tenant (is_admin_tenant=True), OR
    2. A user without a tenant context (accessing from main domain), OR
    3. A user with the username 'admin' (built-in superuser)

    Regular tenant admins should NOT be considered superusers.
    They should manage their users in their OAuth provider, not in Superset.
    """
    if not current_user or not current_user.is_authenticated:
        return False

    # Built-in admin user is always a superuser
    if current_user.username == "admin":
        return True

    # Check if there's no tenant context (system-level access)
    tenant = g.get("tenant")
    tenant_id = g.get("tenant_id")

    if not tenant_id and not tenant:
        return True

    # Check if this is an admin tenant
    if tenant and hasattr(tenant, "is_admin_tenant") and tenant.is_admin_tenant:
        return True

    return False


# =============================================================================
# Superuser-Restricted FAB View Classes
# =============================================================================


class SuperuserRequiredMixin:
    """
    Mixin that adds superuser checks to all view methods.

    When a tenant admin tries to access these views, they get a 403 error
    with a message directing them to use their OAuth provider for user management.
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
                description=(
                    "Access denied. User management is handled in your identity provider. "
                    "Contact your system administrator for access."
                ),
            )


class TenantAwareUserDBModelView(SuperuserRequiredMixin, UserDBModelView):
    """
    User list view for database-authenticated users - SUPERUSER ONLY.
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


# =============================================================================
# Superuser-Restricted API Classes
# =============================================================================


def _check_api_superuser() -> None:
    """
    Check if current user is superuser, abort with 403 if not.
    """
    if not is_superuser():
        logger.warning(
            "Non-superuser '%s' attempted to access protected API",
            current_user.username if current_user else "anonymous",
        )
        abort(
            403,
            description=(
                "Access denied. User and role management is restricted to "
                "platform administrators. Manage users in your identity provider."
            ),
        )


def _get_current_tenant_pk() -> Optional[int]:
    """Get the current tenant's primary key from request context."""
    return g.get("tenant_pk")


class TenantUserFilter(BaseFilter):
    """
    Filter users by tenant_id for tenant-scoped access.

    Uses module-level imports for User and UserTenant to avoid
    per-request import overhead.
    """

    name = "Tenant Filter"
    arg_name = "tenant_id"

    def apply(self, query: Any, value: Any) -> Any:
        # Superusers see all
        if is_superuser():
            return query

        # Get current tenant
        tenant_pk = _get_current_tenant_pk()
        if not tenant_pk:
            # No tenant context - return empty
            return query.filter(text("1=0"))

        # Join with user_tenants to filter users
        return query.join(UserTenant, User.id == UserTenant.user_id).filter(
            UserTenant.tenant_id == tenant_pk
        )


def _check_user_tenant_access(user_id: int) -> None:
    """
    Check if current user can access the specified user.

    Caches the result in g context to avoid repeated DB queries
    for the same user_id within a single request.
    """
    if is_superuser():
        return

    tenant_pk = _get_current_tenant_pk()
    if not tenant_pk:
        abort(403, description="No tenant context")

    # Check cache first
    cache_key = f"_user_tenant_access_{user_id}"
    cached_tenant_id = g.get(cache_key)
    if cached_tenant_id is not None:
        if cached_tenant_id != tenant_pk:
            abort(403, description="Cannot access users from other tenants")
        return

    mapping = db.session.query(UserTenant).filter_by(user_id=user_id).first()

    if not mapping:
        # User without tenant can only be accessed by superusers
        abort(403, description="Cannot access user account without tenant association")

    # Cache for this request
    g.setdefault(cache_key, mapping.tenant_id)

    # Tenant admins can only access their own tenant's users
    if mapping.tenant_id != tenant_pk:
        logger.warning(
            "User '%s' attempted to access user %s from different tenant",
            current_user.username,
            user_id,
        )
        abort(403, description="Cannot access users from other tenants")


class TenantAwareUserApi:
    """
    Mixin that adds tenant-scoped access to User API endpoints.
    """

    def get_headless(self, pk: int) -> Any:
        """GET user by ID - tenant-scoped."""
        _check_user_tenant_access(pk)
        return super().get_headless(pk)  # type: ignore[misc]

    def get_list_headless(self, **kwargs: Any) -> Any:
        """GET list of users - filtered by TenantUserFilter via base_filters."""
        return super().get_list_headless(**kwargs)  # type: ignore[misc]

    def post_headless(self) -> Any:
        """POST create user - SUPERUSER ONLY."""
        _check_api_superuser()
        return super().post_headless()  # type: ignore[misc]

    def put_headless(self, pk: int) -> Any:
        """PUT update user - tenant-scoped (e.g., assign roles)."""
        _check_user_tenant_access(pk)
        return super().put_headless(pk)  # type: ignore[misc]

    def delete_headless(self, pk: int) -> Any:
        """DELETE user - SUPERUSER ONLY."""
        _check_api_superuser()
        return super().delete_headless(pk)  # type: ignore[misc]


class TenantAwareRoleApi:
    """
    Mixin that adds superuser checks to Role API endpoints.
    """

    def get_headless(self, pk: int) -> Any:
        """GET role by ID - SUPERUSER ONLY."""
        _check_api_superuser()
        return super().get_headless(pk)  # type: ignore[misc]

    def get_list_headless(self, **kwargs: Any) -> Any:
        """GET list of roles - SUPERUSER ONLY."""
        _check_api_superuser()
        return super().get_list_headless(**kwargs)  # type: ignore[misc]

    def post_headless(self) -> Any:
        """POST create role - SUPERUSER ONLY."""
        _check_api_superuser()
        return super().post_headless()  # type: ignore[misc]

    def put_headless(self, pk: int) -> Any:
        """PUT update role - SUPERUSER ONLY."""
        _check_api_superuser()
        return super().put_headless(pk)  # type: ignore[misc]

    def delete_headless(self, pk: int) -> Any:
        """DELETE role - SUPERUSER ONLY."""
        _check_api_superuser()
        return super().delete_headless(pk)  # type: ignore[misc]


# Create the combined API classes
class MultiTenantUserApi(TenantAwareUserApi, SupersetUserApi):
    """
    User API with tenant-scoped access.
    """

    base_filters = [
        ["id", TenantUserFilter, lambda: []],
    ]


class MultiTenantRoleApi(TenantAwareRoleApi, SupersetRoleApi):
    """
    Role API with superuser-only access.
    """

    pass


# =============================================================================
# Multi-Tenant Security Manager
# =============================================================================


class MultiTenantSecurityManager(SupersetSecurityManager):
    """
    Custom Security Manager that handles multi-tenant OAuth authentication.
    """

    # Override FAB views to add superuser checks
    userdbmodelview = TenantAwareUserDBModelView
    useroauthmodelview = TenantAwareUserOAuthModelView
    rolemodelview = TenantAwareRoleModelView

    # Override FAB APIs to add superuser checks
    user_api = MultiTenantUserApi
    role_api = MultiTenantRoleApi

    def __init__(self, appbuilder: Any) -> None:
        """Initialize the security manager with OAuth provider cache."""
        super().__init__(appbuilder)
        self._oauth_providers_cache: dict[str, Any] = {}

    def oauth_user_info(self, provider: str, response: Any = None) -> dict[str, Any]:
        """
        Extract user info from OAuth response.
        """
        try:
            logger.debug("oauth_user_info called for provider: %s", provider)

            if provider not in self.oauth_remotes:
                logger.error(
                    "Provider %s not found in oauth_remotes: %s",
                    provider,
                    list(self.oauth_remotes.keys()),
                )
                return {}

            me = self.oauth_remotes[provider].userinfo()
            logger.debug("Received userinfo from OAuth: %s", me)

            # Get current tenant from request context or session
            tenant = g.get("tenant")
            if not tenant:
                tenant_slug = session.get("tenant_id")
                if tenant_slug:
                    tenant = (
                        db.session.query(Tenant).filter_by(slug=tenant_slug).first()
                    )

            tenant_id = tenant.id if tenant else None

            # Extract groups for role mapping
            groups = me.get("groups", [])
            realm_roles = me.get("realm_access", {}).get("roles", [])
            groups.extend(realm_roles)

            user_info = {
                "username": me.get("preferred_username", me.get("sub")),
                "email": me.get("email", ""),
                "first_name": me.get("given_name", ""),
                "last_name": me.get("family_name", ""),
                "role_keys": groups,
                "tenant_id": tenant_id,
            }

            logger.debug(
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

        Uses PostgreSQL upsert to handle race conditions when multiple
        requests for the same user arrive simultaneously.
        """
        logger.debug("auth_user_oauth called with userinfo: %s", userinfo)

        tenant_id = userinfo.pop("tenant_id", None)

        try:
            user = super().auth_user_oauth(userinfo)
        except Exception as e:
            logger.exception("Error in parent auth_user_oauth: %s", str(e))
            return None

        if user and tenant_id:
            # Store in session for request-scoped access
            session["user_tenant_id"] = tenant_id

            # Use PostgreSQL upsert to avoid race conditions
            # If two requests arrive simultaneously for the same user,
            # the unique constraint on user_id prevents duplicates
            try:
                stmt = pg_insert(UserTenant).values(
                    user_id=user.id,
                    tenant_id=tenant_id,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={"tenant_id": tenant_id},
                )
                db.session.execute(stmt)
                db.session.commit()
                logger.debug(
                    "Upserted user-tenant mapping for %s -> %s",
                    user.username,
                    tenant_id,
                )
            except IntegrityError as e:
                # Fallback: if upsert fails, try to update existing
                db.session.rollback()
                logger.warning(
                    "Upsert failed for user %s, attempting update: %s",
                    user.username,
                    str(e),
                )
                mapping = (
                    db.session.query(UserTenant).filter_by(user_id=user.id).first()
                )
                if mapping:
                    mapping.tenant_id = tenant_id
                    db.session.commit()

        return user

    def get_oauth_redirect_url(self, provider: str) -> str:
        """
        Get the OAuth callback URL.
        """
        return url_for(
            "AuthOAuthView.oauth_authorized",
            provider=provider,
            _external=True,
        )

    def get_current_tenant_id(self) -> Optional[int]:
        """
        Get the current user's tenant ID.
        """
        tenant = g.get("tenant")
        if tenant:
            return tenant.id
        return session.get("user_tenant_id")

    def register_oauth_provider(self, provider_config: dict[str, Any]) -> None:
        """
        Register an OAuth provider dynamically.
        """
        provider_name = provider_config["name"]

        if provider_name in self._oauth_providers_cache:
            logger.debug("OAuth provider %s already registered", provider_name)
            return

        logger.info("Registering OAuth provider: %s", provider_name)

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

        if not hasattr(self.appbuilder.app.config, "OAUTH_PROVIDERS"):
            self.appbuilder.app.config["OAUTH_PROVIDERS"] = []

        self.appbuilder.app.config["OAUTH_PROVIDERS"].append(provider_config)
        self._oauth_providers_cache[provider_name] = provider_config

        logger.info("Successfully registered OAuth provider: %s", provider_name)

    def get_oauth_login_url(self, tenant_provider: str) -> str:
        """
        Get the OAuth login URL for a specific tenant's provider.
        """
        return url_for("AuthOAuthView.login", provider=tenant_provider)

    def get_keycloak_logout_url(self, tenant: Any, post_logout_redirect: str) -> str:
        """
        Get the OAuth logout URL for single sign-out.
        """
        from flask import current_app

        # Use tenant's oauth_issuer if available
        if tenant.oauth_issuer and "/realms/" in tenant.oauth_issuer:
            base_url = tenant.oauth_issuer.split("/realms/")[0]
            realm = tenant.keycloak_realm
        else:
            base_url = current_app.config.get("KEYCLOAK_BASE_URL", "")
            realm = tenant.keycloak_realm

        logout_url = (
            f"{base_url}/realms/{realm}"
            f"/protocol/openid-connect/logout"
            f"?post_logout_redirect_uri={quote(post_logout_redirect)}"
            f"&client_id={tenant.client_id}"
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
        """
        tenant_id = g.get("tenant_id")

        # Superusers can see all schemas
        if is_superuser():
            return super().get_schemas_accessible_by_user(
                database, catalog, schemas, hierarchical
            )

        # For tenant users, filter to ONLY their tenant's schema
        if tenant_id:
            tenant_schema = f"tenant_{tenant_id}"
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


# Legacy alias for backward compatibility
KeycloakMultiTenantSecurityManager = MultiTenantSecurityManager
