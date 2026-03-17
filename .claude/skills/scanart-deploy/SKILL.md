---
name: scanart-deploy
description: Deploy ScanArt app to Google Cloud Production. Auto-invoke when user says "deploy", "push to prod", "fa deploy", "trimite pe Cloud Run", "lansează versiunea", "dă drumul la versiunea", "pune pe live".
allowed_tools: Bash, Read, Glob
---

# ScanArt Deploy Skill

## Deploy order (always follow exactly)

1. **Verify sw.js version** — read `frontend/sw.js`, confirm cache name matches intended version
2. **Build Docker image:**
   ```
   gcloud builds submit backend/ --tag gcr.io/gen-lang-client-0167987852/scanart-backend:{version} --quiet
   ```
3. **Deploy Cloud Run** (SINGLE LINE — no backslashes):
   ```
   gcloud run deploy scanart-backend --image=gcr.io/gen-lang-client-0167987852/scanart-backend:{version} --region=us-central1 --platform=managed --allow-unauthenticated --memory=1Gi --cpu=2 --concurrency=10 --timeout=300 --set-env-vars=GOOGLE_CLOUD_PROJECT=gen-lang-client-0167987852,GCS_BUCKET_NAME=scanart-results --quiet
   ```
4. **Sync frontend:**
   ```
   gsutil -m rsync -r -d frontend/ gs://scanart-frontend-1772986018
   ```
5. **Verify health:**
   ```
   curl https://scanart-backend-603810013022.us-central1.run.app/health
   ```
6. **Report:** revision name from Cloud Run output, frontend URL, backend URL

## Critical rules
- NEVER `--config deploy/cloudbuild.yaml` (uses $COMMIT_SHA = empty string locally)
- NEVER multi-line `gcloud run deploy` with `\` (breaks silently)
- ALWAYS `--quiet` on `gcloud builds submit`
- GCS bucket for media env var = `scanart-results` (NO -1772986018 suffix)
- GCS bucket for rsync = `scanart-frontend-1772986018` (WITH suffix)
