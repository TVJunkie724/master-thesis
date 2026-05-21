#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

APPLY=false
PROJECT_ID=""
BILLING_ACCOUNT=""
IDENTITY_NAME="twin2mc-deployer"
REGION="europe-west1"
ROLE_ID="Twin2MCDeployer"
ROLE_FILE="${REPO_ROOT}/3-cloud-deployer/docs/references/gcp_custom_role.yaml"
OUTPUT_FILE=""

usage() {
  cat <<'USAGE'
Usage:
  bootstrap/gcp/bootstrap_deployment_identity.sh --project-id <id> [options]

Options:
  --apply                    Create/update the service account and role binding. Without this flag, the script is dry-run only.
  --project-id <id>          GCP project id used for deployments.
  --billing-account <id>     Optional billing account id for pricing and project setup metadata.
  --name <name>              Service account display/name prefix. Default: twin2mc-deployer.
  --region <region>          Default deployment region. Default: europe-west1.
  --role-id <id>             Custom role id. Default: Twin2MCDeployer.
  --role-file <path>         Custom role YAML. Default: 3-cloud-deployer/docs/references/gcp_custom_role.yaml.
  --output-file <path>       Write CloudConnection JSON to this local file instead of stdout.
  -h, --help                 Show this help.

The script never accepts admin secrets as arguments. Authenticate the gcloud CLI
outside the script, then run with --apply only when the dry-run plan is correct.
USAGE
}

require_value() {
  local name="$1"
  local value="${2:-}"
  if [[ -z "${value}" ]]; then
    echo "Missing value for ${name}" >&2
    exit 2
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=true; shift ;;
    --project-id) require_value "$1" "${2:-}"; PROJECT_ID="$2"; shift 2 ;;
    --billing-account) require_value "$1" "${2:-}"; BILLING_ACCOUNT="$2"; shift 2 ;;
    --name) require_value "$1" "${2:-}"; IDENTITY_NAME="$2"; shift 2 ;;
    --region) require_value "$1" "${2:-}"; REGION="$2"; shift 2 ;;
    --role-id) require_value "$1" "${2:-}"; ROLE_ID="$2"; shift 2 ;;
    --role-file) require_value "$1" "${2:-}"; ROLE_FILE="$2"; shift 2 ;;
    --output-file) require_value "$1" "${2:-}"; OUTPUT_FILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

require_value "--project-id" "${PROJECT_ID}"
if [[ ! -f "${ROLE_FILE}" ]]; then
  echo "Role file not found: ${ROLE_FILE}" >&2
  exit 2
fi

SERVICE_ACCOUNT_ID="${IDENTITY_NAME//_/-}"
SERVICE_ACCOUNT_ID="${SERVICE_ACCOUNT_ID//./-}"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_ID}@${PROJECT_ID}.iam.gserviceaccount.com"

if [[ "${APPLY}" != "true" ]]; then
  cat <<PLAN
Dry-run only. No GCP resources were changed.

Planned GCP deployment identity:
  project_id: ${PROJECT_ID}
  billing_account: ${BILLING_ACCOUNT:-not set}
  service_account: ${SERVICE_ACCOUNT_EMAIL}
  region: ${REGION}
  custom_role: projects/${PROJECT_ID}/roles/${ROLE_ID}
  role_file: ${ROLE_FILE}

Run again with --apply after reviewing the role and active gcloud identity.
PLAN
  exit 0
fi

command -v gcloud >/dev/null || { echo "gcloud CLI is required" >&2; exit 2; }

ACTIVE_PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
if [[ "${ACTIVE_PROJECT}" != "${PROJECT_ID}" ]]; then
  echo "Active gcloud project ${ACTIVE_PROJECT} does not match expected ${PROJECT_ID}" >&2
  exit 1
fi

gcloud services enable \
  cloudfunctions.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  eventarc.googleapis.com \
  pubsub.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  cloudscheduler.googleapis.com \
  serviceusage.googleapis.com \
  --project "${PROJECT_ID}" >/dev/null

if ! gcloud iam roles describe "${ROLE_ID}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam roles create "${ROLE_ID}" --project "${PROJECT_ID}" --file "${ROLE_FILE}" >/dev/null
else
  gcloud iam roles update "${ROLE_ID}" --project "${PROJECT_ID}" --file "${ROLE_FILE}" >/dev/null
fi

if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SERVICE_ACCOUNT_ID}" \
    --project "${PROJECT_ID}" \
    --display-name "${IDENTITY_NAME}" >/dev/null
fi

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member "serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role "projects/${PROJECT_ID}/roles/${ROLE_ID}" >/dev/null

KEY_FILE="$(mktemp)"
trap 'rm -f "${KEY_FILE}"' EXIT
gcloud iam service-accounts keys create "${KEY_FILE}" \
  --iam-account "${SERVICE_ACCOUNT_EMAIL}" \
  --project "${PROJECT_ID}" >/dev/null

render_connection_json() {
  python3 - "$IDENTITY_NAME" "$PROJECT_ID" "$BILLING_ACCOUNT" "$REGION" "$KEY_FILE" "$SERVICE_ACCOUNT_EMAIL" <<'PY'
import json
import sys

name, project_id, billing_account, region, key_file, service_account_email = sys.argv[1:]
with open(key_file, "r", encoding="utf-8") as handle:
    service_account_json = handle.read()

payload = {
    "provider": "gcp",
    "display_name": name,
    "auth_type": "service_account_key",
    "cloud_scope": {
        "project_id": project_id,
        "billing_account": billing_account or None,
        "region": region,
        "service_account_email": service_account_email,
    },
    "gcp": {
        "project_id": project_id,
        "billing_account": billing_account or None,
        "region": region,
        "service_account_json": service_account_json,
    },
}
print(json.dumps(payload, indent=2))
PY
}

if [[ -n "${OUTPUT_FILE}" ]]; then
  umask 077
  render_connection_json > "${OUTPUT_FILE}"
  echo "CloudConnection import JSON written to ${OUTPUT_FILE}" >&2
else
  render_connection_json
fi
