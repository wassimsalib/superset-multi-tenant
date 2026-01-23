# Multi-Tenant Superset (Dev MVP)

Keycloak-based multi-tenant authentication with per-tenant schema isolation.

## Prerequisites

- Docker & Docker Compose
- uv (optional, for auto-generating encryption key)

```bash
# Install uv (optional)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Hosts File

Add to `/etc/hosts`:

```
127.0.0.1 demo.app.localhost acme.app.localhost host.docker.internal
```

## Quick Start
This does everything to build the current dev setup:
- Starts Superset, Keycloak, PostgreSQL, Redis, Nginx via docker-compose-multitenant.yml
- Waits on startup to finish, runs superset database migrations
- Creates Keycloak realms with test users
- Sets up tenant schemas and sample data in pseudo-warehouse
- Creates demo dashboards and charts (1 templated + Acme unique dashboard)

```bash
./start-multi-tenant.sh --create-samples
```

# Tests
```bash
docker compose -f docker-compose-multitenant.yml exec superset pytest /app/docker/pythonpath_dev/keycloak_multi_tenant/tests/ -v
``` 



## Test URLs

| Tenant | URL | Login |
|--------|-----|-------|
| Demo | http://demo.app.localhost | demo-admin / demo123 |
| Acme | http://acme.app.localhost | acme-admin / acme123 |
| Keycloak | http://localhost:8180 | admin / admin |

## Current Flow

Tenant isolation via PostgreSQL `search_path` per request + per-tenant Keycloak realms for auth.

## TODO: Moving from mvp -> stable

1. **`search_path` safety** - Check connection pool contamination, race conditions, async task behavior
2. **schema cloning** - Replace bootstrap script with proper migration hooks

4. **SecurityManager subclass** - Coupled to parent class signature changes 
5. **feature flag** - Clean enable/disable without path hacks
6. **migration considerations** - Trace path on existing single-tenant deployments, e.g swapping to multitenant, unintentional breaks


Consolidate scattered code into `superset/extensions/multi_tenant/` following Superset's extension pattern:

- **`MultiTenantExtension`** - Flask extension, feature-flag gated
- **`TenantResolver`** - Pluggable: subdomain, header, JWT claim
- **`IsolationStrategy`** - Pluggable: schema, RLS, separate DBs
- Move migrations into `superset/migrations/versions/`

This makes it database-agnostic, testable, and upstream-mergeable.
