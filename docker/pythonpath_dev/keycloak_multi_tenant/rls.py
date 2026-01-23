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
Row-Level Security (RLS) helpers for external data isolation.

Provides Jinja template context functions for filtering external
data queries by tenant.
"""

import logging
from typing import Optional

from flask import Flask, g

logger = logging.getLogger(__name__)


def get_tenant_id() -> Optional[str]:
    """
    Get the current tenant's string ID.

    Returns:
        Tenant ID string (e.g., "customer1") or None
    """
    tenant = g.get("tenant")
    return tenant.tenant_id if tenant else None


def get_tenant_db_id() -> Optional[int]:
    """
    Get the current tenant's database ID.

    Returns:
        Tenant database ID (integer) or None
    """
    tenant = g.get("tenant")
    return tenant.id if tenant else None


def tenant_filter(column: str = "tenant_id", quote_value: bool = True) -> str:
    """
    Generate a SQL filter clause for the current tenant.

    Usage in SQL Lab or chart queries:
        SELECT * FROM sales WHERE {{ tenant_filter('customer_id') }}
        -- Renders: SELECT * FROM sales WHERE customer_id = 'customer1'

    Args:
        column: Column name to filter on (default: "tenant_id")
        quote_value: Whether to quote the tenant ID (default: True)

    Returns:
        SQL filter clause string, or "1=0" if no tenant context
    """
    tenant_id = get_tenant_id()

    if not tenant_id:
        logger.warning(
            "tenant_filter called without tenant context, returning false condition"
        )
        return "1=0"  # No tenant = no data

    if quote_value:
        return f"{column} = '{tenant_id}'"
    else:
        return f"{column} = {tenant_id}"


def tenant_filter_int(column: str = "tenant_id") -> str:
    """
    Generate a SQL filter clause using tenant's database ID (integer).

    Usage:
        SELECT * FROM sales WHERE {{ tenant_filter_int('tenant_fk') }}
        -- Renders: SELECT * FROM sales WHERE tenant_fk = 42

    Args:
        column: Column name to filter on

    Returns:
        SQL filter clause string
    """
    tenant_db_id = get_tenant_db_id()

    if tenant_db_id is None:
        logger.warning(
            "tenant_filter_int called without tenant context, returning false condition"
        )
        return "1=0"

    return f"{column} = {tenant_db_id}"


def tenant_in_list(column: str, values_by_tenant: dict[str, list]) -> str:
    """
    Generate an IN clause based on tenant-specific value mappings.

    Usage:
        {{ tenant_in_list('region_code', {'customer1': ['US', 'CA'], 'customer2': ['EU']}) }}
        -- For customer1: region_code IN ('US', 'CA')

    Args:
        column: Column name
        values_by_tenant: Dict mapping tenant_id to list of allowed values

    Returns:
        SQL IN clause
    """
    tenant_id = get_tenant_id()

    if not tenant_id:
        return "1=0"

    values = values_by_tenant.get(tenant_id, [])

    if not values:
        return "1=0"

    quoted_values = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted_values})"


def tenant_value() -> str:
    """
    Return the current tenant ID as a quoted SQL value.

    Usage:
        INSERT INTO audit_log (tenant_id, ...) VALUES ({{ tenant_value() }}, ...)

    Returns:
        Quoted tenant ID string
    """
    tenant_id = get_tenant_id()
    return f"'{tenant_id}'" if tenant_id else "NULL"


def get_tenant_schema() -> Optional[str]:
    """
    Get the PostgreSQL schema name for the current tenant.

    Returns the schema name in the format "tenant_{tenant_id}".

    Usage in SQL Lab:
        SELECT * FROM {{ current_tenant_schema() }}.sales

    Returns:
        Schema name (e.g., "tenant_demo") or None
    """
    tenant_id = get_tenant_id()
    if tenant_id:
        return f"tenant_{tenant_id}"
    return None


def register_tenant_jinja_context(app: Flask) -> None:
    """
    Register tenant-aware Jinja context functions.

    These functions become available in SQL Lab and chart queries
    for dynamic tenant-based filtering.

    Args:
        app: Flask application instance
    """
    # Add to Jinja2 globals
    app.jinja_env.globals["current_tenant_id"] = get_tenant_id
    app.jinja_env.globals["current_tenant_db_id"] = get_tenant_db_id
    app.jinja_env.globals["current_tenant_schema"] = get_tenant_schema
    app.jinja_env.globals["tenant_filter"] = tenant_filter
    app.jinja_env.globals["tenant_filter_int"] = tenant_filter_int
    app.jinja_env.globals["tenant_in_list"] = tenant_in_list
    app.jinja_env.globals["tenant_value"] = tenant_value

    # Also register with Superset's Jinja context
    try:
        from superset.jinja_context import ExtraCache

        # Add to the base context processors
        superset_jinja_context = app.config.get("JINJA_CONTEXT_ADDONS", {})
        superset_jinja_context.update({
            "current_tenant_id": get_tenant_id,
            "current_tenant_db_id": get_tenant_db_id,
            "current_tenant_schema": get_tenant_schema,
            "tenant_filter": tenant_filter,
            "tenant_filter_int": tenant_filter_int,
            "tenant_in_list": tenant_in_list,
            "tenant_value": tenant_value,
        })
        app.config["JINJA_CONTEXT_ADDONS"] = superset_jinja_context

        logger.info("Registered tenant Jinja context functions")

    except ImportError:
        logger.warning(
            "Could not import superset.jinja_context, "
            "tenant functions only available in templates"
        )

    logger.info("Tenant RLS Jinja context registered")
