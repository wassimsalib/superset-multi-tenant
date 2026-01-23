# TODO: Add license header
"""
Keycloak-specific OAuth provider implementation.

This module provides Keycloak realm-based OAuth configuration for multi-tenant
deployments.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import quote

from flask import Flask

from superset.multitenancy.oauth.base import OAuthProviderBase

if TYPE_CHECKING:
    from superset.multitenancy.models import Tenant

logger = logging.getLogger(__name__)


class KeycloakOAuthProvider(OAuthProviderBase):
    """
    Generates OAuth provider configuration for Keycloak realms.

    Each tenant has its own Keycloak realm with dedicated client credentials,
    enabling complete authentication isolation between tenants.
    """

    def __init__(self, app: Optional[Flask] = None) -> None:
        super().__init__(app)

    def get_provider_name(self, tenant: Tenant) -> str:
        """Get Keycloak-specific provider name."""
        return f"keycloak_{tenant.slug}"

    def get_oauth_provider_config(self, tenant: Tenant) -> dict[str, Any]:
        """
        Generate OAuth provider configuration for a tenant's Keycloak realm.

        Args:
            tenant: The tenant object with Keycloak configuration

        Returns:
            Dictionary with OAuth provider configuration for authlib
        """
        base_url = self._get_keycloak_base_url(tenant)
        realm = self._get_realm(tenant)
        provider_name = self.get_provider_name(tenant)

        config = {
            "name": provider_name,
            "icon": "fa-key",
            "token_key": "access_token",
            "remote_app": {
                "client_id": tenant.client_id,
                "client_secret": tenant.get_decrypted_secret(),
                "server_metadata_url": self._build_oidc_metadata_url(base_url, realm),
                "api_base_url": self._build_api_base_url(base_url, realm),
                "client_kwargs": {
                    "scope": self.get_scopes(tenant),
                },
            },
        }

        logger.debug(
            "Generated Keycloak OAuth config for tenant %s, realm %s",
            tenant.slug,
            realm,
        )

        return config

    def get_logout_url(self, tenant: Tenant, redirect_uri: str) -> str:
        """
        Generate Keycloak logout URL for single sign-out.

        Args:
            tenant: The tenant object
            redirect_uri: URL to redirect after logout

        Returns:
            Full logout URL
        """
        base_url = self._get_keycloak_base_url(tenant)
        realm = self._get_realm(tenant)

        return (
            f"{base_url}/realms/{realm}"
            f"/protocol/openid-connect/logout"
            f"?post_logout_redirect_uri={quote(redirect_uri)}"
            f"&client_id={tenant.client_id}"
        )

    def _get_keycloak_base_url(self, tenant: Tenant) -> str:
        """
        Get Keycloak base URL.

        If tenant has oauth_issuer, extract base URL from it.
        Otherwise, use config KEYCLOAK_BASE_URL.

        Args:
            tenant: The tenant object

        Returns:
            Keycloak base URL
        """
        if tenant.oauth_issuer and "/realms/" in tenant.oauth_issuer:
            # Extract base URL from issuer
            # Example: 'http://keycloak:8080/realms/demo' -> 'http://keycloak:8080'
            return tenant.oauth_issuer.split("/realms/")[0]

        base_url = self.app.config.get("KEYCLOAK_BASE_URL")
        if not base_url:
            raise ValueError("KEYCLOAK_BASE_URL must be set in configuration")
        return base_url.rstrip("/")

    def _get_realm(self, tenant: Tenant) -> str:
        """
        Get Keycloak realm for tenant.

        Args:
            tenant: The tenant object

        Returns:
            Realm name
        """
        return tenant.keycloak_realm

    @staticmethod
    def _build_oidc_metadata_url(base_url: str, realm: str) -> str:
        """
        Build the OIDC well-known configuration URL.

        Args:
            base_url: Keycloak base URL
            realm: Keycloak realm name

        Returns:
            Full URL to OIDC discovery endpoint
        """
        return f"{base_url}/realms/{realm}/.well-known/openid-configuration"

    @staticmethod
    def _build_api_base_url(base_url: str, realm: str) -> str:
        """
        Build the API base URL for the realm.

        Args:
            base_url: Keycloak base URL
            realm: Keycloak realm name

        Returns:
            Base URL for realm API calls
        """
        return f"{base_url}/realms/{realm}/protocol/openid-connect"


# Global client instance (for backward compatibility)
keycloak_client = KeycloakOAuthProvider()


# Legacy alias
class KeycloakMultiTenantClient(KeycloakOAuthProvider):
    """Legacy alias for KeycloakOAuthProvider."""

    pass
