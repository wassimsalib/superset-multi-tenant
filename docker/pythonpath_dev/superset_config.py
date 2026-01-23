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
#
# This file is included in the final Docker image and SHOULD be overridden when
# deploying the image to prod. Settings configured here are intended for use in local
# development environments. Also note that superset_config_docker.py is imported
# as a final step as a means to override "defaults" configured here
#
import logging
import os
import sys

from celery.schedules import crontab
from flask_appbuilder.security.manager import AUTH_OAUTH
from flask_caching.backends.filesystemcache import FileSystemCache

logger = logging.getLogger()

DATABASE_DIALECT = os.getenv("DATABASE_DIALECT")
DATABASE_USER = os.getenv("DATABASE_USER")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_HOST = os.getenv("DATABASE_HOST")
DATABASE_PORT = os.getenv("DATABASE_PORT")
DATABASE_DB = os.getenv("DATABASE_DB")

# Non-superuser application credentials (for RLS enforcement)
# Falls back to DATABASE_USER if not set (backwards compatibility)
DATABASE_APP_USER = os.getenv("DATABASE_APP_USER", DATABASE_USER)
DATABASE_APP_PASSWORD = os.getenv("DATABASE_APP_PASSWORD", DATABASE_PASSWORD)

EXAMPLES_USER = os.getenv("EXAMPLES_USER")
EXAMPLES_PASSWORD = os.getenv("EXAMPLES_PASSWORD")
EXAMPLES_HOST = os.getenv("EXAMPLES_HOST")
EXAMPLES_PORT = os.getenv("EXAMPLES_PORT")
EXAMPLES_DB = os.getenv("EXAMPLES_DB")

# The SQLAlchemy connection string.
# Uses the non-superuser app credentials for RLS enforcement.
# For migrations, run with DATABASE_APP_USER=superset to use superuser.
SQLALCHEMY_DATABASE_URI = (
    f"{DATABASE_DIALECT}://"
    f"{DATABASE_APP_USER}:{DATABASE_APP_PASSWORD}@"
    f"{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_DB}"
)

# Use environment variable if set, otherwise construct from components
# This MUST take precedence over any other configuration
SQLALCHEMY_EXAMPLES_URI = os.getenv(
    "SUPERSET__SQLALCHEMY_EXAMPLES_URI",
    (
        f"{DATABASE_DIALECT}://"
        f"{EXAMPLES_USER}:{EXAMPLES_PASSWORD}@"
        f"{EXAMPLES_HOST}:{EXAMPLES_PORT}/{EXAMPLES_DB}"
    ),
)


REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_CELERY_DB = os.getenv("REDIS_CELERY_DB", "0")
REDIS_RESULTS_DB = os.getenv("REDIS_RESULTS_DB", "1")

RESULTS_BACKEND = FileSystemCache("/app/superset_home/sqllab")

CACHE_CONFIG = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "superset_",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": REDIS_RESULTS_DB,
}
DATA_CACHE_CONFIG = CACHE_CONFIG
THUMBNAIL_CACHE_CONFIG = CACHE_CONFIG


class CeleryConfig:
    broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_CELERY_DB}"
    imports = (
        "superset.sql_lab",
        "superset.tasks.scheduler",
        "superset.tasks.thumbnails",
        "superset.tasks.cache",
    )
    result_backend = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_RESULTS_DB}"
    worker_prefetch_multiplier = 1
    task_acks_late = False
    beat_schedule = {
        "reports.scheduler": {
            "task": "reports.scheduler",
            "schedule": crontab(minute="*", hour="*"),
        },
        "reports.prune_log": {
            "task": "reports.prune_log",
            "schedule": crontab(minute=10, hour=0),
        },
    }


CELERY_CONFIG = CeleryConfig

FEATURE_FLAGS = {"ALERT_REPORTS": True, "ENABLE_TEMPLATE_PROCESSING": True}
ALERT_REPORTS_NOTIFICATION_DRY_RUN = True
WEBDRIVER_BASEURL = f"http://superset_app{os.environ.get('SUPERSET_APP_ROOT', '/')}/"  # When using docker compose baseurl should be http://superset_nginx{ENV{BASEPATH}}/  # noqa: E501
# The base URL for the email report hyperlinks.
WEBDRIVER_BASEURL_USER_FRIENDLY = (
    f"http://localhost:8888/{os.environ.get('SUPERSET_APP_ROOT', '/')}/"
)
SQLLAB_CTAS_NO_LIMIT = True

log_level_text = os.getenv("SUPERSET_LOG_LEVEL", "INFO")
LOG_LEVEL = getattr(logging, log_level_text.upper(), logging.INFO)

if os.getenv("CYPRESS_CONFIG") == "true":
    # When running the service as a cypress backend, we need to import the config
    # located @ tests/integration_tests/superset_test_config.py
    base_dir = os.path.dirname(__file__)
    module_folder = os.path.abspath(
        os.path.join(base_dir, "../../tests/integration_tests/")
    )
    sys.path.insert(0, module_folder)
    from superset_test_config import *  # noqa

    sys.path.pop(0)

# =============================================================================
# MULTI-TENANT KEYCLOAK AUTHENTICATION
# =============================================================================

# Enable multi-tenant mode
MULTI_TENANT_ENABLED = os.getenv("MULTI_TENANT_ENABLED", "true").lower() == "true"

if MULTI_TENANT_ENABLED:
    from keycloak_multi_tenant import KeycloakMultiTenantSecurityManager
    from keycloak_multi_tenant.middleware import setup_tenant_middleware
    from keycloak_multi_tenant.rls import register_tenant_jinja_context
    from keycloak_multi_tenant.metadata_isolation import setup_metadata_isolation
    from keycloak_multi_tenant.admin import register_admin_views
    from keycloak_multi_tenant.db_isolation import init_db_isolation

    # Authentication type
    AUTH_TYPE = AUTH_OAUTH

    # Custom security manager
    CUSTOM_SECURITY_MANAGER = KeycloakMultiTenantSecurityManager

    # OAuth providers - starts empty, dynamically populated per-tenant
    OAUTH_PROVIDERS = []

    # Keycloak base URL - must work for both browser AND container
    # host.docker.internal works from containers (extra_hosts) and browser (/etc/hosts)
    KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "http://host.docker.internal:8180")

    # Encryption key for tenant client secrets (generate with Fernet.generate_key())
    TENANT_SECRET_ENCRYPTION_KEY = os.getenv("TENANT_SECRET_ENCRYPTION_KEY")

    # Multi-tenant configuration
    MULTI_TENANT_BASE_DOMAIN = os.getenv("MULTI_TENANT_BASE_DOMAIN", "app.localhost")
    TENANT_NOT_FOUND_URL = os.getenv(
        "TENANT_NOT_FOUND_URL", "http://app.localhost/unknown-tenant"
    )
    TENANT_CACHE_TTL = int(os.getenv("TENANT_CACHE_TTL", "300"))

    # Session cookie config for multi-tenant subdomains
    # Leading dot allows cookies to be shared across all subdomains
    SESSION_COOKIE_DOMAIN = f".{MULTI_TENANT_BASE_DOMAIN}"
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # Set True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True

    # Public endpoints that don't require tenant context
    # Note: /login/ is NOT included - we need tenant context to redirect to correct OAuth
    MULTI_TENANT_PUBLIC_ENDPOINTS = [
        "/health",
        "/healthcheck",
        "/static/",
        "/api/v1/security/csrf_token",
        "/logout/",
    ]

    # Role mapping: Keycloak groups -> Superset roles
    AUTH_ROLES_MAPPING = {
        "superset-admin": ["Admin"],
        "superset-alpha": ["Alpha"],
        "superset-gamma": ["Gamma"],
        "superset-sql-lab": ["sql_lab"],
    }
    AUTH_ROLES_SYNC_AT_LOGIN = True

    # Allow OAuth users to self-register
    AUTH_USER_REGISTRATION = True
    # Default role for new OAuth users (when no Keycloak groups match)
    AUTH_USER_REGISTRATION_ROLE = "Gamma"

    # Flask app initialization hook
    def FLASK_APP_MUTATOR(app):
        """Initialize multi-tenant components."""
        setup_tenant_middleware(app)
        register_tenant_jinja_context(app)
        setup_metadata_isolation(app)
        register_admin_views(app)
        init_db_isolation(app)
        logger.info("Multi-tenant Keycloak authentication initialized")

    logger.info("Multi-tenant configuration loaded")
else:
    logger.info("Multi-tenant mode disabled")

# =============================================================================

#
# Optionally import superset_config_docker.py (which will have been included on
# the PYTHONPATH) in order to allow for local settings to be overridden
#
try:
    import superset_config_docker
    from superset_config_docker import *  # noqa: F403

    logger.info(
        "Loaded your Docker configuration at [%s]", superset_config_docker.__file__
    )
except ImportError:
    logger.info("Using default Docker config...")
