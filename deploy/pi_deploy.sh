#!/usr/bin/env bash
# Deploy the Stripe service to Raspberry Pi nodes.
# Usage: ./deploy/pi_deploy.sh [pi-host] [pi-host2] ...
# Example: ./deploy/pi_deploy.sh 192.168.1.100 192.168.1.101 192.168.1.102
set -euo pipefail

SERVICE_NAME="blackroad-stripe"
DEPLOY_DIR="/opt/${SERVICE_NAME}"
SERVICE_USER="blackroad"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ $# -eq 0 ]; then
    echo "Usage: $0 <pi-host> [pi-host2] ..."
    echo "  Deploys the Stripe service to one or more Raspberry Pi nodes."
    echo "  Each host should be reachable via SSH (e.g., pi@192.168.1.100)"
    exit 1
fi

PI_HOSTS=("$@")

echo "=== BlackRoad Stripe Service — Pi Deployment ==="
echo "Deploying to ${#PI_HOSTS[@]} node(s): ${PI_HOSTS[*]}"

for HOST in "${PI_HOSTS[@]}"; do
    echo ""
    echo "── Deploying to ${HOST} ──────────────────────────"

    # Create deploy directory and service user
    ssh "${HOST}" "sudo mkdir -p ${DEPLOY_DIR} && sudo useradd -r -s /bin/false ${SERVICE_USER} 2>/dev/null || true"

    # Sync code
    rsync -avz --delete \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='.env' \
        --exclude='*.pyc' \
        --exclude='cqr_kvret_*' \
        --exclude='dialog2-crop.png' \
        "${REPO_ROOT}/" "${HOST}:${DEPLOY_DIR}/"

    # Install dependencies and set up venv
    ssh "${HOST}" "cd ${DEPLOY_DIR} && python3 -m venv venv && venv/bin/pip install -r requirements.txt"

    # Deploy systemd service
    ssh "${HOST}" "sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null" <<UNIT
[Unit]
Description=BlackRoad Stripe Payment Service
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${DEPLOY_DIR}
EnvironmentFile=${DEPLOY_DIR}/.env
ExecStart=${DEPLOY_DIR}/venv/bin/python -m stripe_service
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

    # Enable and restart
    ssh "${HOST}" "sudo systemctl daemon-reload && sudo systemctl enable ${SERVICE_NAME} && sudo systemctl restart ${SERVICE_NAME}"

    echo "  ✓ Deployed to ${HOST}"
    ssh "${HOST}" "sudo systemctl status ${SERVICE_NAME} --no-pager" || true
done

echo ""
echo "=== Deployment complete to ${#PI_HOSTS[@]} node(s) ==="
echo "Don't forget to copy .env to ${DEPLOY_DIR}/.env on each Pi!"
