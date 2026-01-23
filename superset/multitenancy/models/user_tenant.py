# TODO: Add license header
"""
User-Tenant mapping model.

This provides a 1:1 mapping between Superset users and Tenants without
modifying the core Flask-AppBuilder User model directly.
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from superset.extensions import db
from superset.multitenancy.models.mixins import AuditMixinNullable


class UserTenant(db.Model, AuditMixinNullable):
    """
    1:1 Mapping between Superset users and Tenants.

    This avoids modifying the core FAB User model directly.
    We avoid a direct SQLAlchemy relationship to the User model here
    to prevent initialization order issues and metadata conflicts
    with the core Flask-AppBuilder User model.
    """

    __tablename__ = "user_tenants"

    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(
        Integer,
        ForeignKey(
            "ab_user.id",
            ondelete="CASCADE",
            use_alter=True,
            name="fk_user_tenants_user_id",
        ),
        unique=True,
        nullable=False,
    )
    tenant_id: int = Column(
        Integer,
        ForeignKey(
            "tenants.id",
            ondelete="CASCADE",
            use_alter=True,
            name="fk_user_tenants_tenant_id",
        ),
        nullable=False,
    )

    # Relationship only to Tenant (which is in our metadata)
    tenant = relationship(
        "Tenant",
        foreign_keys=[tenant_id],
        backref="user_mappings",
    )

    def __repr__(self) -> str:
        return f"<UserTenant user_id={self.user_id} tenant_id={self.tenant_id}>"
