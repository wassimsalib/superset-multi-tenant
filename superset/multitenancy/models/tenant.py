# TODO: Add license header
"""
Tenant model for database-backed multi-tenant configuration.

Aligned with CTO architecture conventions:
- slug: Tenant identifier (was: tenant_id/subdomain - merged into one field)
- uuid: External API exposure (Superset requirement)
- is_admin_tenant: Platform admin concept
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from flask import current_app
from sqlalchemy import Boolean, Column, Integer, String, Text

# Import db directly from extensions to avoid circular imports
# (superset/__init__.py imports SupersetSecurityManager which triggers model chain)
from superset.extensions import db
from superset.multitenancy.models.mixins import AuditMixinNullable


class Tenant(db.Model, AuditMixinNullable):
    """
    Database model for tenant configuration.

    Each tenant maps to an OAuth provider (e.g., Keycloak realm) with its own
    client credentials. Secrets are stored encrypted using Fernet symmetric encryption.
    """

    __tablename__ = "tenants"

    id: int = Column(Integer, primary_key=True, autoincrement=True)

    # CTO-aligned naming: uuid for external API, slug for subdomain/identifier
    uuid: str = Column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid4()),
        index=True,
    )
    slug: str = Column(String(255), unique=True, nullable=False, index=True)
    name: str = Column(String(255), nullable=False)

    # Platform admin concept
    is_admin_tenant: bool = Column(Boolean, default=False, nullable=False)

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize Tenant with Python-level defaults.

        SQLAlchemy column defaults only apply on INSERT, not on object
        instantiation. This ensures uuid and is_admin_tenant have values
        immediately after creating a Tenant object.
        """
        if "uuid" not in kwargs:
            kwargs["uuid"] = str(uuid4())
        if "is_admin_tenant" not in kwargs:
            kwargs["is_admin_tenant"] = False
        if "is_active" not in kwargs:
            kwargs["is_active"] = True
        if "client_secret" not in kwargs:
            kwargs["client_secret"] = ""
        super().__init__(**kwargs)

    # Generic OAuth configuration (not Keycloak-specific)
    oauth_issuer: str = Column(String(512), nullable=False)
    client_id: str = Column(String(255), nullable=False)
    # Stores the ENCRYPTED client secret
    client_secret: str = Column(Text, nullable=False, default="")
    scopes: Optional[str] = Column(Text, nullable=True)  # Comma-separated

    # Database isolation
    db_sqlalchemy_uri: Optional[str] = Column(Text, nullable=True)
    default_schema: Optional[str] = Column(String(255), nullable=True)

    # Per-tenant data warehouse credentials (for true security isolation)
    warehouse_db_user: Optional[str] = Column(String(255), nullable=True)
    warehouse_db_password: Optional[str] = Column(Text, nullable=True)

    # Status
    is_active: bool = Column(Boolean, default=True, nullable=False)

    # Optional tenant-specific configuration overrides (JSON)
    config_overrides: Optional[str] = Column(Text, nullable=True)

    # -------------------------------------------------------------------------
    # Legacy compatibility properties (tenant_id -> slug)
    # -------------------------------------------------------------------------

    @property
    def tenant_id(self) -> str:
        """Legacy alias for slug (backward compatibility)."""
        return self.slug

    @tenant_id.setter
    def tenant_id(self, value: str) -> None:
        """Legacy setter for slug (backward compatibility)."""
        self.slug = value

    @property
    def subdomain(self) -> str:
        """Legacy alias for slug (subdomain IS the slug)."""
        return self.slug

    @subdomain.setter
    def subdomain(self, value: str) -> None:
        """Legacy setter for slug."""
        self.slug = value

    # -------------------------------------------------------------------------
    # Legacy Keycloak compatibility properties
    # -------------------------------------------------------------------------

    @property
    def keycloak_realm(self) -> str:
        """
        Extract realm from oauth_issuer for Keycloak compatibility.

        Example: 'http://keycloak:8080/realms/demo' -> 'demo'
        """
        if self.oauth_issuer and "/realms/" in self.oauth_issuer:
            return self.oauth_issuer.split("/realms/")[-1].rstrip("/")
        return self.slug

    @property
    def keycloak_client_id(self) -> str:
        """Legacy alias for client_id."""
        return self.client_id

    @property
    def keycloak_client_secret(self) -> str:
        """Legacy alias for client_secret (encrypted)."""
        return self.client_secret

    def __repr__(self) -> str:
        return f"<Tenant {self.slug}>"

    # -------------------------------------------------------------------------
    # Encryption helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def get_encryption_key() -> Optional[bytes]:
        """Get the Fernet encryption key from app config."""
        key = current_app.config.get("TENANT_SECRET_ENCRYPTION_KEY")
        if not key:
            return None
        if isinstance(key, str):
            key = key.encode()
        return key

    @classmethod
    def encrypt_secret(cls, plaintext: str) -> str:
        """
        Encrypt a secret using Fernet symmetric encryption.

        Args:
            plaintext: The secret to encrypt

        Returns:
            Encrypted string, or original if encryption unavailable
        """
        key = cls.get_encryption_key()
        if not key or not plaintext:
            return plaintext

        try:
            from cryptography.fernet import Fernet, InvalidToken

            fernet = Fernet(key)
            return fernet.encrypt(plaintext.encode()).decode()
        except (ImportError, InvalidToken, TypeError, ValueError):
            # If encryption fails, store as-is (for development/testing)
            return plaintext

    @classmethod
    def decrypt_secret(cls, ciphertext: str) -> str:
        """
        Decrypt a secret using Fernet symmetric encryption.

        Args:
            ciphertext: The encrypted secret

        Returns:
            Decrypted string, or original if decryption unavailable/fails
        """
        key = cls.get_encryption_key()
        if not key or not ciphertext:
            return ciphertext

        try:
            from cryptography.fernet import Fernet, InvalidToken

            fernet = Fernet(key)
            return fernet.decrypt(ciphertext.encode()).decode()
        except (ImportError, InvalidToken, TypeError, ValueError):
            # If decryption fails, assume it's plaintext (migration scenario)
            return ciphertext

    def get_decrypted_secret(self) -> str:
        """Get the decrypted client secret."""
        return self.decrypt_secret(self.client_secret)

    def set_encrypted_secret(self, plaintext: str) -> None:
        """Set the client secret (encrypts before storing)."""
        self.client_secret = self.encrypt_secret(plaintext)

    # -------------------------------------------------------------------------
    # Warehouse credentials helpers
    # -------------------------------------------------------------------------

    def get_warehouse_password(self) -> Optional[str]:
        """Get the decrypted warehouse database password."""
        if not self.warehouse_db_password:
            return None
        return self.decrypt_secret(self.warehouse_db_password)

    def set_warehouse_password(self, plaintext: str) -> None:
        """Set the warehouse password (encrypts before storing)."""
        self.warehouse_db_password = self.encrypt_secret(plaintext)

    def has_warehouse_credentials(self) -> bool:
        """Check if tenant has per-tenant warehouse credentials configured."""
        return bool(self.warehouse_db_user and self.warehouse_db_password)

    def get_warehouse_connection_info(self) -> Optional[dict[str, Any]]:
        """
        Get warehouse connection credentials for this tenant.

        Returns:
            Dict with 'user' and 'password' keys, or None if not configured
        """
        if not self.has_warehouse_credentials():
            return None
        return {
            "user": self.warehouse_db_user,
            "password": self.get_warehouse_password(),
        }

    # -------------------------------------------------------------------------
    # Schema helpers
    # -------------------------------------------------------------------------

    def get_schema_name(self) -> str:
        """
        Get the PostgreSQL schema name for this tenant.

        Returns:
            Schema name (e.g., "tenant_acme")
        """
        if self.default_schema:
            return self.default_schema
        return f"tenant_{self.slug}"

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return tenant as dictionary (excluding secrets)."""
        return {
            "id": self.id,
            "uuid": self.uuid,
            "slug": self.slug,
            "name": self.name,
            "is_admin_tenant": self.is_admin_tenant,
            "oauth_issuer": self.oauth_issuer,
            "client_id": self.client_id,
            "default_schema": self.default_schema,
            "warehouse_db_user": self.warehouse_db_user,
            "has_warehouse_credentials": self.has_warehouse_credentials(),
            "is_active": self.is_active,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "changed_on": self.changed_on.isoformat() if self.changed_on else None,
            "config_overrides": self.config_overrides,
            # Legacy fields for backward compatibility
            "tenant_id": self.slug,
            "subdomain": self.slug,
        }
