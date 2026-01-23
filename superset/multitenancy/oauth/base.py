# TODO: Add license header
"""
Abstract base class for OAuth provider configuration.

This module defines the interface that all OAuth providers must implement
for multi-tenant authentication.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

from flask import Flask, current_app

if TYPE_CHECKING:
    from superset.multitenancy.models import Tenant

logger = logging.getLogger(__name__)


class OAuthProviderBase(ABC):
    """
    Abstract base class for OAuth provider configuration.

    Each implementation generates OAuth configuration for tenant-specific
    authentication, enabling complete isolation between tenants.
    """

    def __init__(self, app: Optional[Flask] = None) -> None:
        self._app = app

    def init_app(self, app: Flask) -> None:
        """Initialize with Flask app."""
        self._app = app

    @property
    def app(self) -> Flask:
        """Get the Flask app instance."""
        return self._app or current_app

    @abstractmethod
    def get_oauth_provider_config(self, tenant: Tenant) -> dict[str, Any]:
        """
        Generate OAuth provider configuration for a tenant.

        Args:
            tenant: The tenant object with OAuth configuration

        Returns:
            Dictionary with OAuth provider configuration for authlib
        """
        pass

    @abstractmethod
    def get_logout_url(self, tenant: Tenant, redirect_uri: str) -> str:
        """
        Generate logout URL for a tenant.

        Args:
            tenant: The tenant object
            redirect_uri: URL to redirect after logout

        Returns:
            Full logout URL
        """
        pass

    def get_provider_name(self, tenant: Tenant) -> str:
        """
        Get unique provider name for tenant.

        Args:
            tenant: The tenant object

        Returns:
            Unique provider name (e.g., "keycloak_acme")
        """
        return f"oauth_{tenant.slug}"

    def get_scopes(self, tenant: Tenant) -> str:
        """
        Get OAuth scopes for tenant.

        Args:
            tenant: The tenant object

        Returns:
            Space-separated scope string
        """
        if tenant.scopes:
            return tenant.scopes.replace(",", " ")
        return "openid email profile"
