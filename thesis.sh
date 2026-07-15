#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
FLUTTER_DIR="$REPO_ROOT/twin2multicloud_flutter"
FLUTTER_CONFIG_DIR="$FLUTTER_DIR/config"
FLUTTER_DEV_CONFIG="$FLUTTER_CONFIG_DIR/dev.json"
FLUTTER_DEMO_CONFIG="$FLUTTER_CONFIG_DIR/demo.json"

THESIS_COMPOSE_PROJECT="${THESIS_COMPOSE_PROJECT:-master-thesis}"
THESIS_OPTIMIZER_PORT="${THESIS_OPTIMIZER_PORT:-5003}"
THESIS_DEPLOYER_PORT="${THESIS_DEPLOYER_PORT:-5004}"
THESIS_MANAGEMENT_API_PORT="${THESIS_MANAGEMENT_API_PORT:-5005}"
THESIS_DOCS_PORT="${THESIS_DOCS_PORT:-5010}"
THESIS_API_BASE_URL="${THESIS_API_BASE_URL:-http://localhost:${THESIS_MANAGEMENT_API_PORT}}"
THESIS_DEV_AUTH_TOKEN="${THESIS_DEV_AUTH_TOKEN:-dev-token}"
THESIS_FLUTTER_DEVICE="${THESIS_FLUTTER_DEVICE:-macos}"
THESIS_DEMO_SCENARIO="${THESIS_DEMO_SCENARIO:-showcase}"
THESIS_DOCKER_CONTEXT="${THESIS_DOCKER_CONTEXT:-}"
THESIS_RUNTIME_SECRETS_DIR="${THESIS_RUNTIME_SECRETS_DIR:-$REPO_ROOT/.secrets/runtime}"
THESIS_LOCAL_DATABASE_PATH="${THESIS_LOCAL_DATABASE_PATH:-$REPO_ROOT/twin2multicloud_backend/data/app.db}"
if [[ "$THESIS_RUNTIME_SECRETS_DIR" != /* ]]; then
  THESIS_RUNTIME_SECRETS_DIR="$REPO_ROOT/$THESIS_RUNTIME_SECRETS_DIR"
fi
if [[ "$THESIS_LOCAL_DATABASE_PATH" != /* ]]; then
  THESIS_LOCAL_DATABASE_PATH="$REPO_ROOT/$THESIS_LOCAL_DATABASE_PATH"
fi
export THESIS_OPTIMIZER_PORT
export THESIS_DEPLOYER_PORT
export THESIS_MANAGEMENT_API_PORT
export THESIS_DOCS_PORT
export THESIS_RUNTIME_SECRETS_DIR

WITH_CREDENTIALS=0
SKIP_SMOKE=0
NO_FLUTTER=0
RUN_SETUP=0
BUILD_IMAGES=0
FLUTTER_DEVICE="$THESIS_FLUTTER_DEVICE"
DEMO_SCENARIO="$THESIS_DEMO_SCENARIO"
FLUTTER_ARGS=()
FLUTTER_ARGS_COUNT=0

usage() {
  cat <<'USAGE'
Usage:
  ./thesis.sh up [options] [-- <extra flutter run args>]
  ./thesis.sh flutter [options] [-- <extra flutter run args>]
  ./thesis.sh demo [options] [-- <extra flutter run args>]
  ./thesis.sh config
  ./thesis.sh setup
  ./thesis.sh secrets
  ./thesis.sh status
  ./thesis.sh logs [service]
  ./thesis.sh down
  ./thesis.sh test backend
  ./thesis.sh test frontend
  ./thesis.sh test frontend-integration
  ./thesis.sh latex [watch|once|clean|logs]
  ./thesis.sh docs [up|down|logs]

App commands:
  up                 Start backend containers, smoke-check them, write Flutter
                     config/dev.json, then start Flutter.
  flutter            Write Flutter config and start Flutter only.
  demo               Start the offline Flutter demo without Docker or APIs.
  config             Write twin2multicloud_flutter/config/dev.json only.
  setup              Write config and run flutter pub get.
  secrets            Create or validate durable local Management API secrets.
  status             Print URLs and matching Docker containers.
  logs [service]     Follow Docker logs. Service examples: management-api,
                     2twin2clouds, 3cloud-deployer.
  down               Stop app/docs containers for this compose project.
  test backend       Run Management API tests without tests/e2e.
  test frontend      Run static architecture, analysis, unit/widget, and build gates.
  test frontend-integration
                     Run read-only Flutter contracts against credential-free
                     local containers. Requires the macOS desktop toolchain;
                     cloud credentials and cloud mutations are not supported.

LaTeX commands:
  latex watch        Run latexmk watch mode in Docker.
  latex once         Compile twin2multicloud-latex/main.tex once in Docker.
  latex clean        Remove LaTeX build artifacts in Docker.
  latex logs         Show LaTeX container logs if a watch container is running.

Docs commands:
  docs up            Start MkDocs on THESIS_DOCS_PORT.
  docs down          Stop docs container.
  docs logs          Follow docs logs.

Options for up/flutter/setup:
  --device ID        Flutter device id. Default: THESIS_FLUTTER_DEVICE or macos.
  --setup            Run flutter pub get before flutter run.
  --no-flutter       For up: start containers and write config, but do not run Flutter.
  --skip-smoke       Skip HTTP smoke checks after docker compose up.
  --build            Build images before docker compose up.
  --with-credentials Add compose.cloud.local.yaml and mount .secrets/local.
  -h, --help         Show this help.

Options for demo:
  --device ID        Flutter device id. Default: THESIS_FLUTTER_DEVICE or macos.
  --scenario NAME    Fixture scenario: showcase, empty, or degraded.
  --setup            Run flutter pub get before flutter run.
  -h, --help         Show this help.

Environment:
  THESIS_COMPOSE_PROJECT       Compose project name. Default: master-thesis.
  THESIS_OPTIMIZER_PORT        Host port for Optimizer. Default: 5003.
  THESIS_DEPLOYER_PORT         Host port for Deployer. Default: 5004.
  THESIS_MANAGEMENT_API_PORT   Host port for Management API. Default: 5005.
  THESIS_DOCS_PORT             Host port for MkDocs. Default: 5010.
  THESIS_API_BASE_URL          Flutter API URL. Default: http://localhost:${THESIS_MANAGEMENT_API_PORT}.
  THESIS_DEV_AUTH_TOKEN        Flutter dev auth token. Default: dev-token.
  THESIS_DEMO_SCENARIO         Offline fixture scenario. Default: showcase.
  THESIS_DOCKER_CONTEXT        Optional Docker context name.
  THESIS_RUNTIME_SECRETS_DIR   Local runtime secret directory. Default: .secrets/runtime.
  THESIS_LOCAL_DATABASE_PATH   Local Management API SQLite path used by the migration guard.

Default startup is credential-free. Use --with-credentials only when
.secrets/local contains intentional local cloud credentials for supervised
cloud validation or sample seeding.
USAGE
}

fail() {
  echo "ERROR: $*" >&2
  exit 2
}

info() {
  echo "==> $*"
}

docker_cmd() {
  if [ -n "$THESIS_DOCKER_CONTEXT" ]; then
    docker --context "$THESIS_DOCKER_CONTEXT" "$@"
  else
    docker "$@"
  fi
}

compose_cmd() {
  local args=(compose -p "$THESIS_COMPOSE_PROJECT" -f "$REPO_ROOT/compose.yaml")
  if [ "$WITH_CREDENTIALS" -eq 1 ]; then
    args+=(-f "$REPO_ROOT/compose.cloud.local.yaml")
  fi

  THESIS_OPTIMIZER_PORT="$THESIS_OPTIMIZER_PORT" \
  THESIS_DEPLOYER_PORT="$THESIS_DEPLOYER_PORT" \
  THESIS_MANAGEMENT_API_PORT="$THESIS_MANAGEMENT_API_PORT" \
  THESIS_DOCS_PORT="$THESIS_DOCS_PORT" \
  docker_cmd "${args[@]}" "$@"
}

compose_latex_cmd() {
  THESIS_OPTIMIZER_PORT="$THESIS_OPTIMIZER_PORT" \
  THESIS_DEPLOYER_PORT="$THESIS_DEPLOYER_PORT" \
  THESIS_MANAGEMENT_API_PORT="$THESIS_MANAGEMENT_API_PORT" \
  THESIS_DOCS_PORT="$THESIS_DOCS_PORT" \
  docker_cmd compose -p "$THESIS_COMPOSE_PROJECT" -f "$REPO_ROOT/compose.yaml" --profile latex "$@"
}

compose_docs_cmd() {
  THESIS_OPTIMIZER_PORT="$THESIS_OPTIMIZER_PORT" \
  THESIS_DEPLOYER_PORT="$THESIS_DEPLOYER_PORT" \
  THESIS_MANAGEMENT_API_PORT="$THESIS_MANAGEMENT_API_PORT" \
  THESIS_DOCS_PORT="$THESIS_DOCS_PORT" \
  docker_cmd compose -p "$THESIS_COMPOSE_PROJECT" -f "$REPO_ROOT/compose.yaml" --profile docs "$@"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "$1 is required but was not found on PATH."
}

require_docker() {
  require_command docker
  if [ -n "$THESIS_DOCKER_CONTEXT" ]; then
    docker --context "$THESIS_DOCKER_CONTEXT" context inspect "$THESIS_DOCKER_CONTEXT" >/dev/null 2>&1 ||
      fail "Docker context '$THESIS_DOCKER_CONTEXT' is not available."
  fi
}

require_flutter() {
  require_command flutter
  require_command dart
}

bootstrap_local_runtime_secrets() {
  require_command python3
  python3 "$REPO_ROOT/scripts/bootstrap_local_runtime_secrets.py" \
    --secrets-dir "$THESIS_RUNTIME_SECRETS_DIR" \
    --database "$THESIS_LOCAL_DATABASE_PATH"
}

require_cloud_secret_files() {
  local missing=0
  for path in \
    "$REPO_ROOT/.secrets/local/config.json" \
    "$REPO_ROOT/.secrets/local/config_credentials.json" \
    "$REPO_ROOT/.secrets/local/google-credentials.json" \
    "$REPO_ROOT/.secrets/local/gcp_credentials.json"
  do
    if [ ! -f "$path" ]; then
      echo "Missing required credential overlay file: $path" >&2
      missing=1
    fi
  done
  [ "$missing" -eq 0 ] || fail "Create .secrets/local files or run without --with-credentials."
}

parse_common_options() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --device)
        [ "$#" -ge 2 ] || fail "--device requires a value."
        FLUTTER_DEVICE="$2"
        shift 2
        ;;
      --setup)
        RUN_SETUP=1
        shift
        ;;
      --no-flutter)
        NO_FLUTTER=1
        shift
        ;;
      --skip-smoke)
        SKIP_SMOKE=1
        shift
        ;;
      --build)
        BUILD_IMAGES=1
        shift
        ;;
      --with-credentials)
        WITH_CREDENTIALS=1
        shift
        ;;
      --)
        shift
        FLUTTER_ARGS+=("$@")
        FLUTTER_ARGS_COUNT=$#
        break
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "Unknown option: $1"
        ;;
    esac
  done
}

parse_demo_options() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --device)
        [ "$#" -ge 2 ] || fail "--device requires a value."
        FLUTTER_DEVICE="$2"
        shift 2
        ;;
      --scenario)
        [ "$#" -ge 2 ] || fail "--scenario requires a value."
        DEMO_SCENARIO="$2"
        shift 2
        ;;
      --setup)
        RUN_SETUP=1
        shift
        ;;
      --)
        shift
        FLUTTER_ARGS+=("$@")
        FLUTTER_ARGS_COUNT=$#
        break
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "Unknown demo option: $1"
        ;;
    esac
  done
}

validate_demo_scenario() {
  case "$DEMO_SCENARIO" in
    showcase|empty|degraded) ;;
    *) fail "Unknown demo scenario: $DEMO_SCENARIO. Expected showcase, empty, or degraded." ;;
  esac
}

write_flutter_config() {
  require_command python3
  mkdir -p "$FLUTTER_CONFIG_DIR"
  THESIS_API_BASE_URL="$THESIS_API_BASE_URL" \
  THESIS_DEV_AUTH_TOKEN="$THESIS_DEV_AUTH_TOKEN" \
  python3 - "$FLUTTER_DEV_CONFIG" <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "APP_MODE": "development",
    "API_BASE_URL": os.environ["THESIS_API_BASE_URL"],
    "DEV_AUTH_TOKEN": os.environ["THESIS_DEV_AUTH_TOKEN"],
}
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
  info "Wrote Flutter config: $FLUTTER_DEV_CONFIG"
}

flutter_pub_get() {
  require_flutter
  (cd "$FLUTTER_DIR" && flutter pub get)
}

run_flutter() {
  require_flutter
  write_flutter_config
  if [ "$RUN_SETUP" -eq 1 ]; then
    flutter_pub_get
  fi
  info "Starting Flutter on device '$FLUTTER_DEVICE'."
  if [ "$FLUTTER_ARGS_COUNT" -gt 0 ]; then
    (cd "$FLUTTER_DIR" && flutter run -d "$FLUTTER_DEVICE" --dart-define-from-file=config/dev.json "${FLUTTER_ARGS[@]}")
  else
    (cd "$FLUTTER_DIR" && flutter run -d "$FLUTTER_DEVICE" --dart-define-from-file=config/dev.json)
  fi
}

run_demo() {
  require_flutter
  validate_demo_scenario
  [ -f "$FLUTTER_DEMO_CONFIG" ] || fail "Missing tracked demo config: $FLUTTER_DEMO_CONFIG"
  if [ "$RUN_SETUP" -eq 1 ]; then
    flutter_pub_get
  fi
  info "Starting offline Flutter demo '$DEMO_SCENARIO' on device '$FLUTTER_DEVICE'."
  if [ "$FLUTTER_ARGS_COUNT" -gt 0 ]; then
    (cd "$FLUTTER_DIR" && flutter run -d "$FLUTTER_DEVICE" \
      --dart-define-from-file=config/demo.json \
      --dart-define="DEMO_SCENARIO=$DEMO_SCENARIO" \
      "${FLUTTER_ARGS[@]}")
  else
    (cd "$FLUTTER_DIR" && flutter run -d "$FLUTTER_DEVICE" \
      --dart-define-from-file=config/demo.json \
      --dart-define="DEMO_SCENARIO=$DEMO_SCENARIO")
  fi
}

wait_for_url() {
  local label="$1"
  local url="$2"
  local attempts="${3:-30}"
  local delay="${4:-2}"

  require_command curl
  info "Waiting for $label: $url"
  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      info "$label is reachable."
      return 0
    fi
    sleep "$delay"
  done
  fail "$label did not become reachable: $url"
}

smoke_app() {
  wait_for_url "Management API" "${THESIS_API_BASE_URL%/}/health"
  wait_for_url "Optimizer API" "http://localhost:${THESIS_OPTIMIZER_PORT}/openapi.json"
  wait_for_url "Deployer API" "http://localhost:${THESIS_DEPLOYER_PORT}/"
}

up_app() {
  require_docker
  bootstrap_local_runtime_secrets
  if [ "$WITH_CREDENTIALS" -eq 1 ]; then
    require_cloud_secret_files
  fi
  if [ "$BUILD_IMAGES" -eq 1 ]; then
    compose_cmd build
  fi
  compose_cmd up -d 2twin2clouds 3cloud-deployer management-api
  write_flutter_config
  if [ "$SKIP_SMOKE" -eq 0 ]; then
    smoke_app
  fi
  if [ "$NO_FLUTTER" -eq 0 ]; then
    run_flutter
  else
    print_status
  fi
}

print_status() {
  cat <<EOF
Twin2MultiCloud
  Compose project: $THESIS_COMPOSE_PROJECT
  Credential overlay: $([ "$WITH_CREDENTIALS" -eq 1 ] && echo enabled || echo disabled)

Application URLs
  Management API: ${THESIS_API_BASE_URL}
  Optimizer API:  http://localhost:${THESIS_OPTIMIZER_PORT}
  Deployer API:   http://localhost:${THESIS_DEPLOYER_PORT}
  Docs site:      http://localhost:${THESIS_DOCS_PORT}

Flutter
  Config: $FLUTTER_DEV_CONFIG
  Device: $FLUTTER_DEVICE

Useful commands
  ./thesis.sh up --no-flutter
  ./thesis.sh flutter --device $FLUTTER_DEVICE
  ./thesis.sh latex once
EOF
  if command -v docker >/dev/null 2>&1; then
    docker_cmd ps \
      --filter "label=com.docker.compose.project=$THESIS_COMPOSE_PROJECT" \
      --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || true
  fi
}

run_backend_tests() {
  require_docker
  bootstrap_local_runtime_secrets
  compose_cmd run --rm --no-deps management-api python -m pytest tests/ --ignore=tests/e2e -q
}

run_frontend_tests() {
  require_command python3
  require_flutter
  [ -f "$FLUTTER_CONFIG_DIR/dev.example.json" ] ||
    fail "Missing tracked Flutter build config: $FLUTTER_CONFIG_DIR/dev.example.json"

  info "Testing the Flutter architecture gate."
  (cd "$REPO_ROOT" && python3 -m unittest scripts.tests.test_check_flutter_architecture)
  (cd "$REPO_ROOT" && python3 scripts/check_flutter_architecture.py)

  info "Checking Dart formatting and static analysis."
  (cd "$FLUTTER_DIR" && dart format --output=none --set-exit-if-changed lib test integration_test)
  (cd "$FLUTTER_DIR" && flutter analyze)

  info "Running Flutter unit and widget tests."
  (cd "$FLUTTER_DIR" && flutter test)

  info "Building Flutter Web release and macOS debug artifacts."
  (cd "$FLUTTER_DIR" && flutter build web --release --dart-define-from-file=config/dev.example.json)
  (cd "$FLUTTER_DIR" && flutter build macos --debug --dart-define-from-file=config/dev.example.json)
}

run_frontend_integration_tests() {
  require_docker
  require_flutter
  [ "$WITH_CREDENTIALS" -eq 0 ] ||
    fail "Frontend integration tests must run without cloud credential overlays."

  bootstrap_local_runtime_secrets

  info "Starting credential-free services for read-only Flutter integration tests."
  compose_cmd up -d 2twin2clouds 3cloud-deployer management-api
  write_flutter_config
  smoke_app

  info "Running the Management API readiness contract on macOS."
  (cd "$FLUTTER_DIR" && flutter test \
    integration_test/management_api_readiness_test.dart \
    -d macos \
    --dart-define-from-file=config/dev.json)
}

latex_command() {
  require_docker
  local subcommand="${1:-watch}"
  case "$subcommand" in
    watch)
      compose_latex_cmd run --rm thesis-latex
      ;;
    once)
      compose_latex_cmd run --rm thesis-latex latexmk -pdf -interaction=nonstopmode -cd /thesis/main.tex
      ;;
    clean)
      compose_latex_cmd run --rm thesis-latex latexmk -C -cd /thesis/main.tex
      ;;
    logs)
      compose_latex_cmd logs -f thesis-latex
      ;;
    -h|--help)
      usage
      ;;
    *)
      fail "Unknown latex command: $subcommand"
      ;;
  esac
}

docs_command() {
  require_docker
  local subcommand="${1:-up}"
  case "$subcommand" in
    up)
      compose_docs_cmd up -d docs
      wait_for_url "Docs site" "http://localhost:${THESIS_DOCS_PORT}/"
      ;;
    down)
      compose_docs_cmd stop docs
      ;;
    logs)
      compose_docs_cmd logs -f docs
      ;;
    -h|--help)
      usage
      ;;
    *)
      fail "Unknown docs command: $subcommand"
      ;;
  esac
}

main() {
  local command="${1:-help}"
  if [ "$#" -gt 0 ]; then
    shift
  fi

  case "$command" in
    up)
      parse_common_options "$@"
      up_app
      ;;
    flutter)
      parse_common_options "$@"
      run_flutter
      ;;
    demo)
      parse_demo_options "$@"
      run_demo
      ;;
    config)
      parse_common_options "$@"
      write_flutter_config
      ;;
    setup)
      parse_common_options "$@"
      bootstrap_local_runtime_secrets
      write_flutter_config
      flutter_pub_get
      ;;
    secrets)
      [ "$#" -eq 0 ] || fail "Unknown option for secrets: $1"
      bootstrap_local_runtime_secrets
      ;;
    status)
      parse_common_options "$@"
      print_status
      ;;
    logs)
      require_docker
      compose_cmd logs -f "$@"
      ;;
    down)
      parse_common_options "$@"
      require_docker
      compose_docs_cmd down --remove-orphans
      ;;
    test)
      local target="${1:-backend}"
      if [ "$#" -gt 0 ]; then
        shift
      fi
      [ "$#" -eq 0 ] || fail "Unknown option for test $target: $1"
      case "$target" in
        backend) run_backend_tests ;;
        frontend) run_frontend_tests ;;
        frontend-integration) run_frontend_integration_tests ;;
        *) fail "Unknown test target: $target" ;;
      esac
      ;;
    latex)
      latex_command "$@"
      ;;
    docs)
      docs_command "$@"
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      fail "Unknown command: $command"
      ;;
  esac
}

main "$@"
