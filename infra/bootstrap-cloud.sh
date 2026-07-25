#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:-}"
REGION="europe-west1"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Kullanım: ./infra/bootstrap-cloud.sh FIREBASE_PROJECT_ID"
  exit 2
fi

gcloud config set project "${PROJECT_ID}"
gcloud services enable \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com

gcloud artifacts repositories describe imarsinyal \
  --location="${REGION}" >/dev/null 2>&1 ||
  gcloud artifacts repositories create imarsinyal \
    --repository-format=docker \
    --location="${REGION}" \
    --description="İmarSinyal container images"

gcloud storage buckets describe \
  "gs://${PROJECT_ID}-imarsinyal-evidence" >/dev/null 2>&1 ||
  gcloud storage buckets create \
    "gs://${PROJECT_ID}-imarsinyal-evidence" \
    --location="${REGION}" \
    --uniform-bucket-level-access

gcloud iam service-accounts describe \
  "imarsinyal-runtime@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1 ||
  gcloud iam service-accounts create imarsinyal-runtime \
    --display-name="İmarSinyal runtime"

gcloud iam service-accounts describe \
  "imarsinyal-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1 ||
  gcloud iam service-accounts create imarsinyal-scheduler \
    --display-name="İmarSinyal scheduler"

for role in roles/datastore.user roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:imarsinyal-runtime@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="${role}" \
    --condition=None >/dev/null
done

gcloud storage buckets add-iam-policy-binding \
  "gs://${PROJECT_ID}-imarsinyal-evidence" \
  --member="serviceAccount:imarsinyal-runtime@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin" >/dev/null

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
CLOUD_BUILD_SA="$(
  gcloud builds get-default-service-account \
    --format='value(serviceAccountEmail)' 2>/dev/null ||
    echo "${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
)"
CLOUD_BUILD_SA="${CLOUD_BUILD_SA##*/}"
for role in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="${role}" \
    --condition=None >/dev/null
done

for secret in gemini-api-key resend-api-key unsubscribe-secret; do
  gcloud secrets describe "${secret}" >/dev/null 2>&1 ||
    gcloud secrets create "${secret}" \
      --replication-policy=user-managed \
      --locations="${REGION}"
done

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:imarsinyal-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --condition=None >/dev/null

gcloud logging metrics describe imarsinyal_empty_scrape_streak >/dev/null 2>&1 ||
  gcloud logging metrics create imarsinyal_empty_scrape_streak \
    --description="Üç ardışık boş ABB askı taraması" \
    --log-filter='resource.type="cloud_run_job" AND textPayload:"THREE_CONSECUTIVE_EMPTY_SCRAPES"'

echo "Bulut temeli hazır."
echo "Şimdi üç secret için ilk sürümü ekleyin; değerleri bu script'e yazmayın."
echo "Ardından Cloud Build ve Scheduler adımlarını README'den çalıştırın."
