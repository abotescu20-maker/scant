#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Alex Agent SDK — Google Cloud Engine VM Deployment
#
# Creates a GCE VM in europe-west3 (Frankfurt) and sets up:
#   - Claude Code CLI + Agent SDK orchestrator
#   - Cron jobs for all autonomous tasks
#   - systemd service for monitoring
#
# Usage:
#   bash agent-sdk/deploy-gce.sh setup      # Create VM + install everything
#   bash agent-sdk/deploy-gce.sh cron       # Install cron jobs only
#   bash agent-sdk/deploy-gce.sh status     # Check VM status
#   bash agent-sdk/deploy-gce.sh ssh        # SSH into VM
#   bash agent-sdk/deploy-gce.sh destroy    # Delete VM
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────────
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
ZONE="europe-west3-a"
VM_NAME="alex-agent-vm"
MACHINE_TYPE="e2-medium"  # 1 vCPU, 4 GB RAM — $24/mo
IMAGE_FAMILY="ubuntu-2404-lts-amd64"
IMAGE_PROJECT="ubuntu-os-cloud"
DISK_SIZE="30"  # GB

echo "═══════════════════════════════════════════════"
echo "  Alex Agent SDK — GCE Deployment"
echo "  Project: ${PROJECT_ID}"
echo "  Zone: ${ZONE}"
echo "  VM: ${VM_NAME} (${MACHINE_TYPE})"
echo "═══════════════════════════════════════════════"

case "${1:-help}" in

setup)
    echo ""
    echo "📦 Creating VM..."
    gcloud compute instances create "${VM_NAME}" \
        --project="${PROJECT_ID}" \
        --zone="${ZONE}" \
        --machine-type="${MACHINE_TYPE}" \
        --image-family="${IMAGE_FAMILY}" \
        --image-project="${IMAGE_PROJECT}" \
        --boot-disk-size="${DISK_SIZE}GB" \
        --boot-disk-type=pd-balanced \
        --tags=alex-agent \
        --metadata=startup-script='#!/bin/bash
# Auto-install on first boot
apt-get update -qq
apt-get install -y -qq python3-pip python3-venv git curl jq

# Install Claude Code
curl -fsSL https://claude.ai/install.sh | sh

# Create agent user
useradd -m -s /bin/bash alexagent || true

echo "VM ready for agent setup"
'

    echo ""
    echo "⏳ Waiting for VM to boot..."
    sleep 30

    echo ""
    echo "📤 Uploading project files..."
    gcloud compute scp --zone="${ZONE}" --recurse \
        "$(dirname "$0")/.." "alexagent@${VM_NAME}:~/insurance-broker-agent"

    echo ""
    echo "🔧 Configuring VM..."
    gcloud compute ssh --zone="${ZONE}" "${VM_NAME}" -- bash -s <<'REMOTE'
        cd ~/insurance-broker-agent

        # Python venv
        python3 -m venv .venv
        source .venv/bin/activate
        pip install -q anthropic python-dotenv

        # Create logs directory
        mkdir -p agent-sdk/logs

        # Install cron jobs
        CRON_FILE="/tmp/alex-cron"
        AGENT_DIR="$HOME/insurance-broker-agent"
        PYTHON="$AGENT_DIR/.venv/bin/python"

        cat > "$CRON_FILE" <<CRON
# Alex Agent SDK — Autonomous Tasks
# Morning briefing — 7:30 AM CET
30 7 * * * cd $AGENT_DIR && $PYTHON agent-sdk/orchestrator.py --task morning-brief >> agent-sdk/logs/cron.log 2>&1

# Renewal check — 8:00 AM and 2:00 PM CET
0 8,14 * * * cd $AGENT_DIR && $PYTHON agent-sdk/orchestrator.py --task renewals >> agent-sdk/logs/cron.log 2>&1

# Claims follow-up — every Friday at 5:00 PM
0 17 * * 5 cd $AGENT_DIR && $PYTHON agent-sdk/orchestrator.py --task follow-up >> agent-sdk/logs/cron.log 2>&1

# Compliance reports — 1st of each month at 9:00 AM
0 9 1 * * cd $AGENT_DIR && $PYTHON agent-sdk/orchestrator.py --task compliance >> agent-sdk/logs/cron.log 2>&1

# Cross-sell analysis — every Monday at 10:00 AM
0 10 * * 1 cd $AGENT_DIR && $PYTHON agent-sdk/orchestrator.py --task cross-sell >> agent-sdk/logs/cron.log 2>&1
CRON

        crontab "$CRON_FILE"
        echo "✅ Cron jobs installed:"
        crontab -l

        echo ""
        echo "✅ VM setup complete!"
        echo "Next: set ANTHROPIC_API_KEY and ALEX_API_URL in ~/.env"
REMOTE

    echo ""
    echo "═══════════════════════════════════════════════"
    echo "  ✅ VM created and configured!"
    echo ""
    echo "  Next steps:"
    echo "    1. SSH in:  bash agent-sdk/deploy-gce.sh ssh"
    echo "    2. Set env: echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ~/.env"
    echo "    3. Test:    python agent-sdk/orchestrator.py --task morning-brief --dry-run"
    echo "═══════════════════════════════════════════════"
    ;;

cron)
    echo "📋 Installing cron jobs on ${VM_NAME}..."
    gcloud compute ssh --zone="${ZONE}" "${VM_NAME}" -- bash -c "crontab -l"
    ;;

status)
    echo "📊 VM Status:"
    gcloud compute instances describe "${VM_NAME}" \
        --zone="${ZONE}" \
        --format="table(name,status,networkInterfaces[0].accessConfigs[0].natIP,machineType.basename())"
    ;;

ssh)
    echo "🔗 Connecting to ${VM_NAME}..."
    gcloud compute ssh --zone="${ZONE}" "${VM_NAME}"
    ;;

destroy)
    echo "⚠️  This will DELETE ${VM_NAME} and all data!"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        gcloud compute instances delete "${VM_NAME}" --zone="${ZONE}" --quiet
        echo "✅ VM deleted"
    else
        echo "Cancelled"
    fi
    ;;

logs)
    echo "📜 Recent logs from ${VM_NAME}:"
    gcloud compute ssh --zone="${ZONE}" "${VM_NAME}" -- \
        "tail -50 ~/insurance-broker-agent/agent-sdk/logs/cron.log 2>/dev/null || echo 'No logs yet'"
    ;;

test)
    echo "🧪 Running dry-run test on ${VM_NAME}..."
    gcloud compute ssh --zone="${ZONE}" "${VM_NAME}" -- \
        "cd ~/insurance-broker-agent && .venv/bin/python agent-sdk/orchestrator.py --task morning-brief --dry-run"
    ;;

*)
    echo "Usage: $0 {setup|cron|status|ssh|destroy|logs|test}"
    echo ""
    echo "Commands:"
    echo "  setup    — Create VM + install agent + configure cron"
    echo "  cron     — Show installed cron jobs"
    echo "  status   — Check VM status and IP"
    echo "  ssh      — SSH into VM"
    echo "  destroy  — Delete VM (irreversible)"
    echo "  logs     — View recent orchestrator logs"
    echo "  test     — Run dry-run test on VM"
    ;;
esac
