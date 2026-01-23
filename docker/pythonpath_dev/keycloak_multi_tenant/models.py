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
Tenant model for database-backed multi-tenant configuration.
"""

from datetime import datetime
from typing import Any, Optional

from flask import current_app
from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text
from superset import db


class Tenant(db.Model):
    """
    Database model for tenant configuration.

    Each tenant maps to a Keycloak realm with its own client credentials.
    The client secret is stored encrypted using Fernet symmetric encryption.
    """

    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    subdomain = Column(String(255), unique=True, nullable=False, index=True)

    # Keycloak configuration
    keycloak_realm = Column(String(255), nullable=False)
    keycloak_client_id = Column(String(255), nullable=False)
    # Stores the ENCRYPTED client secret
    keycloak_client_secret = Column(Text, nullable=False, default="")

    # Per-tenant data warehouse credentials (for true security isolation)
    # These are separate database users that only have access to their tenant's schema
    warehouse_db_user = Column(String(255), nullable=True)
    # Stores the ENCRYPTED warehouse password
    warehouse_db_password = Column(Text, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Optional tenant-specific configuration overrides
    config_overrides = Column(JSON, default=dict)

    def __repr__(self) -> str:
        return f"<Tenant {self.tenant_id}>"

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
        except (InvalidToken, TypeError, ValueError):
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
        except (InvalidToken, TypeError, ValueError):
            # If decryption fails, assume it's plaintext (migration scenario)
            return ciphertext

    def get_decrypted_secret(self) -> str:
        """Get the decrypted client secret."""
        return self.decrypt_secret(self.keycloak_client_secret)

    def set_encrypted_secret(self, plaintext: str) -> None:
        """Set the client secret (encrypts before storing)."""
        self.keycloak_client_secret = self.encrypt_secret(plaintext)

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

    def get_warehouse_connection_info(self) -> Optional[dict[str, str]]:
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
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return tenant as dictionary (excluding secrets)."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "subdomain": self.subdomain,
            "keycloak_realm": self.keycloak_realm,
            "keycloak_client_id": self.keycloak_client_id,
            "warehouse_db_user": self.warehouse_db_user,
            "has_warehouse_credentials": self.has_warehouse_credentials(),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "config_overrides": self.config_overrides,
        }
