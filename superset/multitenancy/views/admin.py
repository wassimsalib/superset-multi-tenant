# TODO: Add license header
"""
Flask-AppBuilder admin views for tenant management.

IMPORTANT: The TenantModelView is restricted to SUPERUSERS ONLY.
Tenant admins should NOT be able to see or manage other tenants.

The is_superuser function is defined in security_manager.py and shared
across all admin views for consistency.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, abort, flash, redirect, url_for
from flask_appbuilder import ModelView, expose
from flask_appbuilder.fieldwidgets import BS3PasswordFieldWidget
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder.security.decorators import has_access
from flask_login import current_user
from wtforms import PasswordField, validators

from superset.multitenancy.models import Tenant
from superset.multitenancy.security_manager import is_superuser

logger = logging.getLogger(__name__)


class TenantModelView(ModelView):
    """
    Admin view for managing tenants.

    SECURITY: This view is restricted to SUPERUSERS ONLY.
    Tenant admins cannot see or manage other tenants.

    Provides CRUD operations for tenant configuration including
    OAuth credentials with encrypted storage.
    """

    datamodel = SQLAInterface(Tenant)
    route_base = "/tenant"

    # List view - don't show secrets
    list_columns = [
        "slug",
        "name",
        "uuid",
        "is_admin_tenant",
        "oauth_issuer",
        "client_id",
        "warehouse_db_user",
        "is_active",
        "created_on",
    ]

    # Search
    search_columns = ["slug", "name", "uuid", "oauth_issuer"]

    # Add form
    add_columns = [
        "slug",
        "name",
        "is_admin_tenant",
        "oauth_issuer",
        "client_id",
        "scopes",
        "default_schema",
        "warehouse_db_user",
        "is_active",
        "config_overrides",
    ]

    # Edit form
    edit_columns = [
        "slug",
        "name",
        "is_admin_tenant",
        "oauth_issuer",
        "client_id",
        "scopes",
        "default_schema",
        "warehouse_db_user",
        "is_active",
        "config_overrides",
    ]

    # Show view - don't show secrets
    show_columns = [
        "id",
        "uuid",
        "slug",
        "name",
        "is_admin_tenant",
        "oauth_issuer",
        "client_id",
        "scopes",
        "default_schema",
        "warehouse_db_user",
        "is_active",
        "created_on",
        "changed_on",
        "config_overrides",
    ]

    # Labels
    label_columns = {
        "slug": "Slug (Subdomain)",
        "name": "Display Name",
        "uuid": "UUID",
        "is_admin_tenant": "Admin Tenant",
        "oauth_issuer": "OAuth Issuer URL",
        "client_id": "Client ID",
        "client_secret": "Client Secret",
        "scopes": "OAuth Scopes",
        "default_schema": "Default Schema",
        "warehouse_db_user": "Warehouse DB User",
        "warehouse_db_password": "Warehouse DB Password",
        "is_active": "Active",
        "config_overrides": "Configuration Overrides",
        "created_on": "Created",
        "changed_on": "Updated",
    }

    # Descriptions for form fields
    description_columns = {
        "slug": "Unique identifier for the tenant (e.g., 'acme' for acme.app.example.com)",
        "is_admin_tenant": "If checked, users from this tenant have superuser privileges",
        "oauth_issuer": "OAuth issuer URL (e.g., 'http://keycloak:8080/realms/acme')",
        "client_id": "OAuth client ID configured in your identity provider",
        "client_secret": "OAuth client secret (stored encrypted)",
        "scopes": "Comma-separated OAuth scopes (default: openid email profile)",
        "default_schema": "PostgreSQL schema name (default: tenant_{slug})",
        "warehouse_db_user": "PostgreSQL user for data warehouse access (e.g., 'tenant_acme_user')",
        "warehouse_db_password": "Password for warehouse DB user (stored encrypted)",
        "config_overrides": "JSON object with tenant-specific configuration overrides",
    }

    # Use password widget for secret fields
    add_form_extra_fields = {
        "client_secret": PasswordField(
            "Client Secret",
            description="OAuth client secret (stored encrypted)",
            widget=BS3PasswordFieldWidget(),
            validators=[validators.DataRequired()],
        ),
        "warehouse_db_password": PasswordField(
            "Warehouse DB Password",
            description="Password for per-tenant warehouse user (enables secure isolation)",
            widget=BS3PasswordFieldWidget(),
            validators=[validators.Optional()],
        ),
    }

    edit_form_extra_fields = {
        "client_secret": PasswordField(
            "Client Secret",
            description="Leave blank to keep existing secret, or enter new value",
            widget=BS3PasswordFieldWidget(),
            validators=[validators.Optional()],
        ),
        "warehouse_db_password": PasswordField(
            "Warehouse DB Password",
            description="Leave blank to keep existing, or enter new password",
            widget=BS3PasswordFieldWidget(),
            validators=[validators.Optional()],
        ),
    }

    # Validators
    validators_columns = {
        "slug": [
            validators.DataRequired(),
            validators.Regexp(
                r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
                message=(
                    "Must be lowercase alphanumeric with hyphens, "
                    "not starting or ending with hyphen"
                ),
            ),
        ],
    }

    base_permissions = ["can_list", "can_show", "can_add", "can_edit", "can_delete"]

    def _check_superuser(self) -> None:
        """Check if user is superuser, abort with 403 if not."""
        if not is_superuser():
            logger.warning(
                "Non-superuser '%s' attempted to access tenant management",
                current_user.username if current_user else "anonymous",
            )
            abort(
                403,
                description="Access denied. Only system administrators can manage tenants.",
            )

    @expose("/list/")
    @has_access
    def list(self):
        """List all tenants - SUPERUSER ONLY."""
        self._check_superuser()
        return super().list()

    @expose("/show/<pk>")
    @has_access
    def show(self, pk):
        """Show tenant details - SUPERUSER ONLY."""
        self._check_superuser()
        return super().show(pk)

    @expose("/add")
    @has_access
    def add(self):
        """Add new tenant - SUPERUSER ONLY."""
        self._check_superuser()
        return super().add()

    @expose("/edit/<pk>")
    @has_access
    def edit(self, pk):
        """Edit tenant - SUPERUSER ONLY."""
        self._check_superuser()
        return super().edit(pk)

    @expose("/delete/<pk>")
    @has_access
    def delete(self, pk):
        """Delete tenant - SUPERUSER ONLY."""
        self._check_superuser()
        return super().delete(pk)

    def pre_add(self, item: Tenant) -> None:
        """Encrypt secrets before adding a new tenant."""
        self._check_superuser()
        logger.info("Creating new tenant: %s", item.slug)

        if item.client_secret:
            item.set_encrypted_secret(item.client_secret)

        from flask import request

        warehouse_password = request.form.get("warehouse_db_password", "")
        if warehouse_password:
            item.set_warehouse_password(warehouse_password)

    def pre_update(self, item: Tenant) -> None:
        """Handle secret updates and clear cache."""
        self._check_superuser()
        logger.info("Updating tenant: %s", item.slug)

        from flask import request

        form_secret = request.form.get("client_secret", "")
        if form_secret:
            item.set_encrypted_secret(form_secret)

        warehouse_password = request.form.get("warehouse_db_password", "")
        if warehouse_password:
            item.set_warehouse_password(warehouse_password)
            try:
                from superset.multitenancy.isolation import get_tenant_db_manager

                get_tenant_db_manager().close_tenant_engine(item.slug)
            except Exception as e:
                logger.warning("Could not clear tenant engine cache: %s", e)

        from superset.multitenancy.tenant_resolver import tenant_resolver

        tenant_resolver.clear_cache()

    def pre_delete(self, item: Tenant) -> None:
        """Actions before deleting a tenant."""
        self._check_superuser()
        logger.warning("Deleting tenant: %s", item.slug)

        from superset.multitenancy.tenant_resolver import tenant_resolver

        tenant_resolver.clear_cache()

    @expose("/test-connection/<int:pk>")
    @has_access
    def test_connection(self, pk: int) -> Any:
        """
        Test OAuth connection for a tenant.

        Args:
            pk: Tenant primary key

        Returns:
            Redirect to show view with result message
        """
        self._check_superuser()
        tenant = self.datamodel.get(pk)
        if not tenant:
            flash("Tenant not found", "danger")
            return redirect(url_for(".list"))

        try:
            import requests

            from superset.multitenancy.oauth.keycloak import KeycloakOAuthProvider

            provider = KeycloakOAuthProvider()
            config = provider.get_oauth_provider_config(tenant)
            metadata_url = config["remote_app"]["server_metadata_url"]

            response = requests.get(metadata_url, timeout=10)
            response.raise_for_status()

            flash(
                f"Successfully connected to OAuth provider at '{tenant.oauth_issuer}'",
                "success",
            )

        except Exception as e:
            logger.error(
                "Failed to connect to OAuth provider for tenant %s: %s",
                tenant.slug,
                str(e),
            )
            flash(f"Connection failed: {str(e)}", "danger")

        return redirect(url_for(".show", pk=pk))

    @expose("/test-warehouse/<int:pk>")
    @has_access
    def test_warehouse(self, pk: int) -> Any:
        """
        Test warehouse database connection for a tenant.

        Args:
            pk: Tenant primary key

        Returns:
            Redirect to show view with result message
        """
        self._check_superuser()
        tenant = self.datamodel.get(pk)
        if not tenant:
            flash("Tenant not found", "danger")
            return redirect(url_for(".list"))

        if not tenant.has_warehouse_credentials():
            flash(
                f"Tenant '{tenant.slug}' does not have warehouse credentials configured. "
                "Set 'Warehouse DB User' and 'Warehouse DB Password' to enable secure isolation.",
                "warning",
            )
            return redirect(url_for(".show", pk=pk))

        try:
            from sqlalchemy import text

            from superset.multitenancy.isolation import get_tenant_db_manager

            manager = get_tenant_db_manager()
            engine = manager.get_tenant_engine(tenant.slug)

            if not engine:
                flash("Failed to create database engine for tenant", "danger")
                return redirect(url_for(".show", pk=pk))

            with engine.connect() as conn:
                result = conn.execute(text("SELECT current_user, current_schema()"))
                row = result.fetchone()
                db_user, db_schema = row[0], row[1]

            flash(
                f"Warehouse connection successful! "
                f"Connected as '{db_user}' with schema '{db_schema}'",
                "success",
            )

        except Exception as e:
            logger.error(
                "Failed to connect to warehouse for tenant %s: %s",
                tenant.slug,
                str(e),
            )
            flash(f"Warehouse connection failed: {str(e)}", "danger")

        return redirect(url_for(".show", pk=pk))


def register_admin_views(app: Flask) -> None:
    """
    Register tenant admin views with Flask-AppBuilder.

    NOTE: The Tenants view is only accessible to superusers.
    The menu item will be shown to all admins, but access is blocked
    at the view level for non-superusers.

    Args:
        app: Flask application instance
    """
    from superset.extensions import appbuilder

    appbuilder.add_view(
        TenantModelView,
        "Tenants",
        icon="fa-building",
        category="Security",
        category_icon="fa-lock",
    )

    logger.info("Registered tenant admin views (superuser access only)")
