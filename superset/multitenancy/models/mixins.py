# TODO: Add license header
"""
Shared mixins for multi-tenancy models.

These are standalone versions that don't depend on superset.models.helpers
to avoid circular import issues during app initialization.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.ext.declarative import declared_attr


class AuditMixinNullable:
    """
    Audit mixin for tracking creation and modification timestamps.

    This is a standalone version that doesn't depend on superset.models.helpers
    to avoid circular import issues during app initialization.
    """

    @declared_attr
    def created_on(cls) -> Column:
        return Column(DateTime, default=datetime.utcnow, nullable=True)

    @declared_attr
    def changed_on(cls) -> Column:
        return Column(
            DateTime,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=True,
        )

    @declared_attr
    def created_by_fk(cls) -> Column:
        return Column(Integer, nullable=True)

    @declared_attr
    def changed_by_fk(cls) -> Column:
        return Column(Integer, nullable=True)
