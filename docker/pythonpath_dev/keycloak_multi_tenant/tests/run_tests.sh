#!/bin/bash
# Run multi-tenant isolation tests
#
# Usage:
#   # From host machine:
#   docker compose exec superset bash /app/docker/pythonpath_dev/keycloak_multi_tenant/tests/run_tests.sh
#
#   # Or run specific test files:
#   docker compose exec superset pytest /app/docker/pythonpath_dev/keycloak_multi_tenant/tests/test_startup.py -v
#   docker compose exec superset pytest /app/docker/pythonpath_dev/keycloak_multi_tenant/tests/test_rls.py -v
#   docker compose exec superset pytest /app/docker/pythonpath_dev/keycloak_multi_tenant/tests/test_security.py -v

set -e

TESTS_DIR="/app/docker/pythonpath_dev/keycloak_multi_tenant/tests"

echo "=========================================="
echo "Multi-Tenant Isolation Tests"
echo "=========================================="
echo ""

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo "ERROR: pytest not found. Install with: pip install pytest"
    exit 1
fi

# Run tests in order: startup first, then others
echo "1. Running startup verification tests..."
echo "   (These check basic setup: tables, tenants, RLS enabled)"
echo ""
pytest "$TESTS_DIR/test_startup.py" -v --tb=short
echo ""

echo "2. Running metadata isolation tests..."
echo "   (These check tenant context management)"
echo ""
pytest "$TESTS_DIR/test_metadata_isolation.py" -v --tb=short
echo ""

echo "3. Running RLS policy tests..."
echo "   (These check PostgreSQL Row-Level Security)"
echo ""
pytest "$TESTS_DIR/test_rls.py" -v --tb=short
echo ""

echo "4. Running security tests..."
echo "   (These check cross-tenant isolation guarantees)"
echo ""
pytest "$TESTS_DIR/test_security.py" -v --tb=short
echo ""

echo "=========================================="
echo "All tests completed!"
echo "=========================================="
