# Alex Insurance Broker — Project Definition

**Owner**: Andrei Botescu
**Status**: In development, production-staging
**Last updated**: 2026-04-18

---

## 1. What This Project Is

**Alex Insurance Broker** is an AI-powered email-to-form system for **TPSH Versicherungsmakler GmbH** (Germany). It receives structured broker emails with attachments (damage photos, police reports, repair estimates), uses **Claude Vision** to classify and extract fields from attachments, routes to the correct German insurance form template (KFZ-Schadenmeldung, Haftpflicht, Maschinenbruch, etc.), auto-fills the form, and emails a completed PDF back to the broker.

**Core flow**:
```
Broker email (IMAP AlexAi@tpsh.ro) →
  Alex parses + Vision extracts attachments →
    Routes to template (KFZ/HPF/MB) →
      Auto-fills form_data →
        Generates PDF with embedded photos →
          Emails broker (sends link to client for review) →
            Client completes + signs →
              PDF forwarded to Versicherer (Allianz, HDI, AXA, R+V, HUK)
```

---

## 2. Where It Lives

### Source Code (local)
- **Primary location**: `/Users/andreibotescu/Desktop/insurance-broker-agent/`
- **Main file**: `main.py` (~1.08 MB, monolithic FastAPI)
- **Git remote**: check `git remote -v` in the directory
- **Recommended move**: `~/Projects/alex-insurance-broker/` (better than Desktop, easier backup)

### Live Deployment (Google Cloud)
- **Project**: `able-genetics-platform-2026` (Compute/Cloud Run)
- **Service**: `alex-insurance-broker`
- **Region**: `europe-west3` (Frankfurt)
- **Live URL**: `https://alex-insurance-broker-unwwkkjdba-ey.a.run.app`
- **Project number**: 426485075291
- **Deploy command**: `gcloud run deploy alex-insurance-broker --source . --region=europe-west3 --project=able-genetics-platform-2026 --allow-unauthenticated`

### Data Storage (Firestore)
- **Project**: `project-79fa7e7d-5de7-4c32-b09` (different from deploy project!)
- **Database**: `(default)` Firestore native mode
- **Collections**: 27 (form_submissions, templates, audit, brokers, clients, knowledge, etc.)
- **IAM required**: Cloud Run service account `426485075291-compute@developer.gserviceaccount.com` must have `roles/datastore.user` on this project

### Secrets & Config (Cloud Run env vars)
- `ANTHROPIC_API_KEY` — Claude API
- `GEMINI_API_KEY` — Google Gemini fallback
- `SMTP_HOST/PORT/USER/PASS` — current: Gmail `fungadgetsgames@gmail.com`
- `GCS_BUCKET=alex-broker-reports` — file storage
- `FIRESTORE_PROJECT=project-79fa7e7d-5de7-4c32-b09` (or default in code)
- **Missing/not set yet**: `IMAP_HOST`, `IMAP_USER`, `IMAP_PASS`, `TPSH_ADDRESS`, `TPSH_PHONE`, `TPSH_EMAIL`, `TPSH_WEBSITE`

### External Services Used
- **Anthropic Claude** (console.anthropic.com) — Vision + chat
- **Google Cloud** (console.cloud.google.com) — Cloud Run + Firestore + GCS
- **Gmail SMTP** — outbound email (needs App Password)
- **ze-one.de IMAP** — inbound `AlexAi@tpsh.ro` (not yet fully integrated in current deploy)
- **Email domain**: `tpsh.ro` — broker receives from/to

### File Attachments
- **Disk (ephemeral)**: `/output/form-attachments/` on Cloud Run container — **disappears on redeploy**
- **Firestore**: attachment metadata (filename, size, category, extracted_fields)
- **GCS bucket**: `alex-broker-reports` — should be used for persistent file storage (currently partially implemented)

---

## 3. Project Separation From Other Work

This project is **NOT** related to:
- **ABLE GENETICS** (`able-genetics-platform-2026` is shared but different services)
- **claude-scientific-skills** (worktree at `~/.claude-worktrees/claude-scientific-skills/tender-mcclintock/`)
- **PANDAS Network**, **Cezar demo**, **Recondition**, **ScanArt**

To open a Claude Code session specifically for Alex:
```bash
cd /Users/andreibotescu/Desktop/insurance-broker-agent
claude
```

---

## 4. Safety & Backup

### Currently Safe
- ✅ Source code is in a git repo (commits pushed to remote when `git push` run)
- ✅ Firestore has automatic daily backups (GCP managed)

### Currently Unsafe
- ❌ **Source on Desktop** — vulnerable to accidental deletion
- ❌ **Attachments on Cloud Run ephemeral disk** — lost on redeploy
- ❌ **No offsite backup** of main.py other than git remote
- ❌ **Secrets in env vars only** — not in Secret Manager
- ❌ **No CI/CD** — manual deploys, no staging environment
- ❌ **No monitoring/alerts** configured

### To Make Safe (action items)
1. **Move source** from Desktop to `~/Projects/alex-insurance-broker/`
2. **Verify git remote** and push regularly (`git remote -v`, `git push`)
3. **Enable GCS upload** for all attachments (move off ephemeral disk)
4. **Migrate secrets** to Google Secret Manager
5. **Add CI/CD** via Cloud Build trigger on git push
6. **Set up monitoring**: Cloud Run alerts for 5xx rate, latency p95
7. **Enable Firestore PITR** (Point-in-Time Recovery)

---

## 5. Transferability Checklist

If you transfer this project to another owner or machine, they need:

### Access
- [ ] GCP IAM on `able-genetics-platform-2026` (Cloud Run)
- [ ] GCP IAM on `project-79fa7e7d-5de7-4c32-b09` (Firestore)
- [ ] Anthropic API key
- [ ] Gmail App Password for SMTP
- [ ] IMAP credentials for AlexAi@tpsh.ro
- [ ] Git repo access

### Files to Hand Over
- [ ] Full `/Users/andreibotescu/Desktop/insurance-broker-agent/` folder (or git clone)
- [ ] List of Cloud Run env vars (from `gcloud run services describe`)
- [ ] This PROJECT.md
- [ ] CLAUDE.md (if exists) with project-specific instructions

### Documentation They'll Need
- [ ] How to deploy: `gcloud run deploy alex-insurance-broker --source .`
- [ ] How to test locally: `uvicorn main:app --reload --port 8000`
- [ ] How to view logs: `gcloud logging read ...`
- [ ] Advanced test script (to be saved as `tests/advanced_battery.py`)

---

## 6. Quick Commands Reference

```bash
# Live health check
curl https://alex-insurance-broker-unwwkkjdba-ey.a.run.app/api/health

# View logs (last 5 min, errors only)
gcloud logging read "resource.labels.service_name=alex-insurance-broker AND severity>=ERROR" \
  --project=able-genetics-platform-2026 --limit=10 --freshness=5m

# Deploy
cd /Users/andreibotescu/Desktop/insurance-broker-agent
gcloud run deploy alex-insurance-broker --source . \
  --region=europe-west3 --project=able-genetics-platform-2026 \
  --allow-unauthenticated --quiet

# List all services in region
gcloud run services list --region=europe-west3 --project=able-genetics-platform-2026

# Firestore read example (from app)
# _fs_db.collection('form_submissions').document(sub_id).get()

# Run advanced test (locally)
python3 tests/advanced_battery.py  # TODO: create this file
```

---

## 7. Contact & Ownership

- **Code owner**: Andrei Botescu
- **Business owner**: TPSH Versicherungsmakler GmbH (Germany)
- **AI assistant**: Claude (Anthropic) via Claude Code

---

## 8. Known Issues (as of 2026-04-18)

See `CLAUDE.md` and session memory for running list. Critical items:
1. Template field mapping — mostly fixed in rev-00123-field-aliases
2. TPSH footer shows placeholder `Musterstr. 1` — needs env vars set
3. Ephemeral attachment storage on Cloud Run
4. Service account IAM had to be re-granted after service recreation (lesson: use service account explicitly in `gcloud run deploy --service-account`)
