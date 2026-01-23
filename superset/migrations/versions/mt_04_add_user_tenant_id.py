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
"""Create user_tenants mapping table

Revision ID: mt_add_user_tenant_id
Revises: mt_add_generic_oauth
Create Date: 2026-01-23 12:00:00.000000

Changes:
- Create user_tenants table for 1:1 user-tenant mapping
- This avoids modifying the core ab_user table
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "mt_add_user_tenant_id"
down_revision = "mt_add_generic_oauth"
branch_labels = None
depends_on = None


def upgrade():
    """Create user_tenants table."""
    op.create_table(
        "user_tenants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        # Audit columns
        sa.Column("created_on", sa.DateTime(), nullable=True),
        sa.Column("changed_on", sa.DateTime(), nullable=True),
        sa.Column("created_by_fk", sa.Integer(), nullable=True),
        sa.Column("changed_by_fk", sa.Integer(), nullable=True),
        
        sa.ForeignKeyConstraint(["user_id"], ["ab_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id"),
    )

    # Add index for efficient tenant-based filtering
    op.create_index(
        "ix_user_tenants_tenant_id",
        "user_tenants",
        ["tenant_id"],
    )


def downgrade():
    """Drop user_tenants table."""
    op.drop_table("user_tenants")