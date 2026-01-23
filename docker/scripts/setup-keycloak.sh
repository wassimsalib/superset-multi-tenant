#!/bin/bash
# =============================================================================
# Keycloak Setup Script for Multi-Tenant Superset
# =============================================================================
# Creates realms, clients, and test users for demo and acme tenants
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_DIR/docker-compose-multitenant.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8180}"
KEYCLOAK_ADMIN="${KEYCLOAK_ADMIN:-admin}"
KEYCLOAK_ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-admin}"

# Superset callback URLs (adjust ports as needed)
SUPERSET_BASE_URL="${SUPERSET_BASE_URL:-http://localhost:80}"

echo "============================================"
echo "Keycloak Multi-Tenant Setup"
echo "============================================"
echo ""
echo "Keycloak URL: $KEYCLOAK_URL"
echo ""

# -----------------------------------------------------------------------------
# Get admin token
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[1/5]${NC} Getting admin access token..."

TOKEN=$(curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${KEYCLOAK_ADMIN}" \
  -d "password=${KEYCLOAK_ADMIN_PASSWORD}" \
  -d "grant_type=password" \
  -d "client_id=admin-cli" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")

if [ -z "$TOKEN" ]; then
    echo -e "${RED}✗${NC} Failed to get admin token. Is Keycloak running?"
    echo "  Try: curl -s ${KEYCLOAK_URL}/health/ready"
    exit 1
fi
echo -e "${GREEN}✓${NC} Got admin token"
echo ""

# -----------------------------------------------------------------------------
# Function to create a realm
# -----------------------------------------------------------------------------
create_realm() {
    local REALM_NAME=$1

    echo -e "${BLUE}Creating realm: ${REALM_NAME}${NC}"

    # Check if realm exists
    EXISTS=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer ${TOKEN}" \
        "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}")

    if [ "$EXISTS" = "200" ]; then
        echo "  Realm already exists, skipping..."
        return 0
    fi

    # Create realm
    curl -s -X POST "${KEYCLOAK_URL}/admin/realms" \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{
            \"realm\": \"${REALM_NAME}\",
            \"enabled\": true,
            \"registrationAllowed\": false,
            \"loginWithEmailAllowed\": true,
            \"duplicateEmailsAllowed\": false,
            \"resetPasswordAllowed\": true,
            \"editUsernameAllowed\": false,
            \"bruteForceProtected\": true
        }"

    echo -e "  ${GREEN}✓${NC} Created realm: ${REALM_NAME}"
}

# -----------------------------------------------------------------------------
# Function to create or update a client (returns the actual secret via global var)
# -----------------------------------------------------------------------------
# Global variable to return client secret
RETURNED_CLIENT_SECRET=""

create_client() {
    local REALM_NAME=$1
    local CLIENT_ID=$2
    local CLIENT_SECRET=$3
    local TENANT_SUBDOMAIN=$4

    echo -e "${BLUE}Setting up client: ${CLIENT_ID} in ${REALM_NAME}${NC}"

    # Check if client already exists
    local CLIENT_UUID=$(curl -s -H "Authorization: Bearer ${TOKEN}" \
        "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/clients?clientId=${CLIENT_ID}" \
        | python3 -c "import sys, json; clients=json.load(sys.stdin); print(clients[0]['id'] if clients else '')")

    if [ -n "$CLIENT_UUID" ]; then
        echo "  Client already exists, regenerating secret..."

        # Regenerate the client secret in Keycloak
        local SECRET_RESPONSE=$(curl -s -X POST \
            -H "Authorization: Bearer ${TOKEN}" \
            "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/clients/${CLIENT_UUID}/client-secret")

        # Get the new secret
        RETURNED_CLIENT_SECRET=$(curl -s -H "Authorization: Bearer ${TOKEN}" \
            "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/clients/${CLIENT_UUID}/client-secret" \
            | python3 -c "import sys, json; print(json.load(sys.stdin).get('value', ''))")

        echo -e "  ${GREEN}✓${NC} Regenerated secret for client: ${CLIENT_ID}"
    else
        # Create new client
        curl -s -X POST "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/clients" \
            -H "Authorization: Bearer ${TOKEN}" \
            -H "Content-Type: application/json" \
            -d "{
                \"clientId\": \"${CLIENT_ID}\",
                \"enabled\": true,
                \"protocol\": \"openid-connect\",
                \"publicClient\": false,
                \"secret\": \"${CLIENT_SECRET}\",
                \"redirectUris\": [
                    \"http://${TENANT_SUBDOMAIN}.app.localhost/*\",
                    \"http://${TENANT_SUBDOMAIN}.app.localhost:80/*\",
                    \"http://localhost/*\",
                    \"http://localhost:8088/*\"
                ],
                \"webOrigins\": [
                    \"http://${TENANT_SUBDOMAIN}.app.localhost\",
                    \"http://${TENANT_SUBDOMAIN}.app.localhost:80\",
                    \"http://localhost\",
                    \"http://localhost:8088\"
                ],
                \"standardFlowEnabled\": true,
                \"implicitFlowEnabled\": false,
                \"directAccessGrantsEnabled\": true,
                \"serviceAccountsEnabled\": false,
                \"authorizationServicesEnabled\": false,
                \"fullScopeAllowed\": true,
                \"defaultClientScopes\": [\"email\", \"profile\"]
            }"

        RETURNED_CLIENT_SECRET="$CLIENT_SECRET"
        echo -e "  ${GREEN}✓${NC} Created client: ${CLIENT_ID}"
    fi
}

# -----------------------------------------------------------------------------
# Function to create a user
# -----------------------------------------------------------------------------
create_user() {
    local REALM_NAME=$1
    local USERNAME=$2
    local EMAIL=$3
    local PASSWORD=$4
    local FIRST_NAME=$5
    local LAST_NAME=$6

    echo -e "${BLUE}Creating user: ${USERNAME} in ${REALM_NAME}${NC}"

    # Create user
    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/users" \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{
            \"username\": \"${USERNAME}\",
            \"email\": \"${EMAIL}\",
            \"emailVerified\": true,
            \"enabled\": true,
            \"firstName\": \"${FIRST_NAME}\",
            \"lastName\": \"${LAST_NAME}\",
            \"credentials\": [{
                \"type\": \"password\",
                \"value\": \"${PASSWORD}\",
                \"temporary\": false
            }]
        }")

    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

    if [ "$HTTP_CODE" = "201" ]; then
        echo -e "  ${GREEN}✓${NC} Created user: ${USERNAME}"
    elif [ "$HTTP_CODE" = "409" ]; then
        echo "  User already exists, skipping..."
    else
        echo -e "  ${YELLOW}Warning:${NC} Unexpected response: ${HTTP_CODE}"
    fi
}

# -----------------------------------------------------------------------------
# Function to create a group
# -----------------------------------------------------------------------------
create_group() {
    local REALM_NAME=$1
    local GROUP_NAME=$2

    echo -e "${BLUE}Creating group: ${GROUP_NAME} in ${REALM_NAME}${NC}"

    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/groups" \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"${GROUP_NAME}\"}")

    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

    if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "409" ]; then
        echo -e "  ${GREEN}✓${NC} Group ready: ${GROUP_NAME}"
    else
        echo -e "  ${YELLOW}Warning:${NC} Group creation response: ${HTTP_CODE}"
    fi
}

# -----------------------------------------------------------------------------
# Function to add user to group
# -----------------------------------------------------------------------------
add_user_to_group() {
    local REALM_NAME=$1
    local USERNAME=$2
    local GROUP_NAME=$3

    echo -e "${BLUE}Adding ${USERNAME} to group ${GROUP_NAME}${NC}"

    # Get user ID
    USER_ID=$(curl -s -H "Authorization: Bearer ${TOKEN}" \
        "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/users?username=${USERNAME}" \
        | python3 -c "import sys, json; users=json.load(sys.stdin); print(users[0]['id'] if users else '')")

    if [ -z "$USER_ID" ]; then
        echo -e "  ${YELLOW}Warning:${NC} User ${USERNAME} not found"
        return 1
    fi

    # Get group ID
    GROUP_ID=$(curl -s -H "Authorization: Bearer ${TOKEN}" \
        "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/groups?search=${GROUP_NAME}" \
        | python3 -c "import sys, json; groups=json.load(sys.stdin); print(groups[0]['id'] if groups else '')")

    if [ -z "$GROUP_ID" ]; then
        echo -e "  ${YELLOW}Warning:${NC} Group ${GROUP_NAME} not found"
        return 1
    fi

    # Add user to group
    curl -s -X PUT "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/users/${USER_ID}/groups/${GROUP_ID}" \
        -H "Authorization: Bearer ${TOKEN}"

    echo -e "  ${GREEN}✓${NC} Added ${USERNAME} to ${GROUP_NAME}"
}

# -----------------------------------------------------------------------------
# Function to add group mapper to client (includes groups in token)
# -----------------------------------------------------------------------------
add_group_mapper() {
    local REALM_NAME=$1
    local CLIENT_ID=$2

    echo -e "${BLUE}Adding group mapper to client ${CLIENT_ID}${NC}"

    # Get client internal ID
    CLIENT_UUID=$(curl -s -H "Authorization: Bearer ${TOKEN}" \
        "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/clients?clientId=${CLIENT_ID}" \
        | python3 -c "import sys, json; clients=json.load(sys.stdin); print(clients[0]['id'] if clients else '')")

    if [ -z "$CLIENT_UUID" ]; then
        echo -e "  ${YELLOW}Warning:${NC} Client ${CLIENT_ID} not found"
        return 1
    fi

    # Add protocol mapper for groups
    curl -s -X POST "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/clients/${CLIENT_UUID}/protocol-mappers/models" \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"groups\",
            \"protocol\": \"openid-connect\",
            \"protocolMapper\": \"oidc-group-membership-mapper\",
            \"consentRequired\": false,
            \"config\": {
                \"full.path\": \"false\",
                \"id.token.claim\": \"true\",
                \"access.token.claim\": \"true\",
                \"claim.name\": \"groups\",
                \"userinfo.token.claim\": \"true\"
            }
        }"

    echo -e "  ${GREEN}✓${NC} Added group mapper to ${CLIENT_ID}"
}

# -----------------------------------------------------------------------------
# Function to setup all groups for a realm
# -----------------------------------------------------------------------------
setup_realm_groups() {
    local REALM_NAME=$1

    echo -e "${BLUE}Setting up Superset role groups in ${REALM_NAME}${NC}"

    # Create groups that map to Superset roles
    create_group "${REALM_NAME}" "superset-admin"
    create_group "${REALM_NAME}" "superset-alpha"
    create_group "${REALM_NAME}" "superset-gamma"
    create_group "${REALM_NAME}" "superset-sql-lab"
}

# -----------------------------------------------------------------------------
# Setup Demo Tenant
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[2/5]${NC} Setting up Demo tenant realm..."

DEMO_CLIENT_SECRET_INITIAL="demo-secret-$(openssl rand -hex 8)"

create_realm "demo-realm"
create_client "demo-realm" "superset-demo" "$DEMO_CLIENT_SECRET_INITIAL" "demo"
# Use the actual secret from Keycloak (either newly created or regenerated)
DEMO_CLIENT_SECRET="$RETURNED_CLIENT_SECRET"
setup_realm_groups "demo-realm"
add_group_mapper "demo-realm" "superset-demo"
create_user "demo-realm" "demo-admin" "admin@demo.local" "demo123" "Demo" "Admin"
create_user "demo-realm" "demo-user" "user@demo.local" "demo123" "Demo" "User"
# Assign users to groups (admin gets full access, user gets viewer access)
add_user_to_group "demo-realm" "demo-admin" "superset-admin"
add_user_to_group "demo-realm" "demo-user" "superset-gamma"

echo ""

# -----------------------------------------------------------------------------
# Setup Acme Tenant
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[3/5]${NC} Setting up Acme tenant realm..."

ACME_CLIENT_SECRET_INITIAL="acme-secret-$(openssl rand -hex 8)"

create_realm "acme-realm"
create_client "acme-realm" "superset-acme" "$ACME_CLIENT_SECRET_INITIAL" "acme"
# Use the actual secret from Keycloak (either newly created or regenerated)
ACME_CLIENT_SECRET="$RETURNED_CLIENT_SECRET"
setup_realm_groups "acme-realm"
add_group_mapper "acme-realm" "superset-acme"
create_user "acme-realm" "acme-admin" "admin@acme.local" "acme123" "Acme" "Admin"
create_user "acme-realm" "acme-user" "user@acme.local" "acme123" "Acme" "User"
# Assign users to groups (admin gets full access, user gets viewer access)
add_user_to_group "acme-realm" "acme-admin" "superset-admin"
add_user_to_group "acme-realm" "acme-user" "superset-gamma"

echo ""

# -----------------------------------------------------------------------------
# Create/Update Superset tenant records
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[4/5]${NC} Creating/updating Superset tenant records..."

docker compose -f "$COMPOSE_FILE" exec superset python3 -c "
import sys
sys.path.insert(0, '/app/docker/pythonpath_dev')
from superset import create_app, db
app = create_app()
with app.app_context():
    from keycloak_multi_tenant.models import Tenant

    # Demo tenant - create or update
    demo = db.session.query(Tenant).filter_by(tenant_id='demo').first()
    if not demo:
        demo = Tenant(
            tenant_id='demo',
            name='Demo Company',
            subdomain='demo',
            keycloak_realm='demo-realm',
            keycloak_client_id='superset-demo',
            keycloak_client_secret='${DEMO_CLIENT_SECRET}'
        )
        db.session.add(demo)
        print('Created demo tenant')
    else:
        demo.set_encrypted_secret('${DEMO_CLIENT_SECRET}')
        print('Updated demo tenant secret')

    # Acme tenant - create or update
    acme = db.session.query(Tenant).filter_by(tenant_id='acme').first()
    if not acme:
        acme = Tenant(
            tenant_id='acme',
            name='Acme Corporation',
            subdomain='acme',
            keycloak_realm='acme-realm',
            keycloak_client_id='superset-acme',
            keycloak_client_secret='${ACME_CLIENT_SECRET}'
        )
        db.session.add(acme)
        print('Created acme tenant')
    else:
        acme.set_encrypted_secret('${ACME_CLIENT_SECRET}')
        print('Updated acme tenant secret')

    db.session.commit()
    print('Tenant records ready!')
"

echo -e "${GREEN}✓${NC} Tenant records created/updated in Superset"
echo ""

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[5/5]${NC} Setup complete!"
echo ""
echo "============================================"
echo -e "${GREEN}Keycloak Setup Complete!${NC}"
echo "============================================"
echo ""
echo "Keycloak Admin Console:"
echo "  URL: ${KEYCLOAK_URL}"
echo "  Username: ${KEYCLOAK_ADMIN}"
echo "  Password: ${KEYCLOAK_ADMIN_PASSWORD}"
echo ""
echo "Demo Tenant (demo-realm):"
echo "  Superset URL: http://demo.app.localhost"
echo "  Test Users:"
echo "    - demo-admin / demo123"
echo "    - demo-user / demo123"
echo ""
echo "Acme Tenant (acme-realm):"
echo "  Superset URL: http://acme.app.localhost"
echo "  Test Users:"
echo "    - acme-admin / acme123"
echo "    - acme-user / acme123"
echo ""
echo "Make sure your /etc/hosts has:"
echo "  127.0.0.1 demo.app.localhost"
echo "  127.0.0.1 acme.app.localhost"
echo "  127.0.0.1 host.docker.internal"
echo "============================================"
