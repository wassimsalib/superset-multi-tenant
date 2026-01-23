#!/bin/bash
# =============================================================================
# Multi-Tenant Superset Startup Script
# =============================================================================
# One command to start everything: Superset, Keycloak, and sample tenants
# =============================================================================
set -e

cd "$(dirname "$0")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

TOTAL_STEPS=5
if [ "$1" = "--create-samples" ]; then
    TOTAL_STEPS=6
fi

echo "============================================"
echo "Multi-Tenant Superset Startup"
echo "============================================"
echo ""

# Step 1: Generate encryption key if not set
echo -e "${YELLOW}[1/${TOTAL_STEPS}]${NC} Checking encryption key..."
if grep -q "^TENANT_SECRET_ENCRYPTION_KEY=.\+" docker/.env 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Encryption key already set"
else
    echo "Generating new encryption key..."
    # Try uv first, fall back to direct python
    if command -v uv &> /dev/null; then
        KEY=$(uv run --no-project --with cryptography python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null)
    else
        KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || true)
    fi

    if [ -z "$KEY" ]; then
        echo -e "${YELLOW}!${NC} Could not generate key (cryptography not installed)"
        echo "  Continuing without encryption (secrets stored in plaintext - fine for dev)"
    else
        if grep -q "^TENANT_SECRET_ENCRYPTION_KEY=" docker/.env 2>/dev/null; then
            sed -i.bak "s|^TENANT_SECRET_ENCRYPTION_KEY=.*|TENANT_SECRET_ENCRYPTION_KEY=$KEY|" docker/.env
            rm -f docker/.env.bak
        else
            echo "TENANT_SECRET_ENCRYPTION_KEY=$KEY" >> docker/.env
        fi
        echo -e "${GREEN}✓${NC} Generated and saved encryption key"
    fi
fi
echo ""

# Step 2: Start all containers (Superset, Keycloak, DB, etc.)
echo -e "${YELLOW}[2/${TOTAL_STEPS}]${NC} Starting containers..."
# Remove any standalone keycloak container that might conflict
docker rm -f superset_keycloak 2>/dev/null || true
docker compose -f docker-compose-multitenant.yml up -d
echo -e "${GREEN}✓${NC} Containers started"
echo ""

# Step 3: Wait for Keycloak to be ready
echo -e "${YELLOW}[3/${TOTAL_STEPS}]${NC} Waiting for Keycloak..."
for i in {1..90}; do
    if curl -s http://localhost:8180/realms/master 2>/dev/null | grep -q "master"; then
        echo -e "${GREEN}✓${NC} Keycloak is ready"
        break
    fi
    if [ $i -eq 90 ]; then
        echo -e "${RED}✗${NC} Timeout waiting for Keycloak"
        echo "  Check: docker compose -f docker-compose-multitenant.yml logs keycloak"
        exit 1
    fi
    echo -n "."
    sleep 2
done
echo ""

# Step 4: Wait for Superset to be ready
echo -e "${YELLOW}[4/${TOTAL_STEPS}]${NC} Waiting for Superset..."
for i in {1..90}; do
    if curl -s http://localhost:8088/health 2>/dev/null | grep -q "OK"; then
        echo -e "${GREEN}✓${NC} Superset is ready"
        break
    fi
    if [ $i -eq 90 ]; then
        echo -e "${RED}✗${NC} Timeout waiting for Superset"
        echo "  Check: docker compose -f docker-compose-multitenant.yml logs superset"
        exit 1
    fi
    echo -n "."
    sleep 2
done
echo ""

# Step 5: Run migrations
echo -e "${YELLOW}[5/${TOTAL_STEPS}]${NC} Running database migrations..."
docker compose -f docker-compose-multitenant.yml exec -T superset superset db upgrade > /dev/null 2>&1
echo -e "${GREEN}✓${NC} Migrations complete"
echo ""

# Step 6: Full demo bootstrap (if --create-samples)
if [ "$1" = "--create-samples" ]; then
    echo -e "${YELLOW}[6/${TOTAL_STEPS}]${NC} Running full demo bootstrap..."
    echo ""

    # Run demo-bootstrap.sh which handles:
    # - Tenant schemas for metadata isolation
    # - Keycloak realms, clients, users
    # - Warehouse connections
    # - Sample dashboards and charts
    if [ -f "docker/scripts/demo-bootstrap.sh" ]; then
        bash docker/scripts/demo-bootstrap.sh
    else
        echo -e "${RED}✗${NC} demo-bootstrap.sh not found"
        exit 1
    fi
fi

echo ""
echo "============================================"
echo -e "${GREEN}Setup Complete!${NC}"
echo "============================================"
echo ""
echo "Services:"
echo "  Superset:  http://localhost:8088"
echo "  Keycloak:  http://localhost:8180 (admin/admin)"
echo ""

if [ "$1" = "--create-samples" ]; then
    echo "Test URLs:"
    echo "  http://demo.app.localhost  (demo-admin / demo123)"
    echo "  http://acme.app.localhost  (acme-admin / acme123)"
    echo ""
    echo "Make sure /etc/hosts has:"
    echo "  127.0.0.1 demo.app.localhost acme.app.localhost host.docker.internal"
else
    echo "To create sample tenants with Keycloak realms:"
    echo "  ./start-multi-tenant.sh --create-samples"
    echo ""
    echo "Or set up manually:"
    echo "  1. Create Keycloak realm at http://localhost:8180"
    echo "  2. Add tenant at http://localhost:8088/admin/tenant/"
fi
echo "============================================"
