#!/usr/bin/env bash
# Applies the feanor realm configuration to a running Keycloak instance via
# the Admin REST API. Idempotent: deletes and recreates the realm on each run.
#
# Usage:
#   ./keycloak/configure-realm.sh
#   KEYCLOAK_URL=http://myhost:8080 ./keycloak/configure-realm.sh
#
# Requires: curl, python3
set -euo pipefail

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8080}"
ADMIN_USER="${KEYCLOAK_ADMIN:-admin}"
ADMIN_PASS="${KEYCLOAK_ADMIN_PASSWORD:-changeme}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REALM_JSON="$SCRIPT_DIR/feanor-realm.json"

json_field() {
  python3 -c "import sys,json; print(json.load(sys.stdin)$1)"
}

echo "Connecting to $KEYCLOAK_URL ..."

# --- Admin token (master realm) ---
TOKEN=$(curl -sf -X POST "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&client_id=admin-cli&username=$ADMIN_USER&password=$ADMIN_PASS" \
  | json_field "['access_token']")

AUTH="Authorization: Bearer $TOKEN"

# --- Drop and recreate the feanor realm ---
echo "Removing existing 'feanor' realm (if present)..."
curl -sf -X DELETE "$KEYCLOAK_URL/admin/realms/feanor" -H "$AUTH" 2>/dev/null || true

echo "Importing feanor-realm.json ..."
curl -sf -X POST "$KEYCLOAK_URL/admin/realms" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d @"$REALM_JSON"

# --- Assign service_account role to the airflow-sa service account user ---
# The user is created by Keycloak when serviceAccountsEnabled=true on the client,
# but role mapping from the realm JSON import isn't always applied. Re-apply here.
AIRFLOW_CLIENT_UUID=$(curl -sf "$KEYCLOAK_URL/admin/realms/feanor/clients?clientId=airflow-sa" \
  -H "$AUTH" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

SA_USER_ID=$(curl -sf "$KEYCLOAK_URL/admin/realms/feanor/clients/$AIRFLOW_CLIENT_UUID/service-account-user" \
  -H "$AUTH" | json_field "['id']")

SA_ROLE=$(curl -sf "$KEYCLOAK_URL/admin/realms/feanor/roles/service_account" -H "$AUTH")

curl -sf -X POST "$KEYCLOAK_URL/admin/realms/feanor/users/$SA_USER_ID/role-mappings/realm" \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d "[$SA_ROLE]"

echo ""
echo "Done. Realm 'feanor' configured:"
echo "  Roles:   platform_admin, engineer, analyst, service_account"
echo "  Users:   admin@feanor.local, engineer@feanor.local, analyst@feanor.local"
echo "  Clients: feanor-cli (device flow), feanor-sdk (PKCE), airflow-sa (client creds)"
