# TODO: Add license header
"""
Flask-AppBuilder views for multi-tenancy.
"""

from superset.multitenancy.views.admin import TenantModelView, register_admin_views

__all__ = [
    "TenantModelView",
    "register_admin_views",
]
