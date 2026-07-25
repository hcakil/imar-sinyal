#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:-}"
CHANNEL_ID="${2:-}"

if [[ -z "${PROJECT_ID}" || -z "${CHANNEL_ID}" ]]; then
  echo "Kullanım: ./infra/configure-alerts.sh PROJECT_ID NOTIFICATION_CHANNEL_ID"
  exit 2
fi

CHANNEL_NAME="projects/${PROJECT_ID}/notificationChannels/${CHANNEL_ID}"
ACCESS_TOKEN="$(gcloud auth print-access-token)"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TEMP_DIR}"' EXIT

for template in infra/monitoring/*-policy.json; do
  rendered="${TEMP_DIR}/$(basename "${template}")"
  sed "s|__NOTIFICATION_CHANNEL__|${CHANNEL_NAME}|g" "${template}" > "${rendered}"
  curl --fail --silent --show-error \
    --request POST \
    --header "Authorization: Bearer ${ACCESS_TOKEN}" \
    --header "Content-Type: application/json; charset=utf-8" \
    --data-binary "@${rendered}" \
    "https://monitoring.googleapis.com/v3/projects/${PROJECT_ID}/alertPolicies"
  echo
done

echo "İki Monitoring alert politikası oluşturuldu."
