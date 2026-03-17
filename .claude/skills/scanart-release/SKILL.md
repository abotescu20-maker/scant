name: scanart-release
description: Full release pipeline for ScanArt. Auto-invoke when user says "release", "lansează", "fa release", "ship it", "push new version". Chains version bump + deploy + smoke test into one atomic operation.

# ScanArt Release Skill (Multi-Phase)

This skill orchestrates a complete release in 5 phases. If any phase fails, STOP and report which phase failed.

## Phase 1: Version Bump
1. Read `frontend/sw.js` → extract current version number from `const CACHE = 'scanart-vXX'`
2. Increment version: vXX → v(XX+1)
3. Edit `frontend/sw.js` → update CACHE string
4. Edit `CLAUDE.md` → update "Current version" line
5. Report: "Bumped v{old} → v{new}"

## Phase 2: Backend Build
1. Run: `gcloud builds submit backend/ --tag gcr.io/gen-lang-client-0167987852/scanart-backend:v{new} --quiet`
2. Wait for SUCCESS status
3. If FAILURE → STOP, report build error

## Phase 3: Backend Deploy
1. Run (SINGLE LINE, no backslash continuations):
   `gcloud run deploy scanart-backend --image=gcr.io/gen-lang-client-0167987852/scanart-backend:v{new} --region=us-central1 --platform=managed --allow-unauthenticated --memory=1Gi --cpu=2 --concurrency=10 --timeout=300 --set-env-vars=GOOGLE_CLOUD_PROJECT=gen-lang-client-0167987852,GCS_BUCKET_NAME=scanart-results --quiet`
2. Capture revision name from output
3. If deploy fails → STOP, report error

## Phase 4: Frontend Sync
1. Run: `gsutil -m rsync -r -d frontend/ gs://scanart-frontend-1772986018`
2. Verify both index.html and sw.js were synced

## Phase 5: Smoke Tests
Run ALL of these and report pass/fail for each:
1. `curl -sf https://scanart-backend-603810013022.us-central1.run.app/health` → expect 200
2. `curl -sf https://scanart-backend-603810013022.us-central1.run.app/api/tiers` → expect 200 + JSON
3. `curl -sf https://scanart-backend-603810013022.us-central1.run.app/api/trending` → expect 200
4. `curl -sf https://storage.googleapis.com/scanart-frontend-1772986018/index.html` → expect 200
5. `curl -sf https://storage.googleapis.com/scanart-frontend-1772986018/sw.js` → verify contains `scanart-v{new}`

## Release Report
After all phases, output a summary:
```
Release v{new} ✅
- Backend revision: {revision_name}
- Backend URL: https://scanart-backend-603810013022.us-central1.run.app
- Frontend URL: https://storage.googleapis.com/scanart-frontend-1772986018/index.html
- Smoke tests: {passed}/{total} passed
```

## Critical Rules
- NEVER use `--config deploy/cloudbuild.yaml` (fails locally due to empty $COMMIT_SHA)
- NEVER use backslash line continuations in gcloud commands
- ALWAYS verify sw.js was bumped BEFORE deploying
- GCS bucket for frontend: `scanart-frontend-1772986018` (with numeric suffix)
- GCS env var for results: `scanart-results` (without suffix)
