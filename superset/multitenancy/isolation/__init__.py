# TODO: Add license header
"""
Database isolation strategies for multi-tenancy.
"""

from superset.multitenancy.isolation.schema_isolation import (
    get_tenant_schema,
    get_tenant_from_schema,
    setup_schema_isolation,
    TenantAwareDatabaseConfig,
    TenantSchemaManager,
    TenantRLSManager,
    create_tenant_database_uri,
    get_tenant_schema_for_connection,
    init_db_isolation,
    get_secure_tenant_engine,
    execute_secure_query,
    has_secure_warehouse_access,
    get_warehouse_security_status,
)
from superset.multitenancy.isolation.tenant_database import (
    TenantDatabaseManager,
    TenantUserManager,
    get_tenant_db_manager,
    get_current_tenant_engine,
    get_tenant_sqla_uri,
)
from superset.multitenancy.isolation.metadata_isolation import (
    get_current_tenant_id,
    tenant_context,
    setup_metadata_isolation,
)

__all__ = [
    # Schema isolation
    "get_tenant_schema",
    "get_tenant_from_schema",
    "setup_schema_isolation",
    "TenantAwareDatabaseConfig",
    "TenantSchemaManager",
    "TenantRLSManager",
    "create_tenant_database_uri",
    "get_tenant_schema_for_connection",
    "init_db_isolation",
    "get_secure_tenant_engine",
    "execute_secure_query",
    "has_secure_warehouse_access",
    "get_warehouse_security_status",
    # Tenant database
    "TenantDatabaseManager",
    "TenantUserManager",
    "get_tenant_db_manager",
    "get_current_tenant_engine",
    "get_tenant_sqla_uri",
    # Metadata isolation
    "get_current_tenant_id",
    "tenant_context",
    "setup_metadata_isolation",
]
