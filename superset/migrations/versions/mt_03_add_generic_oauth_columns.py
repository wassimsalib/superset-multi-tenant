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
"""Add generic OAuth columns and multi-tenant improvements

Revision ID: mt_add_generic_oauth
Revises: mt_add_tenant_id
Create Date: 2026-01-23 10:00:00.000000

Changes:
- Add slug column (subdomain identifier, replaces tenant_id for new code)
- Add uuid column for external API exposure
- Add is_admin_tenant for platform admin privileges
- Add generic OAuth columns (oauth_issuer, client_id, client_secret, scopes)
- Add default_schema and db_sqlalchemy_uri for database isolation
- Rename audit columns (created_at -> created_on, updated_at -> changed_on)
- Add audit foreign key columns (created_by_fk, changed_by_fk)
- Make legacy Keycloak-specific columns nullable (keycloak_realm, etc.)
"""

import sqlalchemy as sa
from alembic import op
from uuid import uuid4

# revision identifiers, used by Alembic.
revision = "mt_add_generic_oauth"
down_revision = "mt_add_tenant_id"
branch_labels = None
depends_on = None


def upgrade():
    """Align tenants table with CTO architecture."""

    # Add uuid column
    op.add_column(
        "tenants",
        sa.Column("uuid", sa.String(36), nullable=True),
    )

    # Add is_admin_tenant column
    op.add_column(
        "tenants",
        sa.Column("is_admin_tenant", sa.Boolean(), default=False, nullable=True),
    )

    # Add generic OAuth columns
    op.add_column(
        "tenants",
        sa.Column("oauth_issuer", sa.String(512), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("client_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("client_secret", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("scopes", sa.Text(), nullable=True),
    )

    # Add default_schema column
    op.add_column(
        "tenants",
        sa.Column("default_schema", sa.String(255), nullable=True),
    )

    # Add db_sqlalchemy_uri column for per-tenant database connections
    op.add_column(
        "tenants",
        sa.Column("db_sqlalchemy_uri", sa.Text(), nullable=True),
    )

    # Rename audit columns to match Superset's AuditMixinNullable
    op.alter_column("tenants", "created_at", new_column_name="created_on")
    op.alter_column("tenants", "updated_at", new_column_name="changed_on")

    # Add audit foreign key columns (nullable, for user tracking)
    op.add_column(
        "tenants",
        sa.Column("created_by_fk", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("changed_by_fk", sa.Integer(), nullable=True),
    )

    # Add slug column (will be populated from tenant_id)
    op.add_column(
        "tenants",
        sa.Column("slug", sa.String(255), nullable=True),
    )

    # Migrate data: copy tenant_id to slug, build oauth_issuer from keycloak_realm
    op.execute("""
        UPDATE tenants
        SET slug = tenant_id,
            uuid = gen_random_uuid()::text,
            is_admin_tenant = false,
            oauth_issuer = 'http://host.docker.internal:8180/realms/' || keycloak_realm,
            client_id = keycloak_client_id,
            client_secret = keycloak_client_secret
        WHERE slug IS NULL
    """)

    # Make slug not nullable and add unique constraint
    op.alter_column("tenants", "slug", nullable=False)
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    # Make uuid not nullable and add unique constraint
    op.alter_column("tenants", "uuid", nullable=False)
    op.create_index("ix_tenants_uuid", "tenants", ["uuid"], unique=True)

    # Make is_admin_tenant not nullable
    op.alter_column("tenants", "is_admin_tenant", nullable=False, server_default="false")

    # Make oauth_issuer not nullable (populated from keycloak_realm)
    op.alter_column("tenants", "oauth_issuer", nullable=False)

    # Make legacy columns nullable (we now use slug, oauth_issuer, client_id, client_secret)
    op.alter_column("tenants", "tenant_id", nullable=True)
    op.alter_column("tenants", "subdomain", nullable=True)
    op.alter_column("tenants", "keycloak_realm", nullable=True)
    op.alter_column("tenants", "keycloak_client_id", nullable=True)
    op.alter_column("tenants", "keycloak_client_secret", nullable=True)

    # Note: We keep tenant_id and subdomain columns for backward compatibility
    # They can be removed in a future migration once all code is updated


def downgrade():
    """Revert CTO alignment changes."""
    # Restore NOT NULL on legacy columns
    op.alter_column("tenants", "tenant_id", nullable=False)
    op.alter_column("tenants", "subdomain", nullable=False)
    op.alter_column("tenants", "keycloak_realm", nullable=False)
    op.alter_column("tenants", "keycloak_client_id", nullable=False)
    op.alter_column("tenants", "keycloak_client_secret", nullable=False)

    # Drop new indexes
    op.drop_index("ix_tenants_uuid", table_name="tenants")
    op.drop_index("ix_tenants_slug", table_name="tenants")

    # Drop new columns
    op.drop_column("tenants", "slug")
    op.drop_column("tenants", "default_schema")
    op.drop_column("tenants", "db_sqlalchemy_uri")
    op.drop_column("tenants", "scopes")
    op.drop_column("tenants", "client_secret")
    op.drop_column("tenants", "client_id")
    op.drop_column("tenants", "oauth_issuer")
    op.drop_column("tenants", "is_admin_tenant")
    op.drop_column("tenants", "uuid")
    op.drop_column("tenants", "created_by_fk")
    op.drop_column("tenants", "changed_by_fk")

    # Rename audit columns back to original names
    op.alter_column("tenants", "created_on", new_column_name="created_at")
    op.alter_column("tenants", "changed_on", new_column_name="updated_at")
