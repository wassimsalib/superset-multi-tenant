# TODO: Add license header
"""
PostgreSQL Schema-Based Tenant Isolation for Superset.

Provides automatic schema isolation for multi-tenant deployments where
each tenant's data lives in a separate PostgreSQL schema.

Architecture:
    - Single PostgreSQL database
    - One schema per tenant (e.g., tenant_demo, tenant_acme)
    - Per-tenant database users for security (recommended)
    - Fallback: Single database user with search_path (convenience only)

Security Model:
    - Per-tenant DB users: True isolation via PostgreSQL permissions (RECOMMENDED)
    - search_path: Convenience routing only (NOT a security boundary)
    - Optional RLS as defense-in-depth
    - Audit logging for schema switches

See tenant_database.py for the per-tenant credential manager.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Optional

from flask import Flask, g, has_request_context
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool

if TYPE_CHECKING:
    from superset.multitenancy.models import Tenant

logger = logging.getLogger(__name__)


# =============================================================================
# Schema Naming Convention
# =============================================================================


def get_tenant_schema(tenant_id: str) -> str:
    """
    Get PostgreSQL schema name for a tenant.

    Args:
        tenant_id: Tenant identifier (slug, e.g., "demo", "acme")

    Returns:
        Schema name (e.g., "tenant_demo", "tenant_acme")
    """
    # Sanitize tenant_id to prevent SQL injection
    safe_tenant_id = "".join(c for c in tenant_id if c.isalnum() or c == "_")
    return f"tenant_{safe_tenant_id}"


def get_tenant_from_schema(schema_name: str) -> Optional[str]:
    """
    Extract tenant slug from schema name.

    Args:
        schema_name: PostgreSQL schema name

    Returns:
        Tenant slug or None if not a tenant schema
    """
    if schema_name.startswith("tenant_"):
        return schema_name[7:]  # Remove "tenant_" prefix
    return None


# =============================================================================
# SQLAlchemy Connection Hooks
# =============================================================================


def setup_schema_isolation(app: Flask) -> None:
    """
    Configure SQLAlchemy to automatically set search_path based on tenant.

    This hooks into SQLAlchemy's connection pool to set the schema
    on every connection checkout.

    Args:
        app: Flask application instance
    """
    from superset import db

    @event.listens_for(Pool, "checkout")
    def set_tenant_schema(
        dbapi_conn: Any, connection_record: Any, connection_proxy: Any
    ) -> None:
        """Set search_path when connection is checked out from pool."""
        if dbapi_conn is None:
            return

        # Only apply to PostgreSQL connections
        conn_type = type(dbapi_conn).__module__
        if "psycopg" not in conn_type and "pg8000" not in conn_type:
            return

        # Use g.tenant_id (string) to avoid detached session issues
        tenant_id = g.get("tenant_id") if has_request_context() else None

        try:
            if tenant_id:
                schema = get_tenant_schema(tenant_id)
                cursor = dbapi_conn.cursor()
                try:
                    cursor.execute(f"SET search_path TO {schema}, public")
                    logger.debug("Set search_path to: %s, public", schema)
                finally:
                    cursor.close()
        except Exception as e:
            logger.debug("Could not set search_path: %s", e)

    @event.listens_for(Pool, "checkin")
    def reset_tenant_schema(dbapi_conn: Any, connection_record: Any) -> None:
        """Reset search_path when connection is returned to pool."""
        if dbapi_conn is None:
            return

        conn_type = type(dbapi_conn).__module__
        if "psycopg" not in conn_type and "pg8000" not in conn_type:
            return

        try:
            cursor = dbapi_conn.cursor()
            try:
                cursor.execute("SET search_path TO public")
            finally:
                cursor.close()
        except Exception as e:
            logger.debug("Could not reset search_path: %s", e)

    logger.info("Schema-based tenant isolation configured")


# =============================================================================
# Database Configuration for Tenant Data Sources
# =============================================================================


class TenantAwareDatabaseConfig:
    """
    Configuration for tenant-aware database connections.

    Use this when configuring Superset database connections that should
    automatically route to tenant schemas.
    """

    @staticmethod
    def get_connection_string(
        base_uri: str,
        tenant_id: str,
        include_schema: bool = True,
    ) -> str:
        """
        Build connection string with tenant schema in options.

        Args:
            base_uri: Base PostgreSQL connection string
            tenant_id: Tenant identifier (slug)
            include_schema: Whether to include schema in connection options

        Returns:
            Modified connection string with schema options
        """
        if not include_schema:
            return base_uri

        schema = get_tenant_schema(tenant_id)

        if "?" in base_uri:
            return f"{base_uri}&options=-csearch_path%3D{schema},public"
        else:
            return f"{base_uri}?options=-csearch_path%3D{schema},public"

    @staticmethod
    def get_sqlalchemy_options(tenant_id: str) -> dict[str, str]:
        """
        Get SQLAlchemy connect_args for tenant isolation.

        Args:
            tenant_id: Tenant identifier (slug)

        Returns:
            Dictionary of connection arguments
        """
        schema = get_tenant_schema(tenant_id)
        return {"options": f"-csearch_path={schema},public"}


# =============================================================================
# Schema Management
# =============================================================================


class TenantSchemaManager:
    """
    Manage PostgreSQL schemas for tenants.

    Handles schema creation, migration, and cleanup.
    """

    def __init__(self, engine: Engine) -> None:
        """
        Initialize schema manager.

        Args:
            engine: SQLAlchemy engine connected to target database
        """
        self.engine = engine

    def create_schema(self, tenant_id: str) -> None:
        """
        Create schema for a new tenant.

        Args:
            tenant_id: Tenant identifier (slug)
        """
        schema = get_tenant_schema(tenant_id)

        with self.engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            conn.commit()
            logger.info("Created schema: %s", schema)

    def drop_schema(self, tenant_id: str, cascade: bool = False) -> None:
        """
        Drop schema for a tenant.

        Args:
            tenant_id: Tenant identifier (slug)
            cascade: If True, drop all objects in schema
        """
        schema = get_tenant_schema(tenant_id)
        cascade_sql = "CASCADE" if cascade else "RESTRICT"

        with self.engine.connect() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} {cascade_sql}"))
            conn.commit()
            logger.warning("Dropped schema: %s", schema)

    def schema_exists(self, tenant_id: str) -> bool:
        """
        Check if tenant schema exists.

        Args:
            tenant_id: Tenant identifier (slug)

        Returns:
            True if schema exists
        """
        schema = get_tenant_schema(tenant_id)

        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"
                ),
                {"schema": schema},
            )
            return result.fetchone() is not None

    def list_tenant_schemas(self) -> list[str]:
        """
        List all tenant schemas.

        Returns:
            List of tenant slugs that have schemas
        """
        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name LIKE 'tenant_%'"
                )
            )
            return [
                get_tenant_from_schema(row[0])
                for row in result.fetchall()
                if get_tenant_from_schema(row[0])
            ]

    def clone_schema(self, source_tenant_id: str, target_tenant_id: str) -> None:
        """
        Clone schema structure from one tenant to another.

        Args:
            source_tenant_id: Source tenant slug
            target_tenant_id: Target tenant slug
        """
        source_schema = get_tenant_schema(source_tenant_id)
        target_schema = get_tenant_schema(target_tenant_id)

        with self.engine.connect() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {target_schema}"))

            tables = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = :schema"
                ),
                {"schema": source_schema},
            ).fetchall()

            for (table_name,) in tables:
                conn.execute(
                    text(
                        f"CREATE TABLE {target_schema}.{table_name} "
                        f"(LIKE {source_schema}.{table_name} INCLUDING ALL)"
                    )
                )

            conn.commit()
            logger.info("Cloned schema %s to %s", source_schema, target_schema)


# =============================================================================
# Row-Level Security (Defense in Depth)
# =============================================================================


class TenantRLSManager:
    """
    Manage PostgreSQL Row-Level Security for additional protection.

    Even with schema isolation, RLS provides defense-in-depth
    in case of misconfiguration.
    """

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def setup_rls_for_table(
        self,
        schema: str,
        table: str,
        tenant_column: str = "tenant_id",
    ) -> None:
        """
        Enable RLS on a table with tenant isolation policy.

        Args:
            schema: Schema name
            table: Table name
            tenant_column: Column containing tenant identifier
        """
        full_table = f"{schema}.{table}"

        with self.engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE {full_table} ENABLE ROW LEVEL SECURITY"))

            conn.execute(
                text(
                    f"""
                CREATE POLICY tenant_isolation ON {full_table}
                USING ({tenant_column} = current_setting('app.current_tenant', true))
            """
                )
            )

            conn.execute(
                text(f"ALTER TABLE {full_table} FORCE ROW LEVEL SECURITY")
            )

            conn.commit()
            logger.info("Enabled RLS on %s", full_table)

    def set_tenant_context(self, conn: Any, tenant_id: str) -> None:
        """
        Set tenant context for RLS policies.

        Args:
            conn: Database connection
            tenant_id: Tenant identifier (slug)
        """
        conn.execute(text(f"SET app.current_tenant = '{tenant_id}'"))


# =============================================================================
# Superset Database Connection Hook
# =============================================================================


def create_tenant_database_uri(
    base_uri: str,
    tenant_id: Optional[str] = None,
) -> str:
    """
    Create database URI with tenant schema isolation.

    Use this when creating Superset database connections.

    Args:
        base_uri: Base PostgreSQL connection string
        tenant_id: Optional tenant identifier (uses current tenant if None)

    Returns:
        Connection string with schema options
    """
    if tenant_id is None:
        tenant_id = g.get("tenant_id") if has_request_context() else None

    if tenant_id:
        return TenantAwareDatabaseConfig.get_connection_string(base_uri, tenant_id)

    return base_uri


def get_tenant_schema_for_connection() -> Optional[str]:
    """
    Get the current tenant's schema name for database connections.

    Returns:
        Schema name or None if no tenant context
    """
    tenant_id = g.get("tenant_id") if has_request_context() else None
    if tenant_id:
        return get_tenant_schema(tenant_id)
    return None


# =============================================================================
# Middleware Integration
# =============================================================================


def setup_db_isolation_middleware(app: Flask) -> None:
    """
    Set up database isolation middleware.

    Integrates with the existing tenant middleware to ensure
    database connections use correct schema.

    Args:
        app: Flask application
    """
    from superset import db

    @app.before_request
    def set_db_tenant_context() -> None:
        """Set database tenant context before each request."""
        tenant_id = g.get("tenant_id")
        if tenant_id:
            try:
                db.session.execute(text(f"SET app.current_tenant = '{tenant_id}'"))
            except Exception as e:
                logger.warning("Could not set tenant context: %s", e)

    logger.info("Database isolation middleware configured")


# =============================================================================
# Initialization
# =============================================================================


def init_db_isolation(app: Flask) -> None:
    """
    Initialize all database isolation components.

    Call this from FLASK_APP_MUTATOR in superset_config.py.

    Args:
        app: Flask application
    """
    setup_schema_isolation(app)
    setup_db_isolation_middleware(app)
    logger.info("Database isolation initialized")


# =============================================================================
# Per-Tenant Database Integration (Security Model)
# =============================================================================


def get_secure_tenant_engine(tenant_id: Optional[str] = None) -> Optional[Engine]:
    """
    Get a secure database engine for the tenant.

    This uses per-tenant database credentials which provide true isolation
    via PostgreSQL permissions.

    Args:
        tenant_id: Tenant identifier (uses current request tenant if None)

    Returns:
        SQLAlchemy Engine with tenant credentials, or None if not configured
    """
    from superset.multitenancy.isolation.tenant_database import get_tenant_db_manager

    if tenant_id is None:
        tenant_id = g.get("tenant_id") if has_request_context() else None

    if not tenant_id:
        return None

    return get_tenant_db_manager().get_tenant_engine(tenant_id)


def execute_secure_query(sql: str, params: Optional[dict[str, Any]] = None) -> Any:
    """
    Execute a query using the current tenant's secure credentials.

    This is the recommended way to execute data warehouse queries as it
    uses per-tenant database users for true isolation.

    Args:
        sql: SQL query to execute
        params: Optional query parameters

    Returns:
        Query result

    Raises:
        PermissionError: If tenant doesn't have secure credentials configured
        RuntimeError: If no tenant context
    """
    from superset.multitenancy.isolation.tenant_database import get_tenant_db_manager

    tenant_id = g.get("tenant_id") if has_request_context() else None
    if not tenant_id:
        raise RuntimeError("No tenant context - cannot execute query")

    return get_tenant_db_manager().execute_query(tenant_id, sql, params)


def has_secure_warehouse_access(tenant_id: Optional[str] = None) -> bool:
    """
    Check if a tenant has secure warehouse access configured.

    Secure access means per-tenant database credentials are set up,
    providing true PostgreSQL permission-based isolation.

    Args:
        tenant_id: Tenant identifier (uses current request tenant if None)

    Returns:
        True if secure credentials are configured
    """
    from superset.multitenancy.models import Tenant

    if tenant_id is None:
        tenant_id = g.get("tenant_id") if has_request_context() else None

    if not tenant_id:
        return False

    tenant = Tenant.query.filter_by(slug=tenant_id, is_active=True).first()
    return tenant.has_warehouse_credentials() if tenant else False


def get_warehouse_security_status() -> dict[str, Any]:
    """
    Get security status for the current tenant's warehouse access.

    Returns a dict describing the security model in use.

    Returns:
        Security status dictionary
    """
    tenant_id = g.get("tenant_id") if has_request_context() else None

    if not tenant_id:
        return {
            "tenant_id": None,
            "security_level": "none",
            "message": "No tenant context",
        }

    if has_secure_warehouse_access(tenant_id):
        return {
            "tenant_id": tenant_id,
            "security_level": "enforced",
            "message": (
                "Per-tenant database credentials configured. "
                "PostgreSQL permissions prevent cross-tenant access."
            ),
        }
    else:
        return {
            "tenant_id": tenant_id,
            "security_level": "convenience_only",
            "message": (
                "Using shared database user with search_path. "
                "Users CAN query other tenant schemas explicitly. "
                "Configure per-tenant warehouse credentials for true isolation."
            ),
        }
