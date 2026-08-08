#!/bin/sh
set -eu

: "${GF_SECURITY_ADMIN_USER:?Grafana admin user is required}"
: "${GF_SECURITY_ADMIN_PASSWORD:?Grafana admin password is required}"
: "${GRAFANA_VIEWER_USER:?Grafana viewer user is required}"
: "${GRAFANA_VIEWER_PASSWORD:?Grafana viewer password is required}"
: "${RAW_HISTORY_READER_URL:?Raw-history reader URL is required}"
: "${RAW_HISTORY_READER_KEY:?Raw-history reader key is required}"

case "${RAW_HISTORY_READER_URL}" in
  https://*) ;;
  *)
    echo "Raw-history reader URL must use HTTPS" >&2
    exit 1
    ;;
esac
if ! printf '%s' "${RAW_HISTORY_READER_URL}" | grep -Eq '^https://[A-Za-z0-9.-]+/?$'; then
  echo "Raw-history reader URL contains unsupported characters" >&2
  exit 1
fi
if ! printf '%s' "${GRAFANA_VIEWER_USER}" | grep -Eq '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+$'; then
  echo "Grafana viewer user must be an email address" >&2
  exit 1
fi

escaped_reader_url=$(printf '%s' "${RAW_HISTORY_READER_URL%/}" | sed 's/[&|]/\\&/g')
sed "s|__RAW_HISTORY_READER_URL__|${escaped_reader_url}|g" \
  /opt/twin2multicloud/dashboard.json.template \
  > /etc/grafana/provisioning/dashboards/content/twin2multicloud.json

/run.sh &
grafana_pid=$!
trap 'kill -TERM "${grafana_pid}" 2>/dev/null || true' INT TERM

attempt=0
until curl --fail --silent --show-error --insecure \
  --user "${GF_SECURITY_ADMIN_USER}:${GF_SECURITY_ADMIN_PASSWORD}" \
  https://127.0.0.1:3000/api/health >/dev/null; do
  attempt=$((attempt + 1))
  if [ "${attempt}" -ge 60 ]; then
    echo "Grafana did not become ready in time" >&2
    kill -TERM "${grafana_pid}" 2>/dev/null || true
    wait "${grafana_pid}" || true
    exit 1
  fi
  sleep 1
done

lookup_response=$(curl --fail --silent --show-error --insecure \
  --user "${GF_SECURITY_ADMIN_USER}:${GF_SECURITY_ADMIN_PASSWORD}" \
  --get --data-urlencode "loginOrEmail=${GRAFANA_VIEWER_USER}" \
  https://127.0.0.1:3000/api/users/lookup 2>/dev/null || true)
viewer_id=$(printf '%s' "${lookup_response}" | sed -n 's/.*"id":[[:space:]]*\([0-9][0-9]*\).*/\1/p')

if [ -z "${viewer_id}" ]; then
  create_response=$(curl --fail --silent --show-error --insecure \
    --user "${GF_SECURITY_ADMIN_USER}:${GF_SECURITY_ADMIN_PASSWORD}" \
    --header 'Content-Type: application/json' \
    --data "{\"name\":\"Twin2MultiCloud Viewer\",\"email\":\"${GRAFANA_VIEWER_USER}\",\"login\":\"${GRAFANA_VIEWER_USER}\",\"password\":\"${GRAFANA_VIEWER_PASSWORD}\"}" \
    https://127.0.0.1:3000/api/admin/users)
  viewer_id=$(printf '%s' "${create_response}" | sed -n 's/.*"id":[[:space:]]*\([0-9][0-9]*\).*/\1/p')
  if [ -z "${viewer_id}" ]; then
    echo "Grafana viewer bootstrap did not return a user ID" >&2
    exit 1
  fi
else
  curl --fail --silent --show-error --insecure \
    --user "${GF_SECURITY_ADMIN_USER}:${GF_SECURITY_ADMIN_PASSWORD}" \
    --request PUT --header 'Content-Type: application/json' \
    --data "{\"password\":\"${GRAFANA_VIEWER_PASSWORD}\"}" \
    "https://127.0.0.1:3000/api/admin/users/${viewer_id}/password" >/dev/null
fi

curl --fail --silent --show-error --insecure \
  --user "${GF_SECURITY_ADMIN_USER}:${GF_SECURITY_ADMIN_PASSWORD}" \
  --request PATCH --header 'Content-Type: application/json' \
  --data '{"role":"Viewer"}' \
  "https://127.0.0.1:3000/api/org/users/${viewer_id}" >/dev/null

probe_reader() {
  bucket_seconds="$1"
  from_time="$2"
  to_time="$3"
  response=$(curl --fail --silent --show-error \
    --header "x-twin2multicloud-reader-key: ${RAW_HISTORY_READER_KEY}" \
    --get \
    --data-urlencode 'device_id=poc-device-001' \
    --data-urlencode 'metric=temperature' \
    --data-urlencode "from=${from_time}" \
    --data-urlencode "to=${to_time}" \
    --data-urlencode "bucket_seconds=${bucket_seconds}" \
    --data-urlencode 'limit=1' \
    "${RAW_HISTORY_READER_URL%/}/raw-history/v1") || return 1
  printf '%s' "${response}" | grep -q '"schema_version":"raw-history-query.v1"'
}

probe_datasource_health() {
  response=$(curl --fail --silent --show-error --insecure \
    --user "${GF_SECURITY_ADMIN_USER}:${GF_SECURITY_ADMIN_PASSWORD}" \
    https://127.0.0.1:3000/api/datasources/uid/twin2multicloud-raw-history/health) || return 1
  printf '%s' "${response}" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"OK"'
}

attempt=0
until probe_reader 0 '2026-01-01T00:00:00Z' '2026-01-02T00:00:00Z' \
  && probe_reader 3600 '2026-01-01T00:00:00Z' '2026-01-31T00:00:00Z' \
  && probe_datasource_health \
  && curl --fail --silent --show-error --insecure \
    --user "${GF_SECURITY_ADMIN_USER}:${GF_SECURITY_ADMIN_PASSWORD}" \
    https://127.0.0.1:3000/api/dashboards/uid/twin2multicloud-raw-rollups >/dev/null; do
  attempt=$((attempt + 1))
  if [ "${attempt}" -ge 60 ]; then
    echo "Grafana datasource, dashboard, or bounded reader probes did not become ready" >&2
    kill -TERM "${grafana_pid}" 2>/dev/null || true
    wait "${grafana_pid}" || true
    exit 1
  fi
  sleep 1
done

wait "${grafana_pid}"
