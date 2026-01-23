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
Tenant resolution from request subdomain.
"""

import logging
from typing import Optional

from flask import Flask, Request, current_app
from superset import db

from keycloak_multi_tenant.models import Tenant

logger = logging.getLogger(__name__)


class TenantResolver:
    """
    Resolves tenant from HTTP request based on subdomain.

    Example: customer1.app.example.com -> tenant_id="customer1"
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

    def resolve_from_request(self, request: Request) -> Optional[Tenant]:
        """
        Extract tenant from request subdomain.

        Args:
            request: Flask request object

        Returns:
            Tenant object if found and active, None otherwise
        """
        subdomain = self._extract_subdomain(request.host)

        if not subdomain:
            logger.debug("No subdomain found in host: %s", request.host)
            return None

        tenant = self._get_tenant_by_subdomain(subdomain)

        if tenant:
            logger.debug("Resolved tenant: %s for subdomain: %s", tenant.tenant_id, subdomain)
        else:
            logger.warning("No active tenant found for subdomain: %s", subdomain)

        return tenant

    def _extract_subdomain(self, host: str) -> Optional[str]:
        """
        Extract subdomain from host.

        Examples:
            - "customer1.app.example.com" -> "customer1"
            - "customer1.app.example.com:8088" -> "customer1"
            - "app.example.com" -> None
            - "localhost:8088" -> None

        Args:
            host: The HTTP host header value

        Returns:
            Subdomain string or None if not found
        """
        # Remove port if present
        host_without_port = host.split(":")[0]

        base_domain = self.app.config.get(
            "MULTI_TENANT_BASE_DOMAIN", "app.example.com"
        )

        # Check if host ends with base domain
        if not host_without_port.endswith(base_domain):
            logger.debug(
                "Host %s does not match base domain %s",
                host_without_port,
                base_domain,
            )
            return None

        # Extract subdomain
        if host_without_port == base_domain:
            return None

        # Get the subdomain part (everything before the base domain)
        subdomain_part = host_without_port[: -(len(base_domain) + 1)]

        # Return the first part if there are nested subdomains
        # e.g., "customer1.region1.app.example.com" -> "customer1"
        return subdomain_part.split(".")[0] if subdomain_part else None

    def _get_tenant_by_subdomain(self, subdomain: str) -> Optional[Tenant]:
        """
        Look up tenant by subdomain.

        Args:
            subdomain: The subdomain to look up

        Returns:
            Tenant object if found and active, None otherwise
        """
        # Direct query - no caching for now to ensure immediate tenant recognition
        # and avoid SQLAlchemy DetachedInstanceError issues
        return db.session.query(Tenant).filter_by(
            subdomain=subdomain, is_active=True
        ).first()

    def clear_cache(self) -> None:
        """Clear the tenant lookup cache (no-op, caching disabled)."""
        logger.debug("Tenant cache clear called (caching currently disabled)")

    def invalidate_tenant(self, subdomain: str) -> None:
        """Invalidate cache for a specific tenant (no-op, caching disabled)."""
        pass


# Global resolver instance
tenant_resolver = TenantResolver()
