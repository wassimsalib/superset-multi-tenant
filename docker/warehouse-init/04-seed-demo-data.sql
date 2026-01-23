-- =============================================================================
-- Seed Demo Tenant Data
-- =============================================================================
-- Sample data for the "demo" tenant - a B2C retail company

SET search_path TO tenant_demo, public;

-- -----------------------------------------------------------------------------
-- Customers (B2C retail customers)
-- -----------------------------------------------------------------------------
INSERT INTO customers (customer_name, email, company, industry, country) VALUES
    ('Alice Johnson', 'alice@email.com', NULL, 'Consumer', 'USA'),
    ('Bob Smith', 'bob.smith@email.com', NULL, 'Consumer', 'USA'),
    ('Carol Williams', 'carol.w@email.com', NULL, 'Consumer', 'Canada'),
    ('David Brown', 'david.b@email.com', NULL, 'Consumer', 'UK'),
    ('Eva Martinez', 'eva.m@email.com', NULL, 'Consumer', 'Spain'),
    ('Frank Lee', 'frank.lee@email.com', NULL, 'Consumer', 'USA'),
    ('Grace Kim', 'grace.k@email.com', NULL, 'Consumer', 'South Korea'),
    ('Henry Wilson', 'henry.w@email.com', NULL, 'Consumer', 'Australia'),
    ('Iris Chen', 'iris.c@email.com', NULL, 'Consumer', 'Canada'),
    ('Jack Davis', 'jack.d@email.com', NULL, 'Consumer', 'USA');

-- -----------------------------------------------------------------------------
-- Products (Retail products)
-- -----------------------------------------------------------------------------
INSERT INTO products (product_name, category, price, cost) VALUES
    ('Wireless Headphones', 'Electronics', 79.99, 35.00),
    ('Smart Watch', 'Electronics', 199.99, 85.00),
    ('Running Shoes', 'Footwear', 129.99, 55.00),
    ('Yoga Mat', 'Fitness', 39.99, 12.00),
    ('Coffee Maker', 'Home', 89.99, 40.00),
    ('Backpack', 'Accessories', 59.99, 25.00),
    ('Water Bottle', 'Fitness', 24.99, 8.00),
    ('Desk Lamp', 'Home', 44.99, 18.00),
    ('Phone Case', 'Electronics', 19.99, 5.00),
    ('Notebook Set', 'Office', 14.99, 4.00);

-- -----------------------------------------------------------------------------
-- Sales (2024 retail transactions)
-- -----------------------------------------------------------------------------
INSERT INTO sales (customer_id, product_id, quantity, unit_price, total_amount, sale_date, region, sales_rep) VALUES
    -- January 2024
    (1, 1, 1, 79.99, 79.99, '2024-01-05', 'North America', 'Sales Team A'),
    (2, 3, 1, 129.99, 129.99, '2024-01-08', 'North America', 'Sales Team A'),
    (3, 2, 1, 199.99, 199.99, '2024-01-12', 'North America', 'Sales Team B'),
    (4, 5, 2, 89.99, 179.98, '2024-01-15', 'Europe', 'Sales Team C'),
    (5, 4, 3, 39.99, 119.97, '2024-01-18', 'Europe', 'Sales Team C'),
    -- February 2024
    (6, 1, 2, 79.99, 159.98, '2024-02-02', 'North America', 'Sales Team A'),
    (7, 6, 1, 59.99, 59.99, '2024-02-10', 'Asia Pacific', 'Sales Team D'),
    (8, 2, 1, 199.99, 199.99, '2024-02-14', 'Asia Pacific', 'Sales Team D'),
    (1, 7, 4, 24.99, 99.96, '2024-02-20', 'North America', 'Sales Team A'),
    (2, 8, 1, 44.99, 44.99, '2024-02-25', 'North America', 'Sales Team B'),
    -- March 2024
    (3, 9, 2, 19.99, 39.98, '2024-03-01', 'North America', 'Sales Team B'),
    (4, 10, 5, 14.99, 74.95, '2024-03-05', 'Europe', 'Sales Team C'),
    (5, 1, 1, 79.99, 79.99, '2024-03-12', 'Europe', 'Sales Team C'),
    (9, 3, 2, 129.99, 259.98, '2024-03-18', 'North America', 'Sales Team A'),
    (10, 4, 1, 39.99, 39.99, '2024-03-25', 'North America', 'Sales Team B'),
    -- April 2024
    (1, 2, 1, 199.99, 199.99, '2024-04-03', 'North America', 'Sales Team A'),
    (6, 5, 1, 89.99, 89.99, '2024-04-08', 'North America', 'Sales Team A'),
    (7, 1, 3, 79.99, 239.97, '2024-04-15', 'Asia Pacific', 'Sales Team D'),
    (8, 6, 2, 59.99, 119.98, '2024-04-22', 'Asia Pacific', 'Sales Team D'),
    (2, 3, 1, 129.99, 129.99, '2024-04-28', 'North America', 'Sales Team B');

-- -----------------------------------------------------------------------------
-- Monthly Metrics
-- -----------------------------------------------------------------------------
INSERT INTO monthly_metrics (month, total_revenue, total_orders, unique_customers, avg_order_value, top_product_id) VALUES
    ('2024-01-01', 709.92, 5, 5, 141.98, 2),
    ('2024-02-01', 564.91, 5, 5, 112.98, 1),
    ('2024-03-01', 494.89, 5, 5, 98.98, 3),
    ('2024-04-01', 779.92, 5, 5, 155.98, 1);

-- -----------------------------------------------------------------------------
-- Web Analytics
-- -----------------------------------------------------------------------------
INSERT INTO web_analytics (date, page_views, unique_visitors, bounce_rate, avg_session_duration, conversions, source) VALUES
    ('2024-01-01', 1250, 890, 42.5, 185, 45, 'organic'),
    ('2024-01-01', 650, 520, 55.2, 120, 18, 'paid'),
    ('2024-01-01', 320, 280, 38.1, 210, 22, 'social'),
    ('2024-02-01', 1480, 1050, 40.2, 195, 52, 'organic'),
    ('2024-02-01', 720, 580, 52.8, 130, 21, 'paid'),
    ('2024-02-01', 410, 350, 35.5, 225, 28, 'social'),
    ('2024-03-01', 1620, 1180, 38.8, 205, 58, 'organic'),
    ('2024-03-01', 850, 680, 50.1, 140, 25, 'paid'),
    ('2024-03-01', 520, 440, 33.2, 240, 35, 'social'),
    ('2024-04-01', 1890, 1350, 36.5, 215, 68, 'organic'),
    ('2024-04-01', 920, 740, 48.5, 150, 30, 'paid'),
    ('2024-04-01', 680, 560, 31.8, 255, 42, 'social');

RESET search_path;

\echo 'Seeded demo tenant data (B2C retail)'
