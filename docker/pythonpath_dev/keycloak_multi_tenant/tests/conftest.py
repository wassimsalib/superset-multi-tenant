# TODO: Add Apache license header
"""
Pytest fixtures for multi-tenant testing.

Usage:
    # Run all tests
    docker compose exec superset pytest /app/docker/pythonpath_dev/keycloak_multi_tenant/tests/

    # Run specific test file
    docker compose exec superset pytest /app/docker/pythonpath_dev/keycloak_multi_tenant/tests/test_metadata_isolation.py -v

    # Run with coverage
    docker compose exec superset pytest /app/docker/pythonpath_dev/keycloak_multi_tenant/tests/ --cov=keycloak_multi_tenant
"""

import os
import sys

import pytest
from sqlalchemy import text

# Add pythonpath_dev to path
sys.path.insert(0, "/app/docker/pythonpath_dev")


@pytest.fixture(scope="session")
def app():
    """Create Flask app for testing."""
    from superset import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="session")
def db(app):
    """Get database session."""
    from superset import db as _db

    with app.app_context():
        yield _db


@pytest.fixture
def app_context(app):
    """Provide app context for tests."""
    with app.app_context():
        yield app


@pytest.fixture
def db_session(app, db):
    """Provide a clean database session for each test."""
    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()

        # Bind session to connection
        db.session.bind = connection

        yield db.session

        # Rollback after test
        transaction.rollback()
        connection.close()


@pytest.fixture
def demo_tenant(app_context, db):
    """Get or create demo tenant."""
    from keycloak_multi_tenant.models import Tenant

    tenant = db.session.query(Tenant).filter_by(tenant_id="demo").first()
    if not tenant:
        pytest.skip("Demo tenant not found - run setup-keycloak.sh first")
    return tenant


@pytest.fixture
def acme_tenant(app_context, db):
    """Get or create acme tenant."""
    from keycloak_multi_tenant.models import Tenant

    tenant = db.session.query(Tenant).filter_by(tenant_id="acme").first()
    if not tenant:
        pytest.skip("Acme tenant not found - run setup-keycloak.sh first")
    return tenant


@pytest.fixture
def mock_flask_g():
    """Mock Flask g object for testing tenant context."""
    from flask import g

    original_tenant_id = getattr(g, "tenant_id", None)
    yield g
    # Restore original
    if original_tenant_id is not None:
        g.tenant_id = original_tenant_id
    elif hasattr(g, "tenant_id"):
        delattr(g, "tenant_id")


@pytest.fixture
def set_tenant_demo(app_context, mock_flask_g, db):
    """Set tenant context to demo (sets g.tenant_id and search_path)."""
    from flask import g

    g.tenant_id = "demo"
    # Set search_path for schema-based isolation
    db.session.execute(text("SET search_path = tenant_demo, public"))
    yield "demo"
    # Reset search_path
    db.session.execute(text("SET search_path = public"))


@pytest.fixture
def set_tenant_acme(app_context, mock_flask_g, db):
    """Set tenant context to acme (sets g.tenant_id and search_path)."""
    from flask import g

    g.tenant_id = "acme"
    # Set search_path for schema-based isolation
    db.session.execute(text("SET search_path = tenant_acme, public"))
    yield "acme"
    # Reset search_path
    db.session.execute(text("SET search_path = public"))


@pytest.fixture
def clear_tenant(app_context, db):
    """Clear tenant context (reset search_path to public)."""
    from flask import g

    if hasattr(g, "tenant_id"):
        delattr(g, "tenant_id")
    # Reset search_path for schema-based isolation
    db.session.execute(text("SET search_path = public"))
    yield


def is_postgres(db):
    """Check if we're running on PostgreSQL."""
    return db.engine.dialect.name == "postgresql"


@pytest.fixture
def requires_postgres(db):
    """Skip test if not running on PostgreSQL."""
    if not is_postgres(db):
        pytest.skip("Test requires PostgreSQL")


def is_superuser(db):
    """Check if current database user is a superuser."""
    result = db.session.execute(
        text("SELECT current_setting('is_superuser')")
    )
    return result.scalar() == "on"


@pytest.fixture
def requires_superuser(app_context, db, requires_postgres):
    """Skip test if not running as superuser.

    Some tests need superuser access to create schemas or tables.
    """
    if not is_superuser(db):
        pytest.skip(
            "Test requires superuser access. "
            "Run with DATABASE_APP_USER=superset to use superuser."
        )


@pytest.fixture
def mock_current_user(app_context, monkeypatch):
    """Mock Flask-Login's current_user for testing.

    Usage:
        def test_something(mock_current_user):
            mock_current_user.is_authenticated = True
            mock_current_user.username = "demo-admin"
            # ... test code
    """
    from unittest.mock import MagicMock

    mock_user = MagicMock()
    mock_user.is_authenticated = False
    mock_user.username = None

    # Patch flask_login's current_user
    monkeypatch.setattr("flask_login.utils._get_user", lambda: mock_user)
    monkeypatch.setattr("keycloak_multi_tenant.security_manager.current_user", mock_user)

    yield mock_user
