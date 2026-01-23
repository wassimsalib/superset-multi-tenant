-- =============================================================================
-- Verify Tenant Isolation
-- =============================================================================
-- Run these queries to confirm schema isolation is working correctly.

\echo '============================================'
\echo 'Verifying Tenant Data Isolation'
\echo '============================================'

-- -----------------------------------------------------------------------------
-- Test 1: Demo tenant data
-- -----------------------------------------------------------------------------
\echo ''
\echo '--- Demo Tenant (B2C Retail) ---'

SET search_path TO tenant_demo, public;

\echo 'Customers (should be B2C consumers):'
SELECT id, customer_name, company, industry FROM customers LIMIT 3;

\echo 'Sample sales (should be ~$50-200 range):'
SELECT id, total_amount, sale_date, region FROM sales LIMIT 3;

\echo 'Total revenue:'
SELECT SUM(total_amount) as demo_total_revenue FROM sales;

-- -----------------------------------------------------------------------------
-- Test 2: Acme tenant data
-- -----------------------------------------------------------------------------
\echo ''
\echo '--- Acme Tenant (B2B Enterprise) ---'

SET search_path TO tenant_acme, public;

\echo 'Customers (should be B2B enterprises):'
SELECT id, customer_name, company, industry FROM customers LIMIT 3;

\echo 'Sample sales (should be ~$10,000-100,000 range):'
SELECT id, total_amount, sale_date, region FROM sales LIMIT 3;

\echo 'Total revenue:'
SELECT SUM(total_amount) as acme_total_revenue FROM sales;

-- -----------------------------------------------------------------------------
-- Test 3: Verify no cross-tenant access from public
-- -----------------------------------------------------------------------------
\echo ''
\echo '--- Test No Public Access ---'

SET search_path TO public;

\echo 'Confirming public schema has no direct tenant tables (expected: 0 rows):'
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_name IN ('customers', 'sales', 'products');

-- -----------------------------------------------------------------------------
-- Summary
-- -----------------------------------------------------------------------------
\echo ''
\echo '============================================'
\echo 'Schema Summary'
\echo '============================================'

SELECT
    table_schema,
    COUNT(*) as table_count
FROM information_schema.tables
WHERE table_schema LIKE 'tenant_%'
GROUP BY table_schema
ORDER BY table_schema;

\echo ''
\echo 'Row counts per schema:'

SELECT 'tenant_demo' as schema, 'customers' as table_name, COUNT(*) as rows FROM tenant_demo.customers
UNION ALL
SELECT 'tenant_demo', 'sales', COUNT(*) FROM tenant_demo.sales
UNION ALL
SELECT 'tenant_acme', 'customers', COUNT(*) FROM tenant_acme.customers
UNION ALL
SELECT 'tenant_acme', 'sales', COUNT(*) FROM tenant_acme.sales
ORDER BY schema, table_name;

RESET search_path;

\echo ''
\echo '============================================'
\echo 'Isolation verification complete!'
\echo '============================================'
