# TODO: Add license header
"""
Tenant resolution from request subdomain.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from flask import Flask, Request, current_app

# Import db directly from extensions to avoid circular imports
from superset.extensions import db

if TYPE_CHECKING:
    from superset.multitenancy.models import Tenant

logger = logging.getLogger(__name__)


class TenantResolver:
    """
    Resolves tenant from HTTP request based on subdomain.

    Example: customer1.app.example.com -> slug="customer1"
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
            logger.debug(
                "Resolved tenant: %s for subdomain: %s", tenant.slug, subdomain
            )
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
        return subdomain_part.split(".")[0] if subdomain_part else None

    def _get_tenant_by_subdomain(self, subdomain: str) -> Optional["Tenant"]:
        """
        Look up tenant by subdomain (slug).

        Args:
            subdomain: The subdomain to look up

        Returns:
            Tenant object if found and active, None otherwise
        """
        # Lazy import to avoid circular dependencies at module load time
        from superset.multitenancy.models import Tenant

        # Direct query - no caching for now to ensure immediate tenant recognition
        return db.session.query(Tenant).filter_by(
            slug=subdomain, is_active=True
        ).first()

    def clear_cache(self) -> None:
        """Clear the tenant lookup cache (no-op, caching disabled)."""
        logger.debug("Tenant cache clear called (caching disabled)")

    def invalidate_tenant(self, subdomain: str) -> None:
        """Invalidate cache for a specific tenant (no-op, caching disabled)."""
        pass


# Global resolver instance
tenant_resolver = TenantResolver()
