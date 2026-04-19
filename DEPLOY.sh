#!/usr/bin/env bash
# Alex Insurance Broker — One-command deploy to Cloud Run
# Usage: ./DEPLOY.sh
set -e

PROJECT_ID="able-genetics-platform-2026"
SERVICE="alex-insurance-broker"
REGION="europe-west3"
FIRESTORE_PROJECT="project-79fa7e7d-5de7-4c32-b09"
SA="426485075291-compute@developer.gserviceaccount.com"

echo "═══════════════════════════════════════════════════════════════"
echo "  ALEX INSURANCE BROKER — DEPLOY"
echo "  Project: $PROJECT_ID"
echo "  Service: $SERVICE"
echo "  Region:  $REGION"
echo "═══════════════════════════════════════════════════════════════"

# 1. Git status check
echo ""
echo "▸ Git status:"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "  ⚠ Uncommitted changes detected. Continue? (y/N)"
  read -r ans
  [[ "$ans" != "y" ]] && exit 1
fi
git log --oneline -1

# 2. Verify IAM prerequisites (idempotent)
echo ""
echo "▸ Ensuring IAM on both projects..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA" --role="roles/datastore.user" --quiet >/dev/null
gcloud projects add-iam-policy-binding "$FIRESTORE_PROJECT" \
  --member="serviceAccount:$SA" --role="roles/datastore.user" --quiet >/dev/null
echo "  ✓ SA has datastore.user on both projects"

# 3. Deploy
echo ""
echo "▸ Deploying..."
gcloud run deploy "$SERVICE" \
  --source . \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --allow-unauthenticated \
  --min-instances=1 \
  --memory=1Gi \
  --cpu=1 \
  --timeout=300 \
  --quiet

# 4. Health check
echo ""
echo "▸ Health check..."
URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT_ID" --format='value(status.url)')
echo "  URL: $URL"
sleep 5
curl -sf -m 10 "$URL/api/health" | python3 -m json.tool | head -10

echo ""
echo "✅ Deploy complete."
echo ""
echo "Next steps:"
echo "  • Test:  curl $URL/api/health"
echo "  • Logs:  gcloud logging read \"resource.labels.service_name=$SERVICE\" --project=$PROJECT_ID --limit=20 --freshness=5m"
echo "  • Open:  $URL"
