# TODO: Add license header
"""
OAuth provider implementations for multi-tenancy.
"""

from superset.multitenancy.oauth.base import OAuthProviderBase
from superset.multitenancy.oauth.keycloak import KeycloakOAuthProvider
from superset.multitenancy.oauth.generic import GenericOAuthProvider

__all__ = [
    "OAuthProviderBase",
    "KeycloakOAuthProvider",
    "GenericOAuthProvider",
]
