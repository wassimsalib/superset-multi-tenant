# TODO: Add license header
"""
Pytest fixtures for multi-tenant testing.

Usage:
    # Run all tests
    pytest tests/unit_tests/multitenancy/ -v

    # Run specific test file
    pytest tests/unit_tests/multitenancy/test_metadata_isolation.py -v

    # Run with coverage
    pytest tests/unit_tests/multitenancy/ --cov=superset.multitenancy
"""

from __future__ import annotations

import pytest
from sqlalchemy import text


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
def request_context(app):
    """Provide request context for tests that need has_request_context()."""
    with app.test_request_context():
        yield app


@pytest.fixture
def db_session(app, db):
    """Provide a clean database session for each test."""
    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()

        db.session.bind = connection

        yield db.session

        transaction.rollback()
        connection.close()


@pytest.fixture
def demo_tenant(app_context, db):
    """Get or create demo tenant."""
    from superset.multitenancy.models import Tenant

    tenant = db.session.query(Tenant).filter_by(slug="demo").first()
    if not tenant:
        pytest.skip("Demo tenant not found - run seed_tenants first")
    return tenant


@pytest.fixture
def acme_tenant(app_context, db):
    """Get or create acme tenant."""
    from superset.multitenancy.models import Tenant

    tenant = db.session.query(Tenant).filter_by(slug="acme").first()
    if not tenant:
        pytest.skip("Acme tenant not found - run seed_tenants first")
    return tenant


@pytest.fixture
def mock_flask_g():
    """Mock Flask g object for testing tenant context."""
    from flask import g

    original_tenant_id = getattr(g, "tenant_id", None)
    yield g
    if original_tenant_id is not None:
        g.tenant_id = original_tenant_id
    elif hasattr(g, "tenant_id"):
        delattr(g, "tenant_id")


@pytest.fixture
def set_tenant_demo(app_context, mock_flask_g, db):
    """Set tenant context to demo (sets g.tenant_id and search_path)."""
    from flask import g

    g.tenant_id = "demo"
    db.session.execute(text("SET search_path = tenant_demo, public"))
    yield "demo"
    db.session.execute(text("SET search_path = public"))


@pytest.fixture
def set_tenant_acme(app_context, mock_flask_g, db):
    """Set tenant context to acme (sets g.tenant_id and search_path)."""
    from flask import g

    g.tenant_id = "acme"
    db.session.execute(text("SET search_path = tenant_acme, public"))
    yield "acme"
    db.session.execute(text("SET search_path = public"))


@pytest.fixture
def clear_tenant(app_context, db):
    """Clear tenant context (reset search_path to public)."""
    from flask import g

    if hasattr(g, "tenant_id"):
        delattr(g, "tenant_id")
    db.session.execute(text("SET search_path = public"))
    yield


def is_postgres(db) -> bool:
    """Check if we're running on PostgreSQL."""
    return db.engine.dialect.name == "postgresql"


@pytest.fixture
def requires_postgres(db):
    """Skip test if not running on PostgreSQL."""
    if not is_postgres(db):
        pytest.skip("Test requires PostgreSQL")


def is_superuser_db(db) -> bool:
    """Check if current database user is a superuser."""
    result = db.session.execute(text("SELECT current_setting('is_superuser')"))
    return result.scalar() == "on"


@pytest.fixture
def requires_superuser(app_context, db, requires_postgres):
    """Skip test if not running as superuser."""
    if not is_superuser_db(db):
        pytest.skip(
            "Test requires superuser access. "
            "Run with DATABASE_APP_USER=superset to use superuser."
        )


@pytest.fixture
def mock_current_user(app_context, monkeypatch):
    """Mock Flask-Login's current_user for testing."""
    from unittest.mock import MagicMock

    mock_user = MagicMock()
    mock_user.is_authenticated = False
    mock_user.username = None

    monkeypatch.setattr("flask_login.utils._get_user", lambda: mock_user)
    monkeypatch.setattr(
        "superset.multitenancy.security_manager.current_user", mock_user
    )

    yield mock_user
