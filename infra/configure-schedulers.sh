#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:-}"
REGION="europe-west1"
SCHEDULER_SA="imarsinyal-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"
API_ROOT="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Kullanım: ./infra/configure-schedulers.sh FIREBASE_PROJECT_ID"
  exit 2
fi

upsert_scheduler() {
  local name="$1"
  local schedule="$2"
  local job="$3"
  if gcloud scheduler jobs describe "${name}" --location="${REGION}" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "${name}" \
      --location="${REGION}" \
      --schedule="${schedule}" \
      --time-zone="Europe/Istanbul" \
      --uri="${API_ROOT}/${job}:run" \
      --http-method=POST \
      --oauth-service-account-email="${SCHEDULER_SA}"
  else
    gcloud scheduler jobs create http "${name}" \
      --location="${REGION}" \
      --schedule="${schedule}" \
      --time-zone="Europe/Istanbul" \
      --uri="${API_ROOT}/${job}:run" \
      --http-method=POST \
      --oauth-service-account-email="${SCHEDULER_SA}"
  fi
}

gcloud config set project "${PROJECT_ID}"
upsert_scheduler imarsinyal-nightly-trigger "15 3 * * *" imarsinyal-nightly
upsert_scheduler imarsinyal-newsletter-trigger "30 8 * * 1" imarsinyal-newsletter

echo "Gece taraması 03:15, haftalık bülten Pazartesi 08:30 için ayarlandı."
