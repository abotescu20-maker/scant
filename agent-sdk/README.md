# Alex Agent SDK — Autonomous Insurance Broker

Autonomous task runner for Alex Insurance Broker. Runs on a GCE VM and executes
scheduled insurance tasks using the Alex REST API + Claude AI analysis.

## Architecture

```
┌─────────────────────────────────────┐
│  Cloud Run (existing)               │
│  Alex Chat UI + MCP Tools + API     │
│  https://...run.app                 │
└────────────────┬────────────────────┘
                 │ REST API
┌────────────────▼────────────────────┐
│  GCE VM — alex-agent-vm            │
│  e2-medium, europe-west3, ~$25/mo  │
│                                     │
│  orchestrator.py                    │
│  ├── task_renewals()    → 8AM+2PM  │
│  ├── task_morning_brief() → 7:30AM │
│  ├── task_follow_up()   → Fri 5PM  │
│  ├── task_compliance()  → 1st 9AM  │
│  └── task_cross_sell()  → Mon 10AM │
│                                     │
│  Claude API (Anthropic)             │
│  → Analyzes data, generates reports │
│  → Sends email alerts via SMTP      │
└─────────────────────────────────────┘
```

## Quick Start

### 1. Test locally (dry run)

```bash
cd insurance-broker-agent
python agent-sdk/orchestrator.py --task morning-brief --dry-run
```

### 2. Deploy to GCE

```bash
# Set your GCP project
export GCP_PROJECT_ID=your-project-id

# Create VM + install everything
bash agent-sdk/deploy-gce.sh setup

# SSH in and set API key
bash agent-sdk/deploy-gce.sh ssh
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ~/.env
echo 'ALEX_API_URL=https://your-cloud-run-url' >> ~/.env

# Test
bash agent-sdk/deploy-gce.sh test
```

### 3. Monitor

```bash
bash agent-sdk/deploy-gce.sh logs     # View recent logs
bash agent-sdk/deploy-gce.sh status   # Check VM status
```

## Tasks

| Task | Schedule | What it does |
|------|----------|-------------|
| `morning-brief` | Daily 7:30 AM | Dashboard + urgent renewals + open claims summary |
| `renewals` | Daily 8AM + 2PM | Check expiring policies, prioritize RCA |
| `follow-up` | Friday 5PM | Open claims needing action |
| `compliance` | 1st of month 9AM | ASF + BaFin monthly reports |
| `cross-sell` | Monday 10AM | Portfolio gap analysis |

## Costs

| Component | Monthly |
|-----------|---------|
| GCE e2-medium VM | ~$25 |
| Claude API (Sonnet) | ~$50-200 |
| Total | ~$75-225 |
