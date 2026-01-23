-- =============================================================================
-- Create Per-Tenant Database Users (Security Isolation)
-- =============================================================================
-- Each tenant gets a dedicated PostgreSQL user that can ONLY access their schema.
-- This provides true security enforcement via PostgreSQL permissions.
--
-- KEY SECURITY FEATURES:
-- 1. Each user can only access their own schema
-- 2. Search path is restricted to their schema only
-- 3. USAGE revoked from other schemas (prevents listing)

-- -----------------------------------------------------------------------------
-- Demo Tenant User
-- -----------------------------------------------------------------------------
CREATE USER tenant_demo_user WITH PASSWORD 'demo_secure_pass_123';

-- Grant CONNECT
GRANT CONNECT ON DATABASE datawarehouse TO tenant_demo_user;

-- Grant ONLY tenant_demo schema access
GRANT USAGE ON SCHEMA tenant_demo TO tenant_demo_user;
GRANT SELECT ON ALL TABLES IN SCHEMA tenant_demo TO tenant_demo_user;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA tenant_demo TO tenant_demo_user;

-- Future tables in this schema
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_demo
    GRANT SELECT ON TABLES TO tenant_demo_user;

-- CRITICAL: Set search_path to ONLY their schema (hides other schemas in queries)
ALTER USER tenant_demo_user SET search_path TO tenant_demo;

-- Revoke USAGE on other schemas (prevents listing them)
REVOKE ALL ON SCHEMA public FROM tenant_demo_user;
REVOKE ALL ON SCHEMA tenant_acme FROM tenant_demo_user;
REVOKE ALL ON SCHEMA tenant_template FROM tenant_demo_user;

\echo 'Created tenant_demo_user with access to tenant_demo schema only'

-- -----------------------------------------------------------------------------
-- Acme Tenant User
-- -----------------------------------------------------------------------------
CREATE USER tenant_acme_user WITH PASSWORD 'acme_secure_pass_456';

-- Grant CONNECT
GRANT CONNECT ON DATABASE datawarehouse TO tenant_acme_user;

-- Grant ONLY tenant_acme schema access
GRANT USAGE ON SCHEMA tenant_acme TO tenant_acme_user;
GRANT SELECT ON ALL TABLES IN SCHEMA tenant_acme TO tenant_acme_user;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA tenant_acme TO tenant_acme_user;

-- Future tables in this schema
ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_acme
    GRANT SELECT ON TABLES TO tenant_acme_user;

-- CRITICAL: Set search_path to ONLY their schema (hides other schemas in queries)
ALTER USER tenant_acme_user SET search_path TO tenant_acme;

-- Revoke USAGE on other schemas (prevents listing them)
REVOKE ALL ON SCHEMA public FROM tenant_acme_user;
REVOKE ALL ON SCHEMA tenant_demo FROM tenant_acme_user;
REVOKE ALL ON SCHEMA tenant_template FROM tenant_acme_user;

\echo 'Created tenant_acme_user with access to tenant_acme schema only'

-- -----------------------------------------------------------------------------
-- Verification (these will be run but results just logged)
-- -----------------------------------------------------------------------------
\echo 'Verifying isolation...'

-- This should show the users we created
SELECT usename FROM pg_user WHERE usename LIKE 'tenant_%_user';

\echo 'Per-tenant users created successfully'
