# TODO: Add license header
"""
Default configuration for multi-tenant authentication.
"""

from __future__ import annotations

from typing import Any

# Default configuration values
DEFAULT_CONFIG: dict[str, Any] = {
    # Base domain for subdomain extraction
    "MULTI_TENANT_BASE_DOMAIN": "app.example.com",
    # Redirect URL when tenant is not found
    "TENANT_NOT_FOUND_URL": "https://example.com/unknown-tenant",
    # Cache TTL for tenant lookups (seconds)
    "TENANT_CACHE_TTL": 300,
    # Public endpoints that don't require tenant context
    "MULTI_TENANT_PUBLIC_ENDPOINTS": [
        "/health",
        "/healthcheck",
        "/static/",
        "/api/v1/security/csrf_token",
    ],
}


def get_feature_flag_enabled() -> bool:
    """
    Check if multi-tenancy feature flag is enabled.

    Returns:
        True if MULTI_TENANCY_ENABLED feature flag is set
    """
    try:
        from superset.extensions import feature_flag_manager

        return feature_flag_manager.is_feature_enabled("MULTI_TENANCY_ENABLED")
    except (ImportError, RuntimeError):
        # Fallback for when not in app context
        return False


def is_multi_tenancy_enabled() -> bool:
    """
    Check if multi-tenancy is enabled.

    Checks both the feature flag and direct config.

    Returns:
        True if multi-tenancy is enabled
    """
    try:
        from flask import current_app

        # Check feature flag first
        if get_feature_flag_enabled():
            return True

        # Fallback to direct config
        return current_app.config.get("MULTI_TENANT_ENABLED", False)
    except RuntimeError:
        # Not in app context
        return False
