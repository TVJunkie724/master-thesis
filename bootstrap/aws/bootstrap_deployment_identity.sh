#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

APPLY=false
ROTATE_ACCESS_KEYS=false
OVERWRITE_OUTPUT=false
ACCOUNT_ID=""
IDENTITY_NAME="twin2mc-deployer"
REGION="eu-central-1"
PERMISSION_SET_VERSION="thesis-demo-v1"
POLICY_FILE="${REPO_ROOT}/3-cloud-deployer/docs/references/aws_deployer_policy.json"
OUTPUT_FILE=""

usage() {
  cat <<'USAGE'
Usage:
  bootstrap/aws/bootstrap_deployment_identity.sh --account-id <aws-account-id> [options]

Options:
  --apply                    Create/update the IAM identity. Without this flag, the script is dry-run only.
  --rotate-access-keys       Delete existing access keys for this bootstrap IAM user before creating a new one.
  --overwrite-output         Allow overwriting --output-file if it already exists.
  --account-id <id>          Expected AWS account id for the active admin/bootstrap session.
  --name <name>              IAM user and CloudConnection display name. Default: twin2mc-deployer.
  --region <region>          Default deployment region. Default: eu-central-1.
  --policy-file <path>       IAM policy document. Default: 3-cloud-deployer/docs/references/aws_deployer_policy.json.
  --output-file <path>       Write CloudConnection JSON to this local file instead of stdout.
  -h, --help                 Show this help.

The script never accepts admin secrets as arguments. Authenticate the AWS CLI
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
    --rotate-access-keys) ROTATE_ACCESS_KEYS=true; shift ;;
    --overwrite-output) OVERWRITE_OUTPUT=true; shift ;;
    --account-id) require_value "$1" "${2:-}"; ACCOUNT_ID="$2"; shift 2 ;;
    --name) require_value "$1" "${2:-}"; IDENTITY_NAME="$2"; shift 2 ;;
    --region) require_value "$1" "${2:-}"; REGION="$2"; shift 2 ;;
    --policy-file) require_value "$1" "${2:-}"; POLICY_FILE="$2"; shift 2 ;;
    --output-file) require_value "$1" "${2:-}"; OUTPUT_FILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

require_value "--account-id" "${ACCOUNT_ID}"
if [[ ! -f "${POLICY_FILE}" ]]; then
  echo "Policy file not found: ${POLICY_FILE}" >&2
  exit 2
fi
python3 -m json.tool "${POLICY_FILE}" >/dev/null

if [[ "${APPLY}" != "true" ]]; then
  cat <<PLAN
Dry-run only. No AWS resources were changed.

Planned AWS deployment identity:
  account_id: ${ACCOUNT_ID}
  iam_user: ${IDENTITY_NAME}
  region: ${REGION}
  permission_set_version: ${PERMISSION_SET_VERSION}
  inline_policy: ${POLICY_FILE}

Run again with --apply after reviewing the policy and active AWS CLI identity.
PLAN
  exit 0
fi

command -v aws >/dev/null || { echo "aws CLI is required" >&2; exit 2; }

CALLER_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
if [[ "${CALLER_ACCOUNT}" != "${ACCOUNT_ID}" ]]; then
  echo "Active AWS account ${CALLER_ACCOUNT} does not match expected ${ACCOUNT_ID}" >&2
  exit 1
fi

if ! aws iam get-user --user-name "${IDENTITY_NAME}" >/dev/null 2>&1; then
  aws iam create-user --user-name "${IDENTITY_NAME}" >/dev/null
fi

aws iam put-user-policy \
  --user-name "${IDENTITY_NAME}" \
  --policy-name "${IDENTITY_NAME}-deployment-policy" \
  --policy-document "file://${POLICY_FILE}" >/dev/null

EXISTING_ACCESS_KEYS_TEXT="$(aws iam list-access-keys \
  --user-name "${IDENTITY_NAME}" \
  --query 'AccessKeyMetadata[].AccessKeyId' \
  --output text)"
EXISTING_ACCESS_KEYS=()
while IFS= read -r key_id; do
  [[ -n "${key_id}" ]] && EXISTING_ACCESS_KEYS+=("${key_id}")
done < <(printf "%s\n" "${EXISTING_ACCESS_KEYS_TEXT}" | tr '\t' '\n')

if [[ "${#EXISTING_ACCESS_KEYS[@]}" -gt 0 && "${ROTATE_ACCESS_KEYS}" != "true" ]]; then
  echo "IAM user ${IDENTITY_NAME} already has access key(s)." >&2
  echo "Refusing to create another key. Re-run with --rotate-access-keys after confirming old keys can be deleted." >&2
  exit 1
fi

if [[ "${ROTATE_ACCESS_KEYS}" == "true" ]]; then
  for key_id in "${EXISTING_ACCESS_KEYS[@]}"; do
    aws iam delete-access-key --user-name "${IDENTITY_NAME}" --access-key-id "${key_id}" >/dev/null
  done
fi

read -r ACCESS_KEY_ID SECRET_ACCESS_KEY < <(
  aws iam create-access-key \
    --user-name "${IDENTITY_NAME}" \
    --query 'AccessKey.[AccessKeyId,SecretAccessKey]' \
    --output text
)

render_connection_json() {
  python3 - "$IDENTITY_NAME" "$ACCOUNT_ID" "$REGION" "$PERMISSION_SET_VERSION" "$ACCESS_KEY_ID" "$SECRET_ACCESS_KEY" <<'PY'
import json
import sys

name, account_id, region, permission_set_version, access_key_id, secret_access_key = sys.argv[1:]
print(json.dumps({
    "provider": "aws",
    "display_name": name,
    "auth_type": "access_key",
    "permission_set_version": permission_set_version,
    "cloud_scope": {
        "account_id": account_id,
        "region": region,
        "identity_name": name,
    },
    "aws": {
        "access_key_id": access_key_id,
        "secret_access_key": secret_access_key,
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
