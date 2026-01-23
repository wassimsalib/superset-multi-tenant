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
"""
Dynamic Keycloak OIDC client configuration per tenant.
"""

import logging
from typing import Any, Optional

from flask import Flask, current_app

from keycloak_multi_tenant.models import Tenant

logger = logging.getLogger(__name__)


class KeycloakMultiTenantClient:
    """
    Generates OAuth provider configuration for tenant-specific Keycloak realms.

    Each tenant has its own Keycloak realm with dedicated client credentials,
    enabling complete authentication isolation between tenants.
    """

    def __init__(self, app: Optional[Flask] = None):
        self._app = app

    def init_app(self, app: Flask) -> None:
        """Initialize with Flask app."""
        self._app = app

    @property
    def app(self) -> Flask:
        """Get the Flask app instance."""
        return self._app or current_app

    def get_oauth_provider_config(self, tenant: Tenant) -> dict[str, Any]:
        """
        Generate OAuth provider configuration for a tenant's Keycloak realm.

        Args:
            tenant: The tenant object with Keycloak configuration

        Returns:
            Dictionary with OAuth provider configuration for authlib
        """
        base_url = self._get_keycloak_base_url()

        provider_name = f"keycloak_{tenant.tenant_id}"

        config = {
            "name": provider_name,
            "icon": "fa-key",
            "token_key": "access_token",
            "remote_app": {
                "client_id": tenant.keycloak_client_id,
                # Use decrypted secret for OAuth
                "client_secret": tenant.get_decrypted_secret(),
                "server_metadata_url": self._build_oidc_metadata_url(
                    base_url, tenant.keycloak_realm
                ),
                "api_base_url": self._build_api_base_url(
                    base_url, tenant.keycloak_realm
                ),
                "client_kwargs": {
                    "scope": "openid email profile",
                },
            },
        }

        logger.debug(
            "Generated OAuth config for tenant %s, realm %s",
            tenant.tenant_id,
            tenant.keycloak_realm,
        )

        return config

    def _get_keycloak_base_url(self) -> str:
        """Get Keycloak base URL from configuration."""
        base_url = self.app.config.get("KEYCLOAK_BASE_URL")
        if not base_url:
            raise ValueError("KEYCLOAK_BASE_URL must be set in configuration")
        return base_url.rstrip("/")

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

    def get_logout_url(self, tenant: Tenant, redirect_uri: str) -> str:
        """
        Generate Keycloak logout URL for a tenant.

        Args:
            tenant: The tenant object
            redirect_uri: URL to redirect after logout

        Returns:
            Full logout URL
        """
        base_url = self._get_keycloak_base_url()
        return (
            f"{base_url}/realms/{tenant.keycloak_realm}"
            f"/protocol/openid-connect/logout"
            f"?redirect_uri={redirect_uri}"
        )


# Global client instance
keycloak_client = KeycloakMultiTenantClient()
