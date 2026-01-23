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
"""Create tenants table for multi-tenant authentication

Revision ID: mt_create_tenants
Revises: (set to latest existing revision)
Create Date: 2026-01-21 15:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "mt_create_tenants"
down_revision = "9787190b3d89"  # Latest Superset migration (add_currency_column_support)
branch_labels = None
depends_on = None


def upgrade():
    """Create the tenants table."""
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("subdomain", sa.String(255), unique=True, nullable=False),
        sa.Column("keycloak_realm", sa.String(255), nullable=False),
        sa.Column("keycloak_client_id", sa.String(255), nullable=False),
        sa.Column("keycloak_client_secret", sa.Text(), nullable=False),
        # Per-tenant data warehouse credentials
        sa.Column("warehouse_db_user", sa.String(255), nullable=True),
        sa.Column("warehouse_db_password", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("config_overrides", sa.JSON(), default=dict),
    )

    # Create indexes
    op.create_index("ix_tenants_tenant_id", "tenants", ["tenant_id"], unique=True)
    op.create_index("ix_tenants_subdomain", "tenants", ["subdomain"], unique=True)
    op.create_index("ix_tenants_is_active", "tenants", ["is_active"])


def downgrade():
    """Drop the tenants table."""
    op.drop_index("ix_tenants_is_active", table_name="tenants")
    op.drop_index("ix_tenants_subdomain", table_name="tenants")
    op.drop_index("ix_tenants_tenant_id", table_name="tenants")
    op.drop_table("tenants")
