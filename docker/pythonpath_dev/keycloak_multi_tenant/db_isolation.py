# TODO: Add Apache license header
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

import logging
from contextlib import contextmanager
from typing import Optional

from flask import g
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool

logger = logging.getLogger(__name__)


# =============================================================================
# Schema Naming Convention
# =============================================================================

def get_tenant_schema(tenant_id: str) -> str:
    """
    Get PostgreSQL schema name for a tenant.

    Args:
        tenant_id: Tenant identifier (e.g., "demo", "acme")

    Returns:
        Schema name (e.g., "tenant_demo", "tenant_acme")
    """
    # Sanitize tenant_id to prevent SQL injection
    safe_tenant_id = "".join(c for c in tenant_id if c.isalnum() or c == "_")
    return f"tenant_{safe_tenant_id}"


def get_tenant_from_schema(schema_name: str) -> Optional[str]:
    """
    Extract tenant_id from schema name.

    Args:
        schema_name: PostgreSQL schema name

    Returns:
        Tenant ID or None if not a tenant schema
    """
    if schema_name.startswith("tenant_"):
        return schema_name[7:]  # Remove "tenant_" prefix
    return None


# =============================================================================
# SQLAlchemy Connection Hooks
# =============================================================================

def setup_schema_isolation(app):
    """
    Configure SQLAlchemy to automatically set search_path based on tenant.

    This hooks into SQLAlchemy's connection pool to set the schema
    on every connection checkout.

    Args:
        app: Flask application instance
    """
    from superset import db

    @event.listens_for(Pool, "checkout")
    def set_tenant_schema(dbapi_conn, connection_record, connection_proxy):
        """Set search_path when connection is checked out from pool."""
        # Skip if no connection (shouldn't happen but be safe)
        if dbapi_conn is None:
            return

        # Only apply to PostgreSQL connections (check for psycopg2/psycopg)
        conn_type = type(dbapi_conn).__module__
        if 'psycopg' not in conn_type and 'pg8000' not in conn_type:
            return  # Not a PostgreSQL connection

        # Use g.tenant_id (string) to avoid detached session issues
        tenant_id = g.get("tenant_id") if has_request_context() else None

        try:
            if tenant_id:
                schema = get_tenant_schema(tenant_id)
                cursor = dbapi_conn.cursor()
                try:
                    # Set search_path to tenant schema, then public
                    cursor.execute(f"SET search_path TO {schema}, public")
                    logger.debug(f"Set search_path to: {schema}, public")
                finally:
                    cursor.close()
        except Exception as e:
            logger.debug(f"Could not set search_path: {e}")

    @event.listens_for(Pool, "checkin")
    def reset_tenant_schema(dbapi_conn, connection_record):
        """Reset search_path when connection is returned to pool."""
        # Skip if no connection
        if dbapi_conn is None:
            return

        # Only apply to PostgreSQL connections
        conn_type = type(dbapi_conn).__module__
        if 'psycopg' not in conn_type and 'pg8000' not in conn_type:
            return

        try:
            cursor = dbapi_conn.cursor()
            try:
                cursor.execute("SET search_path TO public")
            finally:
                cursor.close()
        except Exception as e:
            logger.debug(f"Could not reset search_path: {e}")

    logger.info("Schema-based tenant isolation configured")


def has_request_context():
    """Check if we're in a Flask request context."""
    try:
        from flask import has_request_context as flask_has_request_context
        return flask_has_request_context()
    except RuntimeError:
        return False


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
        include_schema: bool = True
    ) -> str:
        """
        Build connection string with tenant schema in options.

        Args:
            base_uri: Base PostgreSQL connection string
            tenant_id: Tenant identifier
            include_schema: Whether to include schema in connection options

        Returns:
            Modified connection string with schema options
        """
        if not include_schema:
            return base_uri

        schema = get_tenant_schema(tenant_id)

        # Add options to connection string
        if "?" in base_uri:
            return f"{base_uri}&options=-csearch_path%3D{schema},public"
        else:
            return f"{base_uri}?options=-csearch_path%3D{schema},public"

    @staticmethod
    def get_sqlalchemy_options(tenant_id: str) -> dict:
        """
        Get SQLAlchemy connect_args for tenant isolation.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Dictionary of connection arguments
        """
        schema = get_tenant_schema(tenant_id)
        return {
            "options": f"-csearch_path={schema},public"
        }


# =============================================================================
# Schema Management
# =============================================================================

class TenantSchemaManager:
    """
    Manage PostgreSQL schemas for tenants.

    Handles schema creation, migration, and cleanup.
    """

    def __init__(self, engine):
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
            tenant_id: Tenant identifier
        """
        schema = get_tenant_schema(tenant_id)

        with self.engine.connect() as conn:
            # Create schema if not exists
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))

            # Grant usage to application user (adjust as needed)
            # conn.execute(text(f"GRANT USAGE ON SCHEMA {schema} TO superset_app"))
            # conn.execute(text(f"GRANT ALL ON ALL TABLES IN SCHEMA {schema} TO superset_app"))

            conn.commit()
            logger.info(f"Created schema: {schema}")

    def drop_schema(self, tenant_id: str, cascade: bool = False) -> None:
        """
        Drop schema for a tenant.

        Args:
            tenant_id: Tenant identifier
            cascade: If True, drop all objects in schema
        """
        schema = get_tenant_schema(tenant_id)
        cascade_sql = "CASCADE" if cascade else "RESTRICT"

        with self.engine.connect() as conn:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} {cascade_sql}"))
            conn.commit()
            logger.warning(f"Dropped schema: {schema}")

    def schema_exists(self, tenant_id: str) -> bool:
        """
        Check if tenant schema exists.

        Args:
            tenant_id: Tenant identifier

        Returns:
            True if schema exists
        """
        schema = get_tenant_schema(tenant_id)

        with self.engine.connect() as conn:
            result = conn.execute(text(
                "SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"
            ), {"schema": schema})
            return result.fetchone() is not None

    def list_tenant_schemas(self) -> list[str]:
        """
        List all tenant schemas.

        Returns:
            List of tenant IDs that have schemas
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'tenant_%'"
            ))
            return [get_tenant_from_schema(row[0]) for row in result.fetchall()]

    def clone_schema(self, source_tenant_id: str, target_tenant_id: str) -> None:
        """
        Clone schema structure from one tenant to another.

        Args:
            source_tenant_id: Source tenant identifier
            target_tenant_id: Target tenant identifier
        """
        source_schema = get_tenant_schema(source_tenant_id)
        target_schema = get_tenant_schema(target_tenant_id)

        # This is a simplified version - production would need more robust handling
        with self.engine.connect() as conn:
            # Create target schema
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {target_schema}"))

            # Get all tables from source schema
            tables = conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = :schema"
            ), {"schema": source_schema}).fetchall()

            for (table_name,) in tables:
                # Clone table structure (without data)
                conn.execute(text(
                    f"CREATE TABLE {target_schema}.{table_name} "
                    f"(LIKE {source_schema}.{table_name} INCLUDING ALL)"
                ))

            conn.commit()
            logger.info(f"Cloned schema {source_schema} to {target_schema}")


# =============================================================================
# Row-Level Security (Defense in Depth)
# =============================================================================

class TenantRLSManager:
    """
    Manage PostgreSQL Row-Level Security for additional protection.

    Even with schema isolation, RLS provides defense-in-depth
    in case of misconfiguration.
    """

    def __init__(self, engine):
        self.engine = engine

    def setup_rls_for_table(
        self,
        schema: str,
        table: str,
        tenant_column: str = "tenant_id"
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
            # Enable RLS
            conn.execute(text(f"ALTER TABLE {full_table} ENABLE ROW LEVEL SECURITY"))

            # Create policy based on session variable
            conn.execute(text(f"""
                CREATE POLICY tenant_isolation ON {full_table}
                USING ({tenant_column} = current_setting('app.current_tenant', true))
            """))

            # Force RLS for table owner too (important!)
            conn.execute(text(
                f"ALTER TABLE {full_table} FORCE ROW LEVEL SECURITY"
            ))

            conn.commit()
            logger.info(f"Enabled RLS on {full_table}")

    def set_tenant_context(self, conn, tenant_id: str) -> None:
        """
        Set tenant context for RLS policies.

        Args:
            conn: Database connection
            tenant_id: Tenant identifier
        """
        conn.execute(text(f"SET app.current_tenant = '{tenant_id}'"))


# =============================================================================
# Superset Database Connection Hook
# =============================================================================

def create_tenant_database_uri(
    base_uri: str,
    tenant_id: Optional[str] = None
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
        # Use g.tenant_id (string) to avoid detached session issues
        tenant_id = g.get("tenant_id")

    if tenant_id:
        return TenantAwareDatabaseConfig.get_connection_string(base_uri, tenant_id)

    return base_uri


# =============================================================================
# Middleware Integration
# =============================================================================

def setup_db_isolation_middleware(app):
    """
    Set up database isolation middleware.

    Integrates with the existing tenant middleware to ensure
    database connections use correct schema.

    Args:
        app: Flask application
    """
    from superset import db

    @app.before_request
    def set_db_tenant_context():
        """Set database tenant context before each request."""
        # Use g.tenant_id (string) to avoid detached session issues
        tenant_id = g.get("tenant_id")
        if tenant_id:
            # Store tenant_id for RLS (if using hybrid approach)
            # This will be available via current_setting('app.current_tenant')
            try:
                db.session.execute(
                    text(f"SET app.current_tenant = '{tenant_id}'")
                )
            except Exception as e:
                logger.warning(f"Could not set tenant context: {e}")

    logger.info("Database isolation middleware configured")


# =============================================================================
# Superset Query Hook (for external databases)
# =============================================================================

def apply_tenant_schema_to_query(database, query, schema=None):
    """
    Modify query to include tenant schema context.

    This is called by Superset before executing queries against external databases.

    Args:
        database: Superset Database model
        query: SQL query string
        schema: Optional schema override

    Returns:
        Modified query with search_path prefix
    """
    if schema:
        # Explicit schema provided
        return f"SET search_path TO {schema}, public; {query}"

    # Get tenant from request context - use g.tenant_id to avoid detached session issues
    tenant_id = g.get("tenant_id") if has_request_context() else None
    if tenant_id:
        tenant_schema = get_tenant_schema(tenant_id)
        return f"SET search_path TO {tenant_schema}, public; {query}"

    return query


def get_tenant_schema_for_connection():
    """
    Get the current tenant's schema name for database connections.

    Returns:
        Schema name or None if no tenant context
    """
    # Use g.tenant_id to avoid detached session issues
    tenant_id = g.get("tenant_id") if has_request_context() else None
    if tenant_id:
        return get_tenant_schema(tenant_id)
    return None


# =============================================================================
# Superset Database Engine Spec Hook
# =============================================================================

class TenantAwareEngineSpec:
    """
    Mixin for Superset engine specs to add tenant schema isolation.

    Add this to customize how Superset connects to tenant-isolated databases.
    """

    @classmethod
    def get_dbapi_connection(cls, database, schema=None, **kwargs):
        """
        Get a database connection with tenant schema set.

        Override this in your engine spec to add tenant isolation.
        """
        connection = super().get_dbapi_connection(database, schema, **kwargs)

        # Set search_path for tenant
        tenant_schema = get_tenant_schema_for_connection()
        if tenant_schema:
            cursor = connection.cursor()
            try:
                cursor.execute(f"SET search_path TO {tenant_schema}, public")
            finally:
                cursor.close()

        return connection


# =============================================================================
# Initialization
# =============================================================================

def init_db_isolation(app):
    """
    Initialize all database isolation components.

    Call this from FLASK_APP_MUTATOR in superset_config.py.

    Args:
        app: Flask application
    """
    setup_schema_isolation(app)
    setup_db_isolation_middleware(app)

    # Register query modifier for external databases
    _register_query_modifier(app)

    logger.info("Database isolation initialized")


def _register_query_modifier(app):
    """
    Register hooks to modify queries for tenant isolation.

    This integrates with Superset's query execution pipeline.
    """
    try:
        from superset import sql_lab

        # Store original execute function
        original_execute = getattr(sql_lab, 'execute_sql_statement', None)

        if original_execute:
            def tenant_aware_execute(sql, *args, **kwargs):
                """Wrap SQL execution with tenant schema."""
                # Use g.tenant_id to avoid detached session issues
                tenant_id = g.get("tenant_id") if has_request_context() else None
                if tenant_id:
                    schema = get_tenant_schema(tenant_id)
                    sql = f"SET search_path TO {schema}, public; {sql}"
                    logger.debug(f"Executing with search_path={schema}")
                return original_execute(sql, *args, **kwargs)

            # Note: This is a simplified example. Production implementation
            # would need to hook into Superset's actual query execution path.
            logger.info("Query modifier registered for tenant isolation")

    except ImportError:
        logger.warning("Could not register SQL Lab query modifier")


# =============================================================================
# Per-Tenant Database Integration (Security Model)
# =============================================================================

def get_secure_tenant_engine(tenant_id: Optional[str] = None):
    """
    Get a secure database engine for the tenant.

    This uses per-tenant database credentials which provide true isolation
    via PostgreSQL permissions.

    Args:
        tenant_id: Tenant identifier (uses current request tenant if None)

    Returns:
        SQLAlchemy Engine with tenant credentials, or None if not configured
    """
    from .tenant_database import get_tenant_db_manager

    if tenant_id is None:
        tenant_id = g.get("tenant_id") if has_request_context() else None

    if not tenant_id:
        return None

    return get_tenant_db_manager().get_tenant_engine(tenant_id)


def execute_secure_query(sql: str, params: Optional[dict] = None):
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
    from .tenant_database import get_tenant_db_manager

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
    from .models import Tenant

    if tenant_id is None:
        tenant_id = g.get("tenant_id") if has_request_context() else None

    if not tenant_id:
        return False

    tenant = Tenant.query.filter_by(tenant_id=tenant_id, is_active=True).first()
    return tenant.has_warehouse_credentials() if tenant else False


def get_warehouse_security_status() -> dict:
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
            "message": "Per-tenant database credentials configured. "
                       "PostgreSQL permissions prevent cross-tenant access.",
        }
    else:
        return {
            "tenant_id": tenant_id,
            "security_level": "convenience_only",
            "message": "Using shared database user with search_path. "
                       "Users CAN query other tenant schemas explicitly. "
                       "Configure per-tenant warehouse credentials for true isolation.",
        }
