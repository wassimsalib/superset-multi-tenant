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
Multi-tenant Keycloak authentication extension for Apache Superset.

This package provides realm-based multi-tenancy with subdomain routing,
per-tenant Keycloak client credentials, and full data isolation.
"""

from keycloak_multi_tenant.security_manager import KeycloakMultiTenantSecurityManager
from keycloak_multi_tenant.models import Tenant
from keycloak_multi_tenant.tenant_resolver import TenantResolver
from keycloak_multi_tenant.keycloak_client import KeycloakMultiTenantClient
from keycloak_multi_tenant.db_isolation import (
    init_db_isolation,
    get_tenant_schema,
    TenantSchemaManager,
    TenantAwareDatabaseConfig,
    create_tenant_database_uri,
    get_secure_tenant_engine,
    execute_secure_query,
    has_secure_warehouse_access,
    get_warehouse_security_status,
)
from keycloak_multi_tenant.tenant_database import (
    TenantDatabaseManager,
    TenantUserManager,
    get_tenant_db_manager,
    get_current_tenant_engine,
    get_tenant_sqla_uri,
)

__all__ = [
    # Core components
    "KeycloakMultiTenantSecurityManager",
    "Tenant",
    "TenantResolver",
    "KeycloakMultiTenantClient",
    # Database isolation (convenience model)
    "init_db_isolation",
    "get_tenant_schema",
    "TenantSchemaManager",
    "TenantAwareDatabaseConfig",
    "create_tenant_database_uri",
    # Secure database access (per-tenant credentials)
    "TenantDatabaseManager",
    "TenantUserManager",
    "get_tenant_db_manager",
    "get_current_tenant_engine",
    "get_tenant_sqla_uri",
    "get_secure_tenant_engine",
    "execute_secure_query",
    "has_secure_warehouse_access",
    "get_warehouse_security_status",
]

__version__ = "1.0.0"
