-- =============================================================================
-- Create Application User
-- =============================================================================
-- Single user for Superset connections. Schema isolation handled by search_path.

CREATE USER superset_app WITH PASSWORD 'superset_warehouse_password';

-- Grant connect to database
GRANT CONNECT ON DATABASE datawarehouse TO superset_app;

-- Allow creating temp tables (needed for some queries)
GRANT TEMPORARY ON DATABASE datawarehouse TO superset_app;

\echo 'Created superset_app user'
