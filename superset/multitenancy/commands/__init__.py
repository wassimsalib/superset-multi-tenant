# TODO: Add license header
"""
Multi-tenancy CLI commands.
"""

from superset.multitenancy.commands.seed_tenants import seed_tenants

__all__ = ["seed_tenants"]
