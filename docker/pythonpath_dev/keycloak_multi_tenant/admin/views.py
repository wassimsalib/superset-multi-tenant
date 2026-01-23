# TODO: Add Apache license header
"""
Flask-AppBuilder admin views for tenant management.

IMPORTANT: The TenantModelView is restricted to SUPERUSERS ONLY.
Tenant admins should NOT be able to see or manage other tenants.

The is_superuser function is defined in security_manager.py and shared
across all admin views for consistency.
"""

import logging
from typing import Any

from flask import abort, Flask, flash, g, redirect, url_for
from flask_appbuilder import ModelView, expose
from flask_appbuilder.fieldwidgets import BS3PasswordFieldWidget
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder.security.decorators import has_access
from flask_login import current_user
from wtforms import PasswordField, StringField, validators

from keycloak_multi_tenant.models import Tenant
from keycloak_multi_tenant.security_manager import is_superuser

logger = logging.getLogger(__name__)


class TenantModelView(ModelView):
    """
    Admin view for managing tenants.

    SECURITY: This view is restricted to SUPERUSERS ONLY.
    Tenant admins cannot see or manage other tenants.

    Provides CRUD operations for tenant configuration including
    Keycloak realm and client credentials with encrypted storage.
    """

    datamodel = SQLAInterface(Tenant)
    route_base = "/tenant"

    # List view - don't show secrets
    list_columns = [
        "tenant_id",
        "name",
        "subdomain",
        "keycloak_realm",
        "keycloak_client_id",
        "warehouse_db_user",
        "is_active",
        "created_at",
    ]

    # Search
    search_columns = ["tenant_id", "name", "subdomain", "keycloak_realm"]

    # Add form - secrets handled via add_form_extra_fields
    add_columns = [
        "tenant_id",
        "name",
        "subdomain",
        "keycloak_realm",
        "keycloak_client_id",
        "warehouse_db_user",
        "is_active",
        "config_overrides",
    ]

    # Edit form - secrets handled via edit_form_extra_fields
    edit_columns = [
        "tenant_id",
        "name",
        "subdomain",
        "keycloak_realm",
        "keycloak_client_id",
        "warehouse_db_user",
        "is_active",
        "config_overrides",
    ]

    # Show view - don't show secrets
    show_columns = [
        "id",
        "tenant_id",
        "name",
        "subdomain",
        "keycloak_realm",
        "keycloak_client_id",
        "warehouse_db_user",
        "is_active",
        "created_at",
        "updated_at",
        "config_overrides",
    ]

    # Labels
    label_columns = {
        "tenant_id": "Tenant ID",
        "name": "Display Name",
        "subdomain": "Subdomain",
        "keycloak_realm": "Keycloak Realm",
        "keycloak_client_id": "Client ID",
        "keycloak_client_secret": "Client Secret",
        "warehouse_db_user": "Warehouse DB User",
        "warehouse_db_password": "Warehouse DB Password",
        "is_active": "Active",
        "config_overrides": "Configuration Overrides",
        "created_at": "Created",
        "updated_at": "Updated",
    }

    # Descriptions for form fields
    description_columns = {
        "tenant_id": "Unique identifier for the tenant (e.g., 'customer1')",
        "subdomain": "Subdomain for tenant access (e.g., 'customer1' for customer1.app.example.com)",
        "keycloak_realm": "Keycloak realm name for this tenant",
        "keycloak_client_id": "OAuth client ID configured in Keycloak",
        "keycloak_client_secret": "OAuth client secret (stored encrypted)",
        "warehouse_db_user": "PostgreSQL user for data warehouse access (e.g., 'tenant_demo_user')",
        "warehouse_db_password": "Password for warehouse DB user (stored encrypted)",
        "config_overrides": "JSON object with tenant-specific configuration overrides",
    }

    # Use password widget for secret fields
    add_form_extra_fields = {
        "keycloak_client_secret": PasswordField(
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
        "keycloak_client_secret": PasswordField(
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
        "tenant_id": [
            validators.DataRequired(),
            validators.Regexp(
                r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
                message="Must be lowercase alphanumeric with hyphens, "
                        "not starting or ending with hyphen",
            ),
        ],
        "subdomain": [
            validators.DataRequired(),
            validators.Regexp(
                r"^[a-z0-9][a-z0-9-]*[a-z0-9]$",
                message="Must be lowercase alphanumeric with hyphens",
            ),
        ],
    }

    # Only Admin role can manage tenants
    base_permissions = ["can_list", "can_show", "can_add", "can_edit", "can_delete"]

    def _check_superuser(self) -> None:
        """Check if user is superuser, abort with 403 if not."""
        if not is_superuser():
            logger.warning(
                "Non-superuser '%s' attempted to access tenant management",
                current_user.username if current_user else "anonymous"
            )
            abort(403, description="Access denied. Only system administrators can manage tenants.")

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
        logger.info("Creating new tenant: %s", item.tenant_id)

        # Encrypt the client secret before storage
        if item.keycloak_client_secret:
            item.set_encrypted_secret(item.keycloak_client_secret)

        # Encrypt the warehouse password if provided
        from flask import request
        warehouse_password = request.form.get("warehouse_db_password", "")
        if warehouse_password:
            item.set_warehouse_password(warehouse_password)

    def pre_update(self, item: Tenant) -> None:
        """Handle secret updates and clear cache."""
        self._check_superuser()
        logger.info("Updating tenant: %s", item.tenant_id)

        from flask import request

        # Handle Keycloak client secret
        form_secret = request.form.get("keycloak_client_secret", "")
        if form_secret:
            item.set_encrypted_secret(form_secret)

        # Handle warehouse password
        warehouse_password = request.form.get("warehouse_db_password", "")
        if warehouse_password:
            item.set_warehouse_password(warehouse_password)
            # Clear cached database engine for this tenant
            try:
                from keycloak_multi_tenant.tenant_database import get_tenant_db_manager
                get_tenant_db_manager().close_tenant_engine(item.tenant_id)
            except Exception as e:
                logger.warning("Could not clear tenant engine cache: %s", e)

        # Clear tenant cache when updated
        from keycloak_multi_tenant.tenant_resolver import tenant_resolver
        tenant_resolver.clear_cache()

    def pre_delete(self, item: Tenant) -> None:
        """Actions before deleting a tenant."""
        self._check_superuser()
        logger.warning("Deleting tenant: %s", item.tenant_id)

        # Clear tenant cache
        from keycloak_multi_tenant.tenant_resolver import tenant_resolver
        tenant_resolver.clear_cache()

    @expose("/test-connection/<int:pk>")
    @has_access
    def test_connection(self, pk: int) -> Any:
        """
        Test Keycloak connection for a tenant.

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
            from keycloak_multi_tenant.keycloak_client import keycloak_client

            # Try to fetch OIDC configuration
            import requests

            config = keycloak_client.get_oauth_provider_config(tenant)
            metadata_url = config["remote_app"]["server_metadata_url"]

            response = requests.get(metadata_url, timeout=10)
            response.raise_for_status()

            flash(
                f"Successfully connected to Keycloak realm '{tenant.keycloak_realm}'",
                "success",
            )

        except Exception as e:
            logger.error(
                "Failed to connect to Keycloak for tenant %s: %s",
                tenant.tenant_id,
                str(e),
            )
            flash(f"Connection failed: {str(e)}", "danger")

        return redirect(url_for(".show", pk=pk))

    @expose("/test-warehouse/<int:pk>")
    @has_access
    def test_warehouse(self, pk: int) -> Any:
        """
        Test warehouse database connection for a tenant.

        Verifies that the per-tenant database credentials work and
        that isolation is properly configured.

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
                f"Tenant '{tenant.tenant_id}' does not have warehouse credentials configured. "
                "Set 'Warehouse DB User' and 'Warehouse DB Password' to enable secure isolation.",
                "warning",
            )
            return redirect(url_for(".show", pk=pk))

        try:
            from keycloak_multi_tenant.tenant_database import get_tenant_db_manager
            from sqlalchemy import text

            manager = get_tenant_db_manager()
            engine = manager.get_tenant_engine(tenant.tenant_id)

            if not engine:
                flash("Failed to create database engine for tenant", "danger")
                return redirect(url_for(".show", pk=pk))

            # Test connection
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
                tenant.tenant_id,
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

    # Register the tenant management view
    appbuilder.add_view(
        TenantModelView,
        "Tenants",
        icon="fa-building",
        category="Security",
        category_icon="fa-lock",
    )

    logger.info("Registered tenant admin views (superuser access only)")
