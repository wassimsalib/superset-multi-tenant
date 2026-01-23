# TODO: Add license header
"""
Schema-based tenant isolation for Superset metadata.

Each tenant has their own schema (tenant_demo, tenant_acme).
The middleware sets search_path on each request to route queries
to the correct tenant schema.

Architecture:
- public schema: Flask-AppBuilder tables (ab_user, ab_role, etc.)
- tenant_X schema: Superset metadata tables (dashboards, slices, tables, dbs, etc.)

How it works:
1. Each tenant's Superset metadata lives in its own PostgreSQL schema
2. On each request, middleware sets: search_path = tenant_X, public
3. Queries automatically route to the correct tenant schema
4. At end of request, search_path is reset to public

Security guarantees:
- Physical schema isolation - no RLS policies needed
- Queries automatically route to correct schema
- Cross-tenant access requires explicit schema qualification (blocked by permissions)
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Optional

from flask import Flask, g, has_request_context
from sqlalchemy import text

from superset.multitenancy.isolation.schema_isolation import get_tenant_schema

logger = logging.getLogger(__name__)


def get_current_tenant_id() -> Optional[str]:
    """
    Get the current tenant ID (slug) from request context.

    Returns:
        Tenant slug string (e.g., "acme", "demo") or None
    """
    if not has_request_context():
        return None
    return g.get("tenant_id")


@contextmanager
def tenant_context(tenant_id: str) -> Generator[None, None, None]:
    """
    Context manager for setting tenant context in scripts.

    Use this when running scripts or batch jobs outside of a web request
    to ensure the correct tenant schema is used.

    Example:
        with tenant_context("acme"):
            # All queries here use tenant_acme schema
            dashboards = Dashboard.query.all()

    Args:
        tenant_id: Tenant slug (e.g., "acme", "demo")

    Yields:
        None
    """
    from superset import db

    schema = get_tenant_schema(tenant_id)
    db.session.execute(text(f"SET search_path = {schema}, public"))
    logger.debug("Set search_path to %s, public", schema)
    try:
        yield
    finally:
        db.session.execute(text("SET search_path = public"))
        logger.debug("Reset search_path to public")


def setup_metadata_isolation(app: Flask) -> None:
    """
    Set up schema-based tenant isolation.

    Note: The actual search_path setting is handled by the middleware
    in middleware.py. This function is kept for API compatibility and
    to log that the isolation system is active.

    Args:
        app: Flask application instance
    """
    logger.info(
        "Schema-based tenant isolation initialized (search_path set by middleware)"
    )
