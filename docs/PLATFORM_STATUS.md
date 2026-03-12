# Alex — Insurance Broker AI Platform
## Technical Status Report — March 2026

> **Last updated:** 12 March 2026
> **Production URL:** https://insurance-broker-alex-603810013022.europe-west3.run.app
> **Cloud Run revision:** `insurance-broker-alex-00092-8tz`
> **AI Model:** Claude Sonnet (claude-sonnet-4-5) via Anthropic API

---

## Current Platform State: MVP — Phase 1

The platform is **fully deployed and operational** on Google Cloud Run (Frankfurt, europe-west3).
All core features are working. The system is in active demo mode.

---

## Infrastructure

| Component | Status | Details |
|---|---|---|
| **Cloud Run** | ✅ Live | europe-west3 (Frankfurt), revision 92 |
| **Firebase Firestore** | ✅ Live | europe-west1, default database |
| **SQLite (in-container)** | ✅ Live | Re-seeded on every deploy from JSON mock data |
| **Firestore Indexes** | ✅ READY | conversations(user_id+updated_at), conversations(user_id+project_id+updated_at), projects(user_id+updated_at) |
| **Cloud Run Job** | ✅ Live | `renewal-alert-job` — daily at 08:00 Europe/Bucharest |
| **Cloud Scheduler** | ✅ Live | `renewal-alert-daily` — triggers renewal-alert-job |
| **Artifact Registry** | ✅ Live | europe-west3-docker.pkg.dev/gen-lang-client-0167987852/cloud-run-source-deploy/insurance-broker-alex |

---

## Authentication

| Account | Email | Password | Role |
|---|---|---|---|
| Admin | admin@demo.ro | admin123 | superadmin |
| Broker | broker@demo.ro | broker123 | broker |

> Both accounts are seeded on every container startup from `scripts/seed_users.py`.
> User data is persisted in **Firebase Firestore** — survives container restarts.

---

## Data Architecture

### What persists in Firestore (cross-deploy)
- `companies` — company profiles (2 entries: Demo Broker SRL + test company)
- `users` — user profiles (3 users: admin, broker, test)
- `tool_permissions` — which tools each user can access
- `conversations` — conversation metadata (title, user, project, timestamps)
- `conversation_messages` — full Anthropic message history per conversation

### What re-seeds on every deploy (from JSON mock data)
- `clients` — 6 demo clients (Romanian + German)
- `policies` — 8 demo policies
- `products` — 10 insurance products (RCA, CASCO, PAD, KFZ, CMR, LIFE)
- `insurers` — 9 insurers (Allianz, Generali, Omniasig, etc.)
- `offers` — cleared on reseed
- `claims` — cleared on reseed

> **Why:** Broker data re-seeds to keep the demo clean. User/conversation data persists because it's part of the service experience.

---

## Feature Checklist

### Core Chat (Chainlit 2.10.0)
- ✅ Login / logout with bcrypt password auth
- ✅ Multi-user (RBAC — superadmin / broker)
- ✅ Project picker + conversation picker at session start
- ✅ Persistent chat history (Firestore dual-write)
- ✅ Smart auto-generated conversation titles (Claude Haiku)
- ✅ Multi-language: EN / RO / DE

### Broker Tools (30 tools)

| Category | Tools | Status |
|---|---|---|
| Clients | search, get, create, update, delete | ✅ |
| Products | search, compare | ✅ |
| Offers | create (PDF + TXT), list, send by email | ✅ |
| Policies | list, renewals dashboard | ✅ |
| Claims | log, get status | ✅ |
| Compliance | ASF summary, BaFin summary, compliance check | ✅ |
| Web automation | browse web, check RCA | ✅ |
| Desktop automation | computer use status, run task | ✅ (local agent) |
| Knowledge base | search, upload, analyze document, status, reindex | ✅ |
| Cloud storage | Google Drive upload/list/link, SharePoint upload/list/link | ✅ |
| Output files | list files, interactive cleanup | ✅ |

### Email
- ✅ Send offer by email (SMTP via Gmail)
- ✅ Full localization: RO / DE / EN (auto-detected from offer content)
- ✅ PDF-first attachment (fallback to TXT)
- ✅ Status updated to 'sent' in DB after successful send
- ✅ Gmail SMTP: fungadgetsgames@gmail.com (App Password configured)

### PDF Generation (WeasyPrint)
- ✅ WeasyPrint installed with full Pango/Cairo/font stack
- ✅ Fonts: fonts-liberation, fonts-dejavu-core, fontconfig + fc-cache
- ✅ HTML → PDF via Jinja2 template (offer_en.html)

### Admin Panel (`/admin`)
- ✅ Login with JWT (admin@demo.ro / admin123)
- ✅ Dashboard: companies, users, token usage, audit log
- ✅ User management: create/edit/disable users
- ✅ Tool permissions matrix: per-user checkbox matrix
- ✅ Audit log: every tool call logged with user + timestamp + tokens

### Daily Renewal Alerts
- ✅ Cloud Run Job: `renewal-alert-job` (runs `scripts/daily_renewal_alert.py`)
- ✅ Cloud Scheduler: fires daily at 08:00 Europe/Bucharest
- ✅ Email sent to: fungadgetsgames@gmail.com
- ✅ Covers: 30 days ahead, urgency classification (≤7 days = URGENT)
- ✅ Live API endpoint: `/api/renewals?days=30`

### Output File Management
- ✅ `broker_list_output_files` — lists PDFs, TXTs, XLSXs with metadata
- ✅ Interactive cleanup: 4-step flow (start → categorize by age → confirm list → execute)
- ✅ Categories: recent (<7d), middle (7-30d), old (>30d)
- ✅ No silent deletion — user selects and confirms

---

## Demo Data (Mock — Phase 1)

| Entity | Count | Examples |
|---|---|---|
| Clients | 6 | Ion Popescu (RO), Maria Ionescu (RO), Stefan Müller (DE), etc. |
| Products | 10 | RCA Allianz, CASCO Generali, PAD Omniasig, KFZ Allianz DE, etc. |
| Policies | 8 | Active, expiring soon, one expired |
| Insurers | 9 | Allianz (RO+DE), Generali, Omniasig, Signal Iduna, etc. |
| Users | 2 | admin@demo.ro / admin123, broker@demo.ro / broker123 |

---

## Deployment Process

Building and deploying a new version:

```bash
# 1. Build Docker image via Cloud Build
gcloud builds submit \
  --gcs-source-staging-dir "gs://gen-lang-client-0167987852_cloudbuild/source" \
  --config /tmp/cloudbuild-r91.yaml

# 2. Deploy to Cloud Run
gcloud run deploy insurance-broker-alex \
  --image "europe-west3-docker.pkg.dev/gen-lang-client-0167987852/cloud-run-source-deploy/insurance-broker-alex:latest" \
  --region europe-west3 \
  --quiet

# Note: cloudbuild-r91.yaml builds and pushes to Artifact Registry
```

**Known issue — macOS Python 3.13 gzip bug:**
`gcloud builds submit [local-path]` crashes on macOS with Python 3.13 (gzip RuntimeError).
Workaround: use `--gcs-source-staging-dir` which uploads via gsutil instead of Python's gzip module.

---

## Environment Variables (Cloud Run)

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude Sonnet API access |
| `GOOGLE_API_KEY` | Gemini / Google Vision API |
| `SMTP_HOST` | smtp.gmail.com |
| `SMTP_PORT` | 587 |
| `SMTP_USER` | fungadgetsgames@gmail.com |
| `SMTP_PASS` | Gmail App Password |
| `CHAINLIT_AUTH_SECRET` | Chainlit session signing |
| `ADMIN_JWT_SECRET` | Admin panel JWT signing |
| `PORT` | 8080 (Cloud Run standard) |
| `PYTHONPATH` | /app:/app/mcp-server |

---

## Known Limitations (Phase 1 — MVP)

| Limitation | Impact | Plan |
|---|---|---|
| Cloud Run cold starts (~3-5s) | First request after inactivity | Phase 2: dedicated VM |
| SQLite in-container (broker data) | Cleared on each deploy | Phase 2: real client data in Firestore/PostgreSQL |
| Demo data only | No real client records | Phase 2: after DPA signed |
| WeasyPrint PDF fonts | Renders correctly, not pixel-perfect | Acceptable for demo |
| RCA check (AIDA) blocked by reCAPTCHA | Returns informative error | Local agent workaround available |
| Local agent required for desktop automation | Needs Python install on client machine | Documented in README |
| Firestore in europe-west1, Cloud Run in europe-west3 | Minor latency (~5ms) | Acceptable — free tier constraint |

---

## Next Steps — Phase 2 Roadmap

- [ ] Migrate broker data (clients, policies) to Firestore/PostgreSQL — no more reseed
- [ ] Add real client data after DPA signing
- [ ] Move to dedicated VM on Google Cloud (from Cloud Run)
- [ ] Connect to real insurer portals via Playwright connectors
- [ ] Password reset flow for admin panel
- [ ] Extend local agent with more connectors (Allianz portal, CEDAM, PAID)
- [ ] Custom branding per company (logo, colors)
- [ ] Multi-company tenant isolation (data per company_id)

---

*Document maintained by the development team. Updated after every significant deployment.*
