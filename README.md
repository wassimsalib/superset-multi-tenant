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

## Tests

```bash
docker compose -f docker-compose-multitenant.yml exec superset pytest /app/tests/unit_tests/multitenancy/ -v
```

## Test URLs

| Tenant | URL | Login |
|--------|-----|-------|
| Demo | http://demo.app.localhost | demo-admin / demo123 |
| Acme | http://acme.app.localhost | acme-admin / acme123 |
| Keycloak | http://localhost:8180 | admin / admin |

---

## Database Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Docker Containers                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐        │
│  │  db (PostgreSQL :5432)      │    │  warehouse (PostgreSQL :5433)│        │
│  │  Superset Metadata DB       │    │  Data Warehouse              │        │
│  │                             │    │                              │        │
│  │  Schemas:                   │    │  Schemas:                    │        │
│  │  ├── public                 │    │  ├── public                  │        │
│  │  │   ├── ab_user            │    │  ├── tenant_demo             │        │
│  │  │   ├── ab_role            │    │  │   ├── sales               │        │
│  │  │   ├── tenants            │    │  │   └── customers           │        │
│  │  │   └── user_tenants       │    │  └── tenant_acme             │        │
│  │  ├── tenant_demo            │    │      ├── sales               │        │
│  │  │   ├── dashboards         │    │      └── customers           │        │
│  │  │   ├── slices (charts)    │    │                              │        │
│  │  │   └── tables (datasets)  │    │                              │        │
│  │  └── tenant_acme            │    │                              │        │
│  │      ├── dashboards         │    │                              │        │
│  │      ├── slices (charts)    │    │                              │        │
│  │      └── tables (datasets)  │    │                              │        │
│  └─────────────────────────────┘    └─────────────────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Isolation Summary

### Schema Isolated

| Component | Database | Schema | Isolation Method |
|-----------|----------|--------|------------------|
| **Superset metadata** (dashboards, charts, datasets) | `db` (:5432) | `tenant_{slug}` | `search_path` set per-request |
| **Data warehouse tables** (sales, customers, etc.) | `warehouse` (:5433) | `tenant_{slug}` | Separate DB + per-tenant credentials |
| **Authentication** | N/A | N/A | Keycloak realms (one per tenant) |
| **User visibility in UI** | `db` (:5432) | `public` | `TenantUserFilter` (API filtering) |
| **Role/Group management** | `db` (:5432) | `public` | Superuser-only (403 for tenant admins) |

### Not currently isolated (Shared)

| Component | Database | Schema | Why |
|-----------|----------|--------|-----|
| **FAB tables** (`ab_user`, `ab_role`, etc.) | `db` (:5432) | `public` | Flask-AppBuilder core tables |
| **`tenants` table** | `db` (:5432) | `public` | Tenant configuration lookup |
| **`user_tenants` table** | `db` (:5432) | `public` | User-to-tenant mapping |
| **Platform superuser** | N/A | N/A | `admin` user has cross-tenant access |

---

## Request Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. User visits demo.app.localhost                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. Nginx proxies request to Superset (strips subdomain for routing)        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. Middleware: TenantResolver extracts "demo" from Host header             │
│     - Looks up tenant in `tenants` table                                    │
│     - Sets g.tenant, g.tenant_id (slug), g.tenant_pk (int)                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  4. Middleware: Sets PostgreSQL search_path                                 │
│     SET search_path = tenant_demo, public                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  5. Middleware: Registers OAuth provider for tenant dynamically             │
│     - Uses tenant's oauth_issuer, client_id, client_secret                  │
│     - Provider name: "keycloak_demo"                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  6. If unauthenticated → Redirect to Keycloak (tenant's realm)              │
│     User logs in with demo-admin / demo123                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  7. OAuth callback: MultiTenantSecurityManager.auth_user_oauth()            │
│     - Creates/updates user in ab_user table                                 │
│     - Creates/updates UserTenant mapping (PostgreSQL upsert)                │
│     - Stores tenant_id in session                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  8. User sees ONLY their tenant's dashboards, charts, datasets              │
│     - All queries go through tenant_demo schema first                       │
│     - FAB tables (users, roles) fall through to public schema               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  9. Request ends: Middleware resets search_path                             │
│     SET search_path = public                                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture: User-Tenant Mapping

Currently using a separate `user_tenants` mapping table (1:1 relationship) to associate users with tenants:

- **Avoids modifying FAB's `ab_user` table** - No schema changes to core Flask-AppBuilder tables
- **Uses PostgreSQL upsert** - Race-condition safe when multiple requests arrive simultaneously
- **Tenant-scoped filtering** - `TenantUserFilter` joins with `user_tenants` to filter API results
- **Created on first login** - Mapping is created/updated during OAuth authentication

**Security controls:**

| Endpoint Type | Access |
|---------------|--------|
| User list/edit API | Filtered by tenant (tenant admins see only their users) |
| Role/Group APIs | Superuser only (403 for tenant admins) |
| FAB Admin views | Superuser only (403 for tenant admins) |

---

## Key Files

```
superset/multitenancy/
├── __init__.py                    # Public exports
├── config.py                      # Feature flag check
├── middleware.py                  # Request lifecycle, search_path, OAuth registration
├── tenant_resolver.py             # Subdomain → Tenant lookup
├── security_manager.py            # MultiTenantSecurityManager, filters, access checks
├── rls.py                         # RLS Jinja helpers
├── models/
│   ├── mixins.py                  # AuditMixinNullable
│   ├── tenant.py                  # Tenant model
│   └── user_tenant.py             # UserTenant mapping model
├── oauth/
│   └── keycloak.py                # Keycloak OAuth provider config
├── isolation/
│   ├── schema_isolation.py        # search_path helpers
│   ├── metadata_isolation.py      # Context managers
│   └── tenant_database.py         # Per-tenant DB credentials
└── views/
    └── admin.py                   # Flask-AppBuilder admin views
```

---

## TODO: Moving from MVP → Stable

1. **`search_path` safety** - Verify connection pool doesn't leak tenant context between requests
2. **Async task isolation** - Celery workers getting tenant context for background jobs
3. **Cache isolation** - Tenant-scoped Redis keys

4. **Schema provisioning** - Replace bootstrap script with proper tenant onboarding API
5. **Feature flag** - Clean enable/disable via `FEATURE_FLAGS["MULTI_TENANCY_ENABLED"]`
6. **Migration path** - Document upgrade from single-tenant to multi-tenant

7. **Generalize pluggable isolation strategies** - Support RLS, separate databases, not just schemas
8. **Tenant provisioning API** - REST API for creating/managing tenants (kc, superset based, ext script?)

### WSGI-Level Schema Isolation

For complete isolation (including FAB tables like `ab_user`, `ab_role`), setting `search_path` at the WSGI layer before Flask runs based on `Host` header would:

- Allow each tenant to have their own users/roles tables
- Require cloning FAB tables into each tenant schema
- Add complexity around OAuth callbacks and platform admin access
- Need careful handling of the bootstrap/superuser account

