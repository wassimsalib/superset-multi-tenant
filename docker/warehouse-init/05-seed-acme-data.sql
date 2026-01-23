-- =============================================================================
-- Seed Acme Tenant Data
-- =============================================================================
-- Sample data for the "acme" tenant - a B2B enterprise software company
-- NOTE: Completely different data patterns from demo tenant!

SET search_path TO tenant_acme, public;

-- -----------------------------------------------------------------------------
-- Customers (B2B enterprise clients)
-- -----------------------------------------------------------------------------
INSERT INTO customers (customer_name, email, company, industry, country) VALUES
    ('John Mitchell', 'j.mitchell@techcorp.com', 'TechCorp Industries', 'Technology', 'USA'),
    ('Sarah Connor', 's.connor@globalbank.com', 'Global Bank Holdings', 'Finance', 'UK'),
    ('Mike Zhang', 'm.zhang@healthplus.com', 'HealthPlus Medical', 'Healthcare', 'USA'),
    ('Emma Thompson', 'e.thompson@retailgiant.com', 'RetailGiant Inc', 'Retail', 'Canada'),
    ('Carlos Rodriguez', 'c.rodriguez@energia.mx', 'Energia Nacional', 'Energy', 'Mexico'),
    ('Yuki Tanaka', 'y.tanaka@automotiveco.jp', 'Automotive Co Japan', 'Automotive', 'Japan'),
    ('Hans Mueller', 'h.mueller@manufactura.de', 'Manufactura GmbH', 'Manufacturing', 'Germany'),
    ('Lisa Park', 'l.park@cloudservices.kr', 'CloudServices Korea', 'Technology', 'South Korea');

-- -----------------------------------------------------------------------------
-- Products (Enterprise software licenses)
-- -----------------------------------------------------------------------------
INSERT INTO products (product_name, category, price, cost) VALUES
    ('Enterprise Platform License', 'Software', 50000.00, 5000.00),
    ('Professional Tier - Annual', 'Subscription', 12000.00, 1200.00),
    ('Data Analytics Module', 'Add-on', 8000.00, 800.00),
    ('API Gateway License', 'Software', 15000.00, 1500.00),
    ('24/7 Premium Support', 'Services', 20000.00, 8000.00),
    ('Implementation Services', 'Services', 35000.00, 20000.00),
    ('Training Package', 'Services', 5000.00, 2000.00),
    ('Security Compliance Add-on', 'Add-on', 10000.00, 1000.00);

-- -----------------------------------------------------------------------------
-- Sales (2024 B2B contracts - much higher values!)
-- -----------------------------------------------------------------------------
INSERT INTO sales (customer_id, product_id, quantity, unit_price, total_amount, sale_date, region, sales_rep) VALUES
    -- Q1 2024 - Big enterprise deals
    (1, 1, 1, 50000.00, 50000.00, '2024-01-15', 'North America', 'Enterprise Team'),
    (1, 5, 1, 20000.00, 20000.00, '2024-01-15', 'North America', 'Enterprise Team'),
    (1, 6, 1, 35000.00, 35000.00, '2024-01-20', 'North America', 'Enterprise Team'),
    (2, 1, 1, 50000.00, 50000.00, '2024-02-01', 'EMEA', 'EMEA Sales'),
    (2, 3, 2, 8000.00, 16000.00, '2024-02-01', 'EMEA', 'EMEA Sales'),
    (2, 8, 1, 10000.00, 10000.00, '2024-02-10', 'EMEA', 'EMEA Sales'),
    (3, 2, 5, 12000.00, 60000.00, '2024-02-20', 'North America', 'Healthcare Team'),
    (3, 7, 3, 5000.00, 15000.00, '2024-02-25', 'North America', 'Healthcare Team'),
    (4, 1, 1, 50000.00, 50000.00, '2024-03-05', 'North America', 'Retail Team'),
    (4, 4, 1, 15000.00, 15000.00, '2024-03-10', 'North America', 'Retail Team'),
    -- Q2 2024
    (5, 2, 3, 12000.00, 36000.00, '2024-04-01', 'LATAM', 'LATAM Sales'),
    (5, 5, 1, 20000.00, 20000.00, '2024-04-05', 'LATAM', 'LATAM Sales'),
    (6, 1, 1, 50000.00, 50000.00, '2024-04-15', 'APAC', 'APAC Enterprise'),
    (6, 6, 1, 35000.00, 35000.00, '2024-04-20', 'APAC', 'APAC Enterprise'),
    (7, 2, 10, 12000.00, 120000.00, '2024-05-01', 'EMEA', 'EMEA Sales'),
    (7, 3, 5, 8000.00, 40000.00, '2024-05-10', 'EMEA', 'EMEA Sales'),
    (8, 1, 1, 50000.00, 50000.00, '2024-05-20', 'APAC', 'APAC Enterprise'),
    (8, 4, 2, 15000.00, 30000.00, '2024-05-25', 'APAC', 'APAC Enterprise');

-- -----------------------------------------------------------------------------
-- Monthly Metrics (Enterprise scale)
-- -----------------------------------------------------------------------------
INSERT INTO monthly_metrics (month, total_revenue, total_orders, unique_customers, avg_order_value, top_product_id) VALUES
    ('2024-01-01', 105000.00, 3, 1, 35000.00, 1),
    ('2024-02-01', 151000.00, 5, 2, 30200.00, 2),
    ('2024-03-01', 65000.00, 2, 1, 32500.00, 1),
    ('2024-04-01', 141000.00, 4, 2, 35250.00, 1),
    ('2024-05-01', 240000.00, 4, 2, 60000.00, 2);

-- -----------------------------------------------------------------------------
-- Web Analytics (B2B patterns - lower volume, higher quality)
-- -----------------------------------------------------------------------------
INSERT INTO web_analytics (date, page_views, unique_visitors, bounce_rate, avg_session_duration, conversions, source) VALUES
    ('2024-01-01', 450, 320, 28.5, 420, 8, 'organic'),
    ('2024-01-01', 280, 210, 35.2, 380, 5, 'linkedin'),
    ('2024-01-01', 120, 95, 22.1, 510, 4, 'referral'),
    ('2024-02-01', 520, 380, 26.2, 440, 12, 'organic'),
    ('2024-02-01', 340, 260, 32.8, 395, 7, 'linkedin'),
    ('2024-02-01', 150, 115, 20.5, 540, 6, 'referral'),
    ('2024-03-01', 610, 450, 24.8, 460, 15, 'organic'),
    ('2024-03-01', 420, 320, 30.1, 410, 9, 'linkedin'),
    ('2024-03-01', 180, 140, 18.2, 580, 8, 'referral'),
    ('2024-04-01', 720, 530, 22.5, 485, 18, 'organic'),
    ('2024-04-01', 510, 390, 28.5, 425, 11, 'linkedin'),
    ('2024-04-01', 220, 170, 16.8, 610, 10, 'referral'),
    ('2024-05-01', 850, 620, 20.8, 505, 22, 'organic'),
    ('2024-05-01', 620, 470, 26.2, 445, 14, 'linkedin'),
    ('2024-05-01', 280, 210, 15.5, 640, 12, 'referral');

RESET search_path;

\echo 'Seeded acme tenant data (B2B enterprise)'
