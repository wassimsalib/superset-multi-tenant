# TODO: Add license header
"""
Generic OAuth2/OIDC provider implementation.

This module provides standard OAuth2/OIDC configuration using the tenant's
oauth_issuer for discovery.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import quote, urljoin

from flask import Flask

from superset.multitenancy.oauth.base import OAuthProviderBase

if TYPE_CHECKING:
    from superset.multitenancy.models import Tenant

logger = logging.getLogger(__name__)


class GenericOAuthProvider(OAuthProviderBase):
    """
    Generic OAuth2/OIDC provider using standard discovery.

    Uses the tenant's oauth_issuer to discover endpoints via
    .well-known/openid-configuration.
    """

    def __init__(self, app: Optional[Flask] = None) -> None:
        super().__init__(app)

    def get_oauth_provider_config(self, tenant: Tenant) -> dict[str, Any]:
        """
        Generate OAuth provider configuration using standard OIDC discovery.

        Args:
            tenant: The tenant object with OAuth configuration

        Returns:
            Dictionary with OAuth provider configuration for authlib
        """
        provider_name = self.get_provider_name(tenant)
        issuer = tenant.oauth_issuer.rstrip("/")

        config = {
            "name": provider_name,
            "icon": "fa-openid",
            "token_key": "access_token",
            "remote_app": {
                "client_id": tenant.client_id,
                "client_secret": tenant.get_decrypted_secret(),
                "server_metadata_url": f"{issuer}/.well-known/openid-configuration",
                "api_base_url": issuer,
                "client_kwargs": {
                    "scope": self.get_scopes(tenant),
                },
            },
        }

        logger.debug(
            "Generated generic OAuth config for tenant %s, issuer %s",
            tenant.slug,
            issuer,
        )

        return config

    def get_logout_url(self, tenant: Tenant, redirect_uri: str) -> str:
        """
        Generate standard OIDC logout URL.

        Args:
            tenant: The tenant object
            redirect_uri: URL to redirect after logout

        Returns:
            Full logout URL (RP-initiated logout)
        """
        issuer = tenant.oauth_issuer.rstrip("/")

        # Standard OIDC RP-initiated logout
        return (
            f"{issuer}/protocol/openid-connect/logout"
            f"?post_logout_redirect_uri={quote(redirect_uri)}"
            f"&client_id={tenant.client_id}"
        )
