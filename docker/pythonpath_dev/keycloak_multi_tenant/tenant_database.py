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

import logging
from typing import Optional
from urllib.parse import urlparse, urlunparse

from flask import current_app, g
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError, OperationalError
from sqlalchemy.pool import QueuePool

from .db_isolation import get_tenant_schema

logger = logging.getLogger(__name__)


class TenantDatabaseManager:
    """
    Manages per-tenant database connections with proper security isolation.

    Uses tenant-specific credentials to create database connections that
    are restricted to only the tenant's schema.
    """

    def __init__(self):
        """Initialize the tenant database manager."""
        # Cache of engines per tenant for connection pooling
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
            tenant_id: Tenant identifier
            base_uri: Base database URI (defaults to WAREHOUSE_DATABASE_URI)

        Returns:
            SQLAlchemy Engine with tenant credentials, or None if not configured
        """
        # Check cache first
        if tenant_id in self._tenant_engines:
            engine = self._tenant_engines[tenant_id]
            # Verify engine is still valid
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return engine
            except (OperationalError, DatabaseError):
                # Engine is stale, remove from cache
                del self._tenant_engines[tenant_id]

        # Get tenant from database
        from .models import Tenant

        tenant = Tenant.query.filter_by(tenant_id=tenant_id, is_active=True).first()
        if not tenant:
            logger.warning(f"Tenant not found: {tenant_id}")
            return None

        # Check if tenant has warehouse credentials
        if not tenant.has_warehouse_credentials():
            logger.warning(
                f"Tenant {tenant_id} does not have warehouse credentials configured. "
                "Falling back to shared connection (NOT SECURE)."
            )
            return None

        # Build connection URI with tenant credentials
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

        # Create engine with connection pooling
        try:
            schema = get_tenant_schema(tenant_id)
            engine = create_engine(
                tenant_uri,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                connect_args={
                    "options": f"-csearch_path={schema},public"
                },
            )

            # Verify connection works
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            # Cache for reuse
            self._tenant_engines[tenant_id] = engine
            logger.info(f"Created tenant engine for {tenant_id}")
            return engine

        except Exception as e:
            logger.error(f"Failed to create tenant engine for {tenant_id}: {e}")
            return None

    def _get_warehouse_base_uri(self) -> str:
        """Get the base warehouse database URI from config."""
        # Use WAREHOUSE_DATABASE_URI if set, otherwise fall back to examples URI
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

            # Replace username and password
            # netloc format: user:pass@host:port
            netloc = f"{username}:{password}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"

            # Reconstruct URI
            tenant_uri = urlunparse((
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            ))

            return tenant_uri

        except Exception as e:
            logger.error(f"Failed to build tenant URI: {e}")
            return None

    def execute_query(
        self,
        tenant_id: str,
        sql: str,
        params: Optional[dict] = None,
    ):
        """
        Execute a query using tenant-specific credentials.

        This is the secure way to run queries against the data warehouse.

        Args:
            tenant_id: Tenant identifier
            sql: SQL query to execute
            params: Optional query parameters

        Returns:
            Query result or raises exception

        Raises:
            PermissionError: If tenant doesn't have warehouse credentials
            Exception: If query fails
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
            tenant_id: Tenant identifier
        """
        if tenant_id in self._tenant_engines:
            try:
                self._tenant_engines[tenant_id].dispose()
            except Exception as e:
                logger.warning(f"Error disposing tenant engine: {e}")
            finally:
                del self._tenant_engines[tenant_id]
                logger.info(f"Closed tenant engine for {tenant_id}")

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
    tenant_id = g.get("tenant_id")
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
    tenant_id = g.get("tenant_id")
    if not tenant_id:
        return None

    from .models import Tenant

    tenant = Tenant.query.filter_by(tenant_id=tenant_id, is_active=True).first()
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

    def __init__(self, admin_engine: Engine):
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
            tenant_id: Tenant identifier
            password: Password for the new user
            schema: Schema name (defaults to tenant_{tenant_id})

        Returns:
            The created username
        """
        username = f"tenant_{tenant_id}_user"
        schema = schema or get_tenant_schema(tenant_id)

        with self.engine.connect() as conn:
            # Create user
            conn.execute(text(
                f"CREATE USER {username} WITH PASSWORD :password"
            ), {"password": password})

            # Revoke all default privileges
            conn.execute(text(
                f"REVOKE ALL ON SCHEMA public FROM {username}"
            ))

            # Grant CONNECT to database
            db_name = self.engine.url.database
            conn.execute(text(
                f"GRANT CONNECT ON DATABASE {db_name} TO {username}"
            ))

            # Grant access only to tenant's schema
            conn.execute(text(
                f"GRANT USAGE ON SCHEMA {schema} TO {username}"
            ))
            conn.execute(text(
                f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {username}"
            ))

            # Ensure future tables in schema are also accessible
            conn.execute(text(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} "
                f"GRANT SELECT ON TABLES TO {username}"
            ))

            conn.commit()

        logger.info(f"Created tenant user {username} with access to {schema}")
        return username

    def drop_tenant_user(self, tenant_id: str) -> None:
        """
        Drop a tenant's PostgreSQL user.

        Args:
            tenant_id: Tenant identifier
        """
        username = f"tenant_{tenant_id}_user"

        with self.engine.connect() as conn:
            # Revoke privileges first
            conn.execute(text(f"DROP OWNED BY {username}"))
            # Drop user
            conn.execute(text(f"DROP USER IF EXISTS {username}"))
            conn.commit()

        logger.info(f"Dropped tenant user {username}")

    def update_user_password(self, tenant_id: str, new_password: str) -> None:
        """
        Update a tenant user's password.

        Args:
            tenant_id: Tenant identifier
            new_password: New password
        """
        username = f"tenant_{tenant_id}_user"

        with self.engine.connect() as conn:
            conn.execute(text(
                f"ALTER USER {username} WITH PASSWORD :password"
            ), {"password": new_password})
            conn.commit()

        logger.info(f"Updated password for {username}")

    def verify_user_isolation(self, tenant_id: str, other_schema: str) -> bool:
        """
        Verify that a tenant user cannot access another schema.

        Args:
            tenant_id: Tenant identifier
            other_schema: Schema that should NOT be accessible

        Returns:
            True if isolation is working (access denied)
        """
        from .models import Tenant

        tenant = Tenant.query.filter_by(tenant_id=tenant_id).first()
        if not tenant or not tenant.has_warehouse_credentials():
            logger.warning(f"Cannot verify isolation: tenant {tenant_id} not configured")
            return False

        manager = get_tenant_db_manager()
        engine = manager.get_tenant_engine(tenant_id)

        if not engine:
            return False

        try:
            with engine.connect() as conn:
                # Try to access another tenant's schema - this should fail
                conn.execute(text(
                    f"SELECT 1 FROM {other_schema}.any_table LIMIT 1"
                ))
            # If we get here, isolation is broken
            logger.error(
                f"SECURITY VIOLATION: {tenant_id} can access {other_schema}!"
            )
            return False

        except Exception as e:
            # Permission denied = isolation working
            if "permission denied" in str(e).lower():
                logger.info(f"Isolation verified: {tenant_id} cannot access {other_schema}")
                return True
            # Other error - unclear
            logger.warning(f"Isolation check inconclusive: {e}")
            return False

    def generate_setup_sql(self, tenant_id: str, password: str) -> str:
        """
        Generate SQL commands for setting up a tenant user.

        Use this to generate scripts for manual execution by DBAs.

        Args:
            tenant_id: Tenant identifier
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
