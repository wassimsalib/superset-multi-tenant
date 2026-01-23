# TODO: Add Apache license header
"""
Admin views for tenant management.

This module provides:
- TenantModelView: Tenant configuration management (superuser only)
- register_admin_views: Function to register views with Flask-AppBuilder

FAB user/role management views are overridden in security_manager.py:
- TenantAwareUserDBModelView
- TenantAwareUserOAuthModelView
- TenantAwareRoleModelView
"""

from keycloak_multi_tenant.admin.views import register_admin_views, TenantModelView
from keycloak_multi_tenant.security_manager import (
    is_superuser,
    TenantAwareRoleModelView,
    TenantAwareUserDBModelView,
    TenantAwareUserOAuthModelView,
)

__all__ = [
    "register_admin_views",
    "TenantModelView",
    "is_superuser",
    "TenantAwareRoleModelView",
    "TenantAwareUserDBModelView",
    "TenantAwareUserOAuthModelView",
]
