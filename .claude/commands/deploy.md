# Deploy ScanArt to production

Deploy the full ScanArt stack to Google Cloud (backend + frontend).

## Steps

1. Ask user for version tag if not provided (e.g., v17, v18...)
2. Verify `frontend/sw.js` cache name matches the version (MUST match before deploy)
3. Build backend Docker image:
   ```
   gcloud builds submit backend/ --tag gcr.io/gen-lang-client-0167987852/scanart-backend:{version} --quiet
   ```
4. Deploy to Cloud Run (single line — no backslashes):
   ```
   gcloud run deploy scanart-backend --image=gcr.io/gen-lang-client-0167987852/scanart-backend:{version} --region=us-central1 --platform=managed --allow-unauthenticated --memory=1Gi --cpu=2 --concurrency=10 --timeout=300 --set-env-vars=GOOGLE_CLOUD_PROJECT=gen-lang-client-0167987852,GCS_BUCKET_NAME=scanart-results --quiet
   ```
5. Sync frontend to GCS:
   ```
   gsutil -m rsync -r -d frontend/ gs://scanart-frontend-1772986018
   ```
6. Verify health:
   ```
   curl https://scanart-backend-603810013022.us-central1.run.app/health
   ```
7. Report: revision name, frontend URL, backend URL, cache version

## Important
- NEVER use `--config deploy/cloudbuild.yaml` (uses $COMMIT_SHA which is empty locally)
- ALWAYS single-line gcloud run deploy (no `\` line continuations)
- sw.js cache name MUST be bumped before deploying
