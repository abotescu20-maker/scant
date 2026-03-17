#!/bin/bash
# Setup initial Google Cloud pentru ScanArt
# Ruleaza o singura data: bash deploy/setup.sh

set -e

PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
BUCKET_RESULTS="scanart-results"
BUCKET_FRONTEND="scanart-frontend"

echo "Setup ScanArt pe proiect: $PROJECT_ID"

# Activeaza API-urile necesare
echo "Activand API-uri..."
gcloud services enable \
  run.googleapis.com \
  aiplatform.googleapis.com \
  generativelanguage.googleapis.com \
  storage.googleapis.com \
  cloudbuild.googleapis.com \
  containerregistry.googleapis.com

# Creeaza bucket pentru rezultate (video-uri)
echo "Creand bucket rezultate..."
gsutil mb -p $PROJECT_ID -l $REGION gs://$BUCKET_RESULTS 2>/dev/null || echo "Bucket deja exista"
gsutil iam ch allUsers:objectViewer gs://$BUCKET_RESULTS
gsutil cors set deploy/cors.json gs://$BUCKET_RESULTS

# Creeaza bucket pentru frontend static
echo "Creand bucket frontend..."
gsutil mb -p $PROJECT_ID -l $REGION gs://$BUCKET_FRONTEND 2>/dev/null || echo "Bucket deja exista"
gsutil iam ch allUsers:objectViewer gs://$BUCKET_FRONTEND
gsutil web set -m index.html -e index.html gs://$BUCKET_FRONTEND

echo ""
echo "✓ Setup complet!"
echo ""
echo "Urmatoarele comenzi pentru deploy:"
echo "  gcloud builds submit --config deploy/cloudbuild.yaml"
echo ""
echo "URL backend: https://scanart-backend-HASH-uc.a.run.app"
echo "URL frontend: https://storage.googleapis.com/$BUCKET_FRONTEND/index.html"
