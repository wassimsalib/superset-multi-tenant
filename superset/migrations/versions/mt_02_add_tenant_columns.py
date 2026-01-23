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
"""Add tenant_id to Superset models for multi-tenant isolation

Revision ID: mt_add_tenant_id
Revises: mt_create_tenants
Create Date: 2026-01-21 15:31:00.000000

The tenant_id column stores the tenant subdomain as a string (e.g., "acme", "demo")
for simpler metadata isolation - no FK lookup required, just filter by subdomain.

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "mt_add_tenant_id"
down_revision = "mt_create_tenants"
branch_labels = None
depends_on = None

# Tables that need tenant_id for metadata isolation
TENANT_ISOLATED_TABLES = [
    "dashboards",
    "slices",
    "tables",  # SqlaTable
    "saved_query",
    "dbs",  # Database connections
]


def upgrade():
    """Add tenant_id column to Superset models."""
    for table_name in TENANT_ISOLATED_TABLES:
        # Add tenant_id column as string (stores subdomain directly)
        # No FK - simpler design, filter by subdomain string
        op.add_column(
            table_name,
            sa.Column(
                "tenant_id",
                sa.String(64),
                nullable=True,
            ),
        )

        # Create index for efficient filtering
        op.create_index(
            f"ix_{table_name}_tenant_id",
            table_name,
            ["tenant_id"],
        )


def downgrade():
    """Remove tenant_id column from Superset models."""
    for table_name in TENANT_ISOLATED_TABLES:
        op.drop_index(f"ix_{table_name}_tenant_id", table_name=table_name)
        op.drop_column(table_name, "tenant_id")
