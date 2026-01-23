# TODO: Add license header
"""
Per-Tenant Database Connection Manager.

Provides true security isolation by using per-tenant PostgreSQL users
for data warehouse connections. Each tenant user only has access to
their own schema, enforced by PostgreSQL permissions.

Security Model:
    - Each tenant gets a dedicated PostgreSQL user (e.g., tenant_demo_user)
    - User only has USAGE on their schema (e.g., tenant_demo)
    - PostgreSQL permissions prevent cross-tenant access
    - Connection pooling per tenant for performance
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import urlparse, urlunparse

from flask import current_app, g, has_request_context
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError, OperationalError
from sqlalchemy.pool import QueuePool

from superset.multitenancy.isolation.schema_isolation import get_tenant_schema

if TYPE_CHECKING:
    from superset.multitenancy.models import Tenant

logger = logging.getLogger(__name__)


class TenantDatabaseManager:
    """
    Manages per-tenant database connections with proper security isolation.

    Uses tenant-specific credentials to create database connections that
    are restricted to only the tenant's schema.
    """

    def __init__(self) -> None:
        """Initialize the tenant database manager."""
        self._tenant_engines: dict[str, Engine] = {}

    def get_tenant_engine(
        self,
        tenant_id: str,
        base_uri: Optional[str] = None,
    ) -> Optional[Engine]:
        """
        Get a SQLAlchemy engine for the tenant with their credentials.

        The engine uses the tenant's database user which only has access
        to their schema.

        Args:
            tenant_id: Tenant identifier (slug)
            base_uri: Base database URI (defaults to WAREHOUSE_DATABASE_URI)

        Returns:
            SQLAlchemy Engine with tenant credentials, or None if not configured
        """
        # Check cache first
        if tenant_id in self._tenant_engines:
            engine = self._tenant_engines[tenant_id]
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return engine
            except (OperationalError, DatabaseError):
                del self._tenant_engines[tenant_id]

        # Get tenant from database
        from superset.multitenancy.models import Tenant

        tenant = Tenant.query.filter_by(slug=tenant_id, is_active=True).first()
        if not tenant:
            logger.warning("Tenant not found: %s", tenant_id)
            return None

        if not tenant.has_warehouse_credentials():
            logger.warning(
                "Tenant %s does not have warehouse credentials configured. "
                "Falling back to shared connection (NOT SECURE).",
                tenant_id,
            )
            return None

        creds = tenant.get_warehouse_connection_info()
        if not creds:
            return None

        tenant_uri = self._build_tenant_uri(
            base_uri or self._get_warehouse_base_uri(),
            creds["user"],
            creds["password"],
        )

        if not tenant_uri:
            return None

        try:
            schema = get_tenant_schema(tenant_id)
            engine = create_engine(
                tenant_uri,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                connect_args={"options": f"-csearch_path={schema},public"},
            )

            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            self._tenant_engines[tenant_id] = engine
            logger.info("Created tenant engine for %s", tenant_id)
            return engine

        except Exception as e:
            logger.error("Failed to create tenant engine for %s: %s", tenant_id, e)
            return None

    def _get_warehouse_base_uri(self) -> str:
        """Get the base warehouse database URI from config."""
        return current_app.config.get(
            "WAREHOUSE_DATABASE_URI",
            current_app.config.get("SQLALCHEMY_EXAMPLES_URI", ""),
        )

    def _build_tenant_uri(
        self,
        base_uri: str,
        username: str,
        password: str,
    ) -> Optional[str]:
        """
        Build a connection URI with tenant-specific credentials.

        Args:
            base_uri: Base PostgreSQL connection URI
            username: Tenant's database username
            password: Tenant's database password

        Returns:
            Modified URI with tenant credentials
        """
        if not base_uri:
            return None

        try:
            parsed = urlparse(base_uri)

            netloc = f"{username}:{password}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"

            tenant_uri = urlunparse(
                (
                    parsed.scheme,
                    netloc,
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment,
                )
            )

            return tenant_uri

        except Exception as e:
            logger.error("Failed to build tenant URI: %s", e)
            return None

    def execute_query(
        self,
        tenant_id: str,
        sql: str,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Execute a query using tenant-specific credentials.

        This is the secure way to run queries against the data warehouse.

        Args:
            tenant_id: Tenant identifier (slug)
            sql: SQL query to execute
            params: Optional query parameters

        Returns:
            Query result or raises exception

        Raises:
            PermissionError: If tenant doesn't have warehouse credentials
        """
        engine = self.get_tenant_engine(tenant_id)

        if not engine:
            raise PermissionError(
                f"Tenant {tenant_id} does not have secure warehouse access configured. "
                "Contact your administrator to set up per-tenant database credentials."
            )

        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            return result

    def close_tenant_engine(self, tenant_id: str) -> None:
        """
        Close and remove a tenant's cached engine.

        Call this when tenant credentials are updated.

        Args:
            tenant_id: Tenant identifier (slug)
        """
        if tenant_id in self._tenant_engines:
            try:
                self._tenant_engines[tenant_id].dispose()
            except Exception as e:
                logger.warning("Error disposing tenant engine: %s", e)
            finally:
                del self._tenant_engines[tenant_id]
                logger.info("Closed tenant engine for %s", tenant_id)

    def close_all(self) -> None:
        """Close all cached tenant engines."""
        for tenant_id in list(self._tenant_engines.keys()):
            self.close_tenant_engine(tenant_id)


# Global instance
_tenant_db_manager: Optional[TenantDatabaseManager] = None


def get_tenant_db_manager() -> TenantDatabaseManager:
    """Get the global TenantDatabaseManager instance."""
    global _tenant_db_manager
    if _tenant_db_manager is None:
        _tenant_db_manager = TenantDatabaseManager()
    return _tenant_db_manager


def get_current_tenant_engine() -> Optional[Engine]:
    """
    Get the database engine for the current request's tenant.

    Returns:
        SQLAlchemy Engine for the current tenant, or None
    """
    tenant_id = g.get("tenant_id") if has_request_context() else None
    if not tenant_id:
        return None
    return get_tenant_db_manager().get_tenant_engine(tenant_id)


# =============================================================================
# Superset SQL Lab Integration Hook
# =============================================================================


def get_tenant_sqla_uri() -> Optional[str]:
    """
    Get the SQLAlchemy URI for the current tenant.

    This can be used to dynamically set the database URI for SQL Lab
    queries to use tenant-specific credentials.

    Returns:
        Connection URI with tenant credentials, or None
    """
    from superset.multitenancy.models import Tenant

    tenant_id = g.get("tenant_id") if has_request_context() else None
    if not tenant_id:
        return None

    tenant = Tenant.query.filter_by(slug=tenant_id, is_active=True).first()
    if not tenant or not tenant.has_warehouse_credentials():
        return None

    creds = tenant.get_warehouse_connection_info()
    if not creds:
        return None

    manager = get_tenant_db_manager()
    base_uri = manager._get_warehouse_base_uri()
    return manager._build_tenant_uri(base_uri, creds["user"], creds["password"])


# =============================================================================
# PostgreSQL User Setup Utilities
# =============================================================================


class TenantUserManager:
    """
    Utilities for managing per-tenant PostgreSQL users.

    Use these to create and configure tenant database users with
    appropriate permissions.
    """

    def __init__(self, admin_engine: Engine) -> None:
        """
        Initialize with an admin database connection.

        Args:
            admin_engine: SQLAlchemy engine with superuser/admin privileges
        """
        self.engine = admin_engine

    def create_tenant_user(
        self,
        tenant_id: str,
        password: str,
        schema: Optional[str] = None,
    ) -> str:
        """
        Create a PostgreSQL user for a tenant with schema-restricted access.

        Args:
            tenant_id: Tenant identifier (slug)
            password: Password for the new user
            schema: Schema name (defaults to tenant_{tenant_id})

        Returns:
            The created username
        """
        username = f"tenant_{tenant_id}_user"
        schema = schema or get_tenant_schema(tenant_id)

        with self.engine.connect() as conn:
            conn.execute(
                text(f"CREATE USER {username} WITH PASSWORD :password"),
                {"password": password},
            )

            conn.execute(text(f"REVOKE ALL ON SCHEMA public FROM {username}"))

            db_name = self.engine.url.database
            conn.execute(text(f"GRANT CONNECT ON DATABASE {db_name} TO {username}"))

            conn.execute(text(f"GRANT USAGE ON SCHEMA {schema} TO {username}"))
            conn.execute(
                text(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {username}")
            )

            conn.execute(
                text(
                    f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} "
                    f"GRANT SELECT ON TABLES TO {username}"
                )
            )

            conn.commit()

        logger.info("Created tenant user %s with access to %s", username, schema)
        return username

    def drop_tenant_user(self, tenant_id: str) -> None:
        """
        Drop a tenant's PostgreSQL user.

        Args:
            tenant_id: Tenant identifier (slug)
        """
        username = f"tenant_{tenant_id}_user"

        with self.engine.connect() as conn:
            conn.execute(text(f"DROP OWNED BY {username}"))
            conn.execute(text(f"DROP USER IF EXISTS {username}"))
            conn.commit()

        logger.info("Dropped tenant user %s", username)

    def update_user_password(self, tenant_id: str, new_password: str) -> None:
        """
        Update a tenant user's password.

        Args:
            tenant_id: Tenant identifier (slug)
            new_password: New password
        """
        username = f"tenant_{tenant_id}_user"

        with self.engine.connect() as conn:
            conn.execute(
                text(f"ALTER USER {username} WITH PASSWORD :password"),
                {"password": new_password},
            )
            conn.commit()

        logger.info("Updated password for %s", username)

    def verify_user_isolation(self, tenant_id: str, other_schema: str) -> bool:
        """
        Verify that a tenant user cannot access another schema.

        Args:
            tenant_id: Tenant identifier (slug)
            other_schema: Schema that should NOT be accessible

        Returns:
            True if isolation is working (access denied)
        """
        from superset.multitenancy.models import Tenant

        tenant = Tenant.query.filter_by(slug=tenant_id).first()
        if not tenant or not tenant.has_warehouse_credentials():
            logger.warning(
                "Cannot verify isolation: tenant %s not configured", tenant_id
            )
            return False

        manager = get_tenant_db_manager()
        engine = manager.get_tenant_engine(tenant_id)

        if not engine:
            return False

        try:
            with engine.connect() as conn:
                conn.execute(
                    text(f"SELECT 1 FROM {other_schema}.any_table LIMIT 1")
                )
            logger.error(
                "SECURITY VIOLATION: %s can access %s!", tenant_id, other_schema
            )
            return False

        except Exception as e:
            if "permission denied" in str(e).lower():
                logger.info(
                    "Isolation verified: %s cannot access %s", tenant_id, other_schema
                )
                return True
            logger.warning("Isolation check inconclusive: %s", e)
            return False

    def generate_setup_sql(self, tenant_id: str, password: str) -> str:
        """
        Generate SQL commands for setting up a tenant user.

        Use this to generate scripts for manual execution by DBAs.

        Args:
            tenant_id: Tenant identifier (slug)
            password: Password for the user

        Returns:
            SQL script as string
        """
        username = f"tenant_{tenant_id}_user"
        schema = get_tenant_schema(tenant_id)

        return f"""-- Per-Tenant User Setup for: {tenant_id}
-- Run this with a PostgreSQL superuser

-- 1. Create the tenant user
CREATE USER {username} WITH PASSWORD '{password}';

-- 2. Revoke default public schema access
REVOKE ALL ON SCHEMA public FROM {username};

-- 3. Grant CONNECT to the database (replace YOUR_DATABASE)
-- GRANT CONNECT ON DATABASE your_database TO {username};

-- 4. Create tenant schema if not exists
CREATE SCHEMA IF NOT EXISTS {schema};

-- 5. Grant schema access ONLY to tenant's schema
GRANT USAGE ON SCHEMA {schema} TO {username};
GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {username};

-- 6. Ensure future tables are also accessible
ALTER DEFAULT PRIVILEGES IN SCHEMA {schema}
GRANT SELECT ON TABLES TO {username};

-- 7. Verify isolation (should fail with "permission denied")
-- SET ROLE {username};
-- SELECT * FROM public.some_table;  -- Should fail
-- SELECT * FROM tenant_other.sales;  -- Should fail
-- SELECT * FROM {schema}.sales;      -- Should work
-- RESET ROLE;
"""
