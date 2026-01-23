# TODO: Add license header
"""
CLI command to seed tenant data.

Usage:
    superset seed-tenants --config tenants.yaml
    superset seed-tenants --demo  # Creates demo and acme tenants
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import click
from flask.cli import with_appcontext

logger = logging.getLogger(__name__)


def create_tenant(
    slug: str,
    name: str,
    oauth_issuer: str,
    client_id: str,
    client_secret: str,
    is_admin_tenant: bool = False,
    scopes: Optional[str] = None,
    default_schema: Optional[str] = None,
    warehouse_db_user: Optional[str] = None,
    warehouse_db_password: Optional[str] = None,
) -> Any:
    """
    Create or update a tenant.

    Args:
        slug: Tenant slug (subdomain identifier)
        name: Display name
        oauth_issuer: OAuth issuer URL
        client_id: OAuth client ID
        client_secret: OAuth client secret (will be encrypted)
        is_admin_tenant: Whether this is an admin tenant
        scopes: Comma-separated OAuth scopes
        default_schema: PostgreSQL schema name
        warehouse_db_user: Warehouse database user
        warehouse_db_password: Warehouse database password (will be encrypted)

    Returns:
        Tenant object
    """
    from superset.extensions import db
    from superset.multitenancy.models import Tenant

    tenant = db.session.query(Tenant).filter_by(slug=slug).first()

    if tenant:
        logger.info("Updating existing tenant: %s", slug)
        tenant.name = name
        tenant.oauth_issuer = oauth_issuer
        tenant.client_id = client_id
        tenant.is_admin_tenant = is_admin_tenant
        if scopes:
            tenant.scopes = scopes
        if default_schema:
            tenant.default_schema = default_schema
        if warehouse_db_user:
            tenant.warehouse_db_user = warehouse_db_user
    else:
        logger.info("Creating new tenant: %s", slug)
        tenant = Tenant(
            slug=slug,
            name=name,
            oauth_issuer=oauth_issuer,
            client_id=client_id,
            is_admin_tenant=is_admin_tenant,
            scopes=scopes,
            default_schema=default_schema,
            warehouse_db_user=warehouse_db_user,
        )
        db.session.add(tenant)

    # Set encrypted secrets
    if client_secret:
        tenant.set_encrypted_secret(client_secret)
    if warehouse_db_password:
        tenant.set_warehouse_password(warehouse_db_password)

    db.session.commit()
    logger.info("Tenant %s saved successfully", slug)
    return tenant


@click.command()
@click.option("--demo", is_flag=True, help="Create demo tenants (demo and acme)")
@click.option(
    "--keycloak-url",
    default="http://host.docker.internal:8180",
    help="Keycloak base URL",
)
@click.option(
    "--client-secret",
    default="changeme",
    help="Default client secret for demo tenants",
)
@with_appcontext
def seed_tenants(demo: bool, keycloak_url: str, client_secret: str) -> None:
    """Seed tenant data for multi-tenancy."""
    if demo:
        logger.info("Creating demo tenants...")

        # Demo tenant
        create_tenant(
            slug="demo",
            name="Demo Company",
            oauth_issuer=f"{keycloak_url}/realms/demo",
            client_id="superset",
            client_secret=client_secret,
            is_admin_tenant=False,
        )

        # Acme tenant
        create_tenant(
            slug="acme",
            name="ACME Corporation",
            oauth_issuer=f"{keycloak_url}/realms/acme",
            client_id="superset",
            client_secret=client_secret,
            is_admin_tenant=False,
        )

        # Admin tenant (optional)
        create_tenant(
            slug="admin",
            name="Platform Admin",
            oauth_issuer=f"{keycloak_url}/realms/admin",
            client_id="superset",
            client_secret=client_secret,
            is_admin_tenant=True,
        )

        click.echo("Demo tenants created successfully!")
    else:
        click.echo("Use --demo to create demo tenants or --config for custom config")
