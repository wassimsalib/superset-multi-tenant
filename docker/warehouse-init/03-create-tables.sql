-- =============================================================================
-- Create Tables in Each Tenant Schema
-- =============================================================================
-- Same table structure in each schema. Queries use search_path to route.

-- -----------------------------------------------------------------------------
-- Table Definitions (applied to each tenant schema)
-- -----------------------------------------------------------------------------

-- Function to create tables in a schema
CREATE OR REPLACE FUNCTION create_tenant_tables(schema_name TEXT) RETURNS VOID AS $$
BEGIN
    -- Customers table
    EXECUTE format('
        CREATE TABLE %I.customers (
            id SERIAL PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            company VARCHAR(255),
            industry VARCHAR(100),
            country VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )', schema_name);

    -- Products table
    EXECUTE format('
        CREATE TABLE %I.products (
            id SERIAL PRIMARY KEY,
            product_name VARCHAR(255) NOT NULL,
            category VARCHAR(100),
            price DECIMAL(10,2),
            cost DECIMAL(10,2),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        )', schema_name);

    -- Sales table
    EXECUTE format('
        CREATE TABLE %I.sales (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER,
            product_id INTEGER,
            quantity INTEGER NOT NULL,
            unit_price DECIMAL(10,2) NOT NULL,
            total_amount DECIMAL(12,2) NOT NULL,
            sale_date DATE NOT NULL,
            region VARCHAR(100),
            sales_rep VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        )', schema_name);

    -- Monthly metrics (aggregated)
    EXECUTE format('
        CREATE TABLE %I.monthly_metrics (
            id SERIAL PRIMARY KEY,
            month DATE NOT NULL,
            total_revenue DECIMAL(14,2),
            total_orders INTEGER,
            unique_customers INTEGER,
            avg_order_value DECIMAL(10,2),
            top_product_id INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        )', schema_name);

    -- Web analytics
    EXECUTE format('
        CREATE TABLE %I.web_analytics (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL,
            page_views INTEGER,
            unique_visitors INTEGER,
            bounce_rate DECIMAL(5,2),
            avg_session_duration INTEGER,
            conversions INTEGER,
            source VARCHAR(100)
        )', schema_name);

    RAISE NOTICE 'Created tables in schema: %', schema_name;
END;
$$ LANGUAGE plpgsql;

-- Create tables in each tenant schema
SELECT create_tenant_tables('tenant_demo');
SELECT create_tenant_tables('tenant_acme');
SELECT create_tenant_tables('tenant_template');

-- Grant SELECT on all tables to superset_app
GRANT SELECT ON ALL TABLES IN SCHEMA tenant_demo TO superset_app;
GRANT SELECT ON ALL TABLES IN SCHEMA tenant_acme TO superset_app;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA tenant_demo TO superset_app;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA tenant_acme TO superset_app;

\echo 'Created tables in all tenant schemas'
