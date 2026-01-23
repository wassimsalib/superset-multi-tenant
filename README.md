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

```bash
./start-multi-tenant.sh --create-samples
```

This does everything:
- Starts Superset, Keycloak, PostgreSQL, Redis, Nginx
- Runs database migrations
- Creates Keycloak realms with test users
- Sets up tenant schemas and sample data
- Creates demo dashboards and charts

## Test URLs

| Tenant | URL | Login |
|--------|-----|-------|
| Demo | http://demo.app.localhost | demo-admin / demo123 |
| Acme | http://acme.app.localhost | acme-admin / acme123 |

Keycloak admin: http://localhost:8180 (admin/admin)
