#!/usr/bin/env bash
set -euo pipefail

APPLY=false
ROTATE_CLIENT_SECRET=false
OVERWRITE_OUTPUT=false
SUBSCRIPTION_ID=""
TENANT_ID=""
IDENTITY_NAME="twin2mc-deployer"
REGION="westeurope"
OUTPUT_FILE=""

usage() {
  cat <<'USAGE'
Usage:
  bootstrap/azure/bootstrap_deployment_identity.sh --subscription-id <id> --tenant-id <id> [options]

Options:
  --apply                    Create/update the service principal. Without this flag, the script is dry-run only.
  --rotate-client-secret     Add a new client secret when the app registration already exists.
  --overwrite-output         Allow overwriting --output-file if it already exists.
  --subscription-id <id>     Azure subscription id used for deployments.
  --tenant-id <id>           Azure tenant id for the active admin/bootstrap session.
  --name <name>              App registration / service principal name. Default: twin2mc-deployer.
  --region <region>          Default deployment region. Default: westeurope.
  --output-file <path>       Write CloudConnection JSON to this local file instead of stdout.
  -h, --help                 Show this help.

The script never accepts admin secrets as arguments. Authenticate the Azure CLI
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
    --rotate-client-secret) ROTATE_CLIENT_SECRET=true; shift ;;
    --overwrite-output) OVERWRITE_OUTPUT=true; shift ;;
    --subscription-id) require_value "$1" "${2:-}"; SUBSCRIPTION_ID="$2"; shift 2 ;;
    --tenant-id) require_value "$1" "${2:-}"; TENANT_ID="$2"; shift 2 ;;
    --name) require_value "$1" "${2:-}"; IDENTITY_NAME="$2"; shift 2 ;;
    --region) require_value "$1" "${2:-}"; REGION="$2"; shift 2 ;;
    --output-file) require_value "$1" "${2:-}"; OUTPUT_FILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

require_value "--subscription-id" "${SUBSCRIPTION_ID}"
require_value "--tenant-id" "${TENANT_ID}"

if [[ "${APPLY}" != "true" ]]; then
  cat <<PLAN
Dry-run only. No Azure resources were changed.

Planned Azure deployment identity:
  subscription_id: ${SUBSCRIPTION_ID}
  tenant_id: ${TENANT_ID}
  service_principal: ${IDENTITY_NAME}
  region: ${REGION}
  roles:
    - Contributor at /subscriptions/${SUBSCRIPTION_ID}
    - User Access Administrator at /subscriptions/${SUBSCRIPTION_ID}

Run again with --apply after reviewing the role scope and active Azure CLI identity.
PLAN
  exit 0
fi

command -v az >/dev/null || { echo "az CLI is required" >&2; exit 2; }

ACTIVE_SUBSCRIPTION="$(az account show --query id -o tsv)"
ACTIVE_TENANT="$(az account show --query tenantId -o tsv)"
if [[ "${ACTIVE_SUBSCRIPTION}" != "${SUBSCRIPTION_ID}" ]]; then
  echo "Active Azure subscription ${ACTIVE_SUBSCRIPTION} does not match expected ${SUBSCRIPTION_ID}" >&2
  exit 1
fi
if [[ "${ACTIVE_TENANT}" != "${TENANT_ID}" ]]; then
  echo "Active Azure tenant ${ACTIVE_TENANT} does not match expected ${TENANT_ID}" >&2
  exit 1
fi

SCOPE="/subscriptions/${SUBSCRIPTION_ID}"
APP_LIST="$(az ad app list --display-name "${IDENTITY_NAME}" -o json)"
APP_COUNT="$(python3 -c 'import json,sys; print(len(json.load(sys.stdin)))' <<<"${APP_LIST}")"

if [[ "${APP_COUNT}" -gt 1 ]]; then
  echo "More than one Azure app registration is named ${IDENTITY_NAME}; use a unique --name." >&2
  exit 1
fi

if [[ "${APP_COUNT}" -eq 1 ]]; then
  CLIENT_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["appId"])' <<<"${APP_LIST}")"
  if [[ "${ROTATE_CLIENT_SECRET}" != "true" ]]; then
    echo "Azure app registration ${IDENTITY_NAME} already exists." >&2
    echo "Refusing to create a new client secret. Re-run with --rotate-client-secret if intentional." >&2
    exit 1
  fi
  if ! az ad sp show --id "${CLIENT_ID}" >/dev/null 2>&1; then
    az ad sp create --id "${CLIENT_ID}" >/dev/null
  fi
  SP_JSON="$(az ad app credential reset --id "${CLIENT_ID}" --append --years 1 -o json)"
  CLIENT_SECRET="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["password"])' <<<"${SP_JSON}")"
else
  SP_JSON="$(az ad sp create-for-rbac \
    --name "${IDENTITY_NAME}" \
    --role Contributor \
    --scopes "${SCOPE}" \
    --years 1 \
    -o json)"
  CLIENT_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["appId"])' <<<"${SP_JSON}")"
  CLIENT_SECRET="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["password"])' <<<"${SP_JSON}")"
fi

ensure_role_assignment() {
  local role="$1"
  local existing
  existing="$(az role assignment list \
    --assignee "${CLIENT_ID}" \
    --role "${role}" \
    --scope "${SCOPE}" \
    --query '[0].id' \
    -o tsv)"
  if [[ -z "${existing}" ]]; then
    az role assignment create \
      --assignee "${CLIENT_ID}" \
      --role "${role}" \
      --scope "${SCOPE}" >/dev/null
  fi
}

ensure_role_assignment "Contributor"
ensure_role_assignment "User Access Administrator"

render_connection_json() {
  python3 - "$IDENTITY_NAME" "$SUBSCRIPTION_ID" "$TENANT_ID" "$CLIENT_ID" "$CLIENT_SECRET" "$REGION" <<'PY'
import json
import sys

name, subscription_id, tenant_id, client_id, client_secret, region = sys.argv[1:]
print(json.dumps({
    "provider": "azure",
    "display_name": name,
    "auth_type": "service_principal",
    "cloud_scope": {
        "subscription_id": subscription_id,
        "tenant_id": tenant_id,
        "region": region,
        "identity_name": name,
    },
    "azure": {
        "subscription_id": subscription_id,
        "client_id": client_id,
        "client_secret": client_secret,
        "tenant_id": tenant_id,
        "region": region,
    },
}, indent=2))
PY
}

if [[ -n "${OUTPUT_FILE}" ]]; then
  if [[ -e "${OUTPUT_FILE}" && "${OVERWRITE_OUTPUT}" != "true" ]]; then
    echo "Output file already exists: ${OUTPUT_FILE}" >&2
    echo "Refusing to overwrite local secret material. Re-run with --overwrite-output if intentional." >&2
    exit 1
  fi
  umask 077
  render_connection_json > "${OUTPUT_FILE}"
  echo "CloudConnection import JSON written to ${OUTPUT_FILE}" >&2
else
  render_connection_json
fi
