#!/usr/bin/env bash
# Fëanor local MVP installer.
# Sets up .env, builds Docker images, starts the stack, and installs the CLI.
set -euo pipefail

# ── Helpers ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${BLUE}[info]${RESET}  $*"; }
ok()      { echo -e "${GREEN}[ok]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[warn]${RESET}  $*"; }
die()     { echo -e "${RED}[error]${RESET} $*" >&2; exit 1; }
header()  { echo -e "\n${BOLD}── $* ──${RESET}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Prerequisites ──────────────────────────────────────────────────────────────
header "Checking prerequisites"

command -v docker   &>/dev/null || die "docker is required but not found."
command -v python3  &>/dev/null || die "python3 is required but not found."

if docker compose version &>/dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE="docker-compose"
else
    die "Docker Compose not found. Install the Docker Compose plugin or standalone docker-compose."
fi

docker info &>/dev/null || die "Docker daemon is not running. Start Docker and retry."

SKIP_PIXI=0
if command -v pixi &>/dev/null; then
    ok "pixi $(pixi --version)"
else
    warn "pixi not found — SDK install step will be skipped."
    warn "Install pixi from https://pixi.sh to use the feanor CLI."
    SKIP_PIXI=1
fi

ok "Prerequisites satisfied."

# ── .env ──────────────────────────────────────────────────────────────────────
header "Environment file"

if [[ -f .env ]]; then
    warn ".env already exists — keeping it. Delete and re-run to regenerate."
else
    cp .env.example .env

    # Fernet key = 32 random bytes, base64url-encoded (stdlib only, no extras needed).
    FERNET_KEY=$(python3 -c \
        "import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")

    # sed -i differs between GNU (Linux) and BSD (macOS).
    if sed --version &>/dev/null 2>&1; then
        sed -i "s|AIRFLOW_FERNET_KEY=REPLACE_WITH_GENERATED_FERNET_KEY|AIRFLOW_FERNET_KEY=${FERNET_KEY}|" .env
    else
        sed -i '' "s|AIRFLOW_FERNET_KEY=REPLACE_WITH_GENERATED_FERNET_KEY|AIRFLOW_FERNET_KEY=${FERNET_KEY}|" .env
    fi

    ok ".env created with a generated Fernet key."
fi

# ── Build images ───────────────────────────────────────────────────────────────
header "Building Docker images"
info "Building api and airflow images (this may take a few minutes the first time)..."
$COMPOSE --project-name feanor build api airflow-webserver
ok "Images built."

# ── Start the stack ────────────────────────────────────────────────────────────
header "Starting the stack"
$COMPOSE --project-name feanor up -d
ok "Services started."

# ── Wait for health ────────────────────────────────────────────────────────────
header "Waiting for services"

# Polls Docker's health status for a named service.
# Usage: wait_healthy <service> <max_wait_seconds>
wait_healthy() {
    local service="$1"
    local max_s="${2:-120}"
    local elapsed=0
    local interval=5

    printf "  %-24s" "$service"
    while [[ $elapsed -lt $max_s ]]; do
        local health
        health=$(docker inspect \
            --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
            "feanor-${service}-1" 2>/dev/null || echo "missing")

        case "$health" in
            healthy) echo -e " ${GREEN}healthy${RESET}"; return 0 ;;
            none)    echo -e " ${YELLOW}no healthcheck — assuming up${RESET}"; return 0 ;;
        esac

        printf "."
        sleep $interval
        (( elapsed += interval ))
    done

    echo -e " ${RED}timed out after ${max_s}s${RESET}"
    warn "  Run '$COMPOSE --project-name feanor logs $service' to investigate."
    return 1
}

# Keycloak and Airflow are slow starters — give them generous windows.
wait_healthy postgres          60
wait_healthy minio             60
wait_healthy keycloak         200
wait_healthy api               90
wait_healthy trino            150
wait_healthy airflow-webserver 180

ok "All services healthy."

# ── Install feanor CLI ─────────────────────────────────────────────────────────
if [[ $SKIP_PIXI -eq 0 ]]; then
    header "Installing feanor CLI"
    pixi install
    ok "feanor CLI installed. Use: pixi run feanor <command>"
    FEANOR_CMD="pixi run feanor"
else
    FEANOR_CMD="feanor  # (install pixi first: https://pixi.sh)"
fi

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  Fëanor local MVP is running.${RESET}"
echo -e "${BOLD}${GREEN}══════════════════════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${BOLD}Service URLs${RESET}"
echo -e "  API / Traefik       http://localhost:8000"
echo -e "  API docs            http://localhost:8000/docs"
echo -e "  Keycloak            http://localhost:8080   admin / changeme"
echo -e "  MinIO console       http://localhost:9001   minioadmin / changeme"
echo -e "  Trino               http://localhost:18080"
echo -e "  Airflow             http://localhost:8090   admin / admin"
echo -e "  Traefik dashboard   http://localhost:8081"
echo ""
echo -e "  ${BOLD}Next steps${RESET}"
echo -e "  1.  ${BOLD}${FEANOR_CMD} login${RESET}"
echo -e "  2.  ${BOLD}${FEANOR_CMD} system health${RESET}"
echo -e "  3.  Read TUTORIAL.md"
echo ""
