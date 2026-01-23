-- =============================================================================
-- Create Tenant Schemas
-- =============================================================================
-- Each tenant gets their own schema with identical table structures.

-- -----------------------------------------------------------------------------
-- Demo Tenant Schema
-- -----------------------------------------------------------------------------
CREATE SCHEMA tenant_demo;

GRANT USAGE ON SCHEMA tenant_demo TO superset_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_demo
    GRANT SELECT ON TABLES TO superset_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_demo
    GRANT USAGE, SELECT ON SEQUENCES TO superset_app;

-- -----------------------------------------------------------------------------
-- Acme Tenant Schema
-- -----------------------------------------------------------------------------
CREATE SCHEMA tenant_acme;

GRANT USAGE ON SCHEMA tenant_acme TO superset_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_acme
    GRANT SELECT ON TABLES TO superset_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_acme
    GRANT USAGE, SELECT ON SEQUENCES TO superset_app;

-- -----------------------------------------------------------------------------
-- Template schema (for cloning to new tenants)
-- -----------------------------------------------------------------------------
CREATE SCHEMA tenant_template;

\echo 'Created tenant schemas: tenant_demo, tenant_acme, tenant_template'
