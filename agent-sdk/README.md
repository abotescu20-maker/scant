# Alex Agent SDK — Autonomous Insurance Broker

Autonomous task runner for Alex Insurance Broker. Runs on a GCE VM and executes
scheduled insurance tasks using the Alex REST API + Claude AI analysis.

## Architecture

```
┌──────────────────────────────────────────┐
│  Broker Desktop (Windows/Mac)            │
│                                          │
│  alex-local-agent/                       │
│  ├── CEDAM connector (RCA checks)        │
│  ├── PAID portal connector               │
│  ├── Allianz connector                   │
│  ├── Desktop generic (Playwright)        │
│  ├── Anthropic Computer Use              │
│  └── Polls /cu/tasks every 3s            │
└──────────────┬───────────────────────────┘
               │ HTTP polling + results
┌──────────────▼───────────────────────────┐
│  Cloud Run (existing) — Frankfurt        │
│  Alex Chat UI + 36 MCP Tools + REST API  │
│  /api/renewals · /api/claims/open        │
│  /cu/enqueue · /cu/tasks · /cu/results   │
│  Google Drive + SharePoint tools         │
│  https://insurance-broker-alex-....app   │
└──────────────┬───────────────────────────┘
               │ REST API
┌──────────────▼───────────────────────────┐
│  GCE VM — alex-agent-vm                 │
│  e2-medium, europe-west3, ~$25/mo       │
│                                          │
│  orchestrator.py                         │
│  ├── CORE TASKS                          │
│  │   ├── task_morning_brief() → 7:30AM  │
│  │   ├── task_renewals()    → 8+14h     │
│  │   ├── task_follow_up()   → Fri 17h   │
│  │   ├── task_compliance()  → 1st 9h    │
│  │   └── task_cross_sell()  → Mon 10h   │
│  │                                       │
│  ├── INTEGRATIONS                        │
│  │   ├── local_agent_sync() → 8:15+14:15│
│  │   │   └── Dispatch tasks to desktop  │
│  │   │       agent (RCA checks, portal) │
│  │   ├── upload_reports()   → 18:00     │
│  │   │   ├── Google Drive upload        │
│  │   │   └── SharePoint upload          │
│  │   └── n8n_notify()       → on events │
│  │       ├── renewal-urgent → SMS       │
│  │       ├── claim-overdue → CRM task   │
│  │       └── task-completed → Slack     │
│  │                                       │
│  └── Claude API (Anthropic)              │
│      → Analyzes data, generates reports  │
│      → Sends email alerts via SMTP       │
└──────────────┬───────────────────────────┘
               │ Webhooks
┌──────────────▼───────────────────────────┐
│  n8n Workflow Automation (optional)      │
│  ├── SMS alerts (Twilio/MessageBird)     │
│  ├── CRM updates (HubSpot/Salesforce)   │
│  ├── Slack/Teams notifications           │
│  ├── Calendar reminders                  │
│  └── Custom workflows                    │
└──────────────────────────────────────────┘
```

## Quick Start

### 1. Test locally (dry run)

```bash
cd insurance-broker-agent
python agent-sdk/orchestrator.py --task morning-brief --dry-run
python agent-sdk/orchestrator.py --task all --dry-run
```

### 2. Deploy to GCE

```bash
# Set your GCP project
export GCP_PROJECT_ID=your-project-id

# Create VM + install everything
bash agent-sdk/deploy-gce.sh setup

# SSH in and configure
bash agent-sdk/deploy-gce.sh ssh
cat >> ~/.env <<EOF
ANTHROPIC_API_KEY=sk-ant-...
ALEX_API_URL=https://your-cloud-run-url
ALERT_TO=broker@company.com
N8N_WEBHOOK_URL=https://your-n8n.com/webhook/xxx
GOOGLE_APPLICATION_CREDENTIALS_JSON={"type":"service_account",...}
GOOGLE_DRIVE_FOLDER_ID=1abc...xyz
SHAREPOINT_TENANT_ID=xxx
SHAREPOINT_CLIENT_ID=xxx
SHAREPOINT_CLIENT_SECRET=xxx
SHAREPOINT_SITE_URL=https://company.sharepoint.com/sites/Brokeraj
SHAREPOINT_FOLDER_PATH=/Shared Documents/Rapoarte
EOF

# Test
bash agent-sdk/deploy-gce.sh test
```

### 3. Monitor

```bash
bash agent-sdk/deploy-gce.sh logs     # View recent logs
bash agent-sdk/deploy-gce.sh status   # Check VM status
```

## Tasks

### Core Tasks

| Task | Schedule | What it does |
|------|----------|-------------|
| `morning-brief` | Daily 7:30 AM | Dashboard + urgent renewals + open claims + local agent status |
| `renewals` | Daily 8AM + 2PM | Check expiring policies, prioritize RCA, n8n alert per urgent |
| `follow-up` | Friday 5PM | Open claims needing action, flag overdue >14 days |
| `compliance` | 1st of month 9AM | ASF + BaFin monthly reports |
| `cross-sell` | Monday 10AM | Portfolio gap analysis, estimated premium uplift |

### Integration Tasks

| Task | Schedule | What it does |
|------|----------|-------------|
| `local-agent-sync` | Daily 8:15 AM + 2:15 PM | Check desktop agents, dispatch RCA verifications, portal screenshots |
| `upload-reports` | Daily 6:00 PM | Upload all today's reports to Google Drive + SharePoint |

### n8n Events (automatic, no separate task)

| Event | Trigger | Suggested n8n Action |
|-------|---------|---------------------|
| `renewal-urgent` | RCA expiring < 7 days | Send SMS to broker |
| `claim-overdue` | Claim open > 14 days | Create CRM task |
| `compliance-due` | Monthly report ready | Notify management |
| `cross-sell-found` | Opportunities detected | Add to sales pipeline |
| `reports-uploaded` | Cloud upload complete | Share link in Slack |
| `task-completed` | Any task finishes | Dashboard update |
| `task-failed` | Any task errors | Alert DevOps |

## Integrations

### Local Agent Bridge

The orchestrator connects to `alex-local-agent` running on the broker's desktop:

```
Orchestrator → POST /cu/enqueue → Cloud Run queues task
                                 ↓
                Local Agent polls /cu/tasks every 3s
                                 ↓
                Agent executes via connector (CEDAM, Playwright, etc.)
                                 ↓
                Agent posts result to /cu/results
                                 ↓
Orchestrator ← GET /cu/result/{id} (polling)
```

**Available connectors:** cedam, paid, allianz, web_generic, desktop_generic, anthropic_computer_use

### Cloud Storage

Reports are automatically uploaded to:
- **Google Drive** — requires service account + folder ID
- **SharePoint** — requires Azure AD app registration

Both use the existing `drive_tools.py` from the MCP server.

### n8n Webhooks

Set `N8N_WEBHOOK_URL` to receive JSON events:

```json
{
  "event": "renewal-urgent",
  "timestamp": "2026-03-14T08:00:00",
  "source": "alex-orchestrator",
  "data": {
    "client": "Gheorghe Popa",
    "policy_type": "RCA",
    "days_left": 3,
    "phone": "+40733445566"
  }
}
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude analysis |
| `ALEX_API_URL` | Yes | Alex Cloud Run URL |
| `ALERT_TO` | No | Email recipients (comma-separated) |
| `SMTP_HOST/PORT/USER/PASS` | No | SMTP server for emails |
| `N8N_WEBHOOK_URL` | No | n8n webhook for workflow automation |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | No | Google Drive service account |
| `GOOGLE_DRIVE_FOLDER_ID` | No | Google Drive target folder |
| `SHAREPOINT_TENANT_ID` | No | Azure AD tenant |
| `SHAREPOINT_CLIENT_ID` | No | Azure AD app client ID |
| `SHAREPOINT_CLIENT_SECRET` | No | Azure AD app secret |
| `SHAREPOINT_SITE_URL` | No | SharePoint site URL |
| `SHAREPOINT_FOLDER_PATH` | No | SharePoint folder path |

## Costs

| Component | Monthly |
|-----------|---------|
| GCE e2-medium VM | ~$25 |
| Claude API (Sonnet) | ~$2-50 |
| Google Drive API | Free |
| SharePoint API | Free (included in M365) |
| n8n (self-hosted) | Free |
| **Total** | **~$27-75/month** |
