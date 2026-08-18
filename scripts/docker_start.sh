#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

if ! command -v docker >/dev/null 2>&1; then
    echo "docker_start: docker is not installed or not on PATH" >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "docker_start: Docker Compose v2 is required" >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "docker_start: Docker daemon is not reachable" >&2
    exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    PYTHON_BIN=python3
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "docker_start: python or python3 is required for smoke testing" >&2
    exit 1
fi

show_diagnostics() {
    docker compose ps >&2 || true
    docker compose logs \
        --no-color \
        --tail=200 \
        chat-api >&2 || true
}

echo "docker_start: building and starting chat-api"
docker compose up --build --detach

if [ -n "${CHAT_API_BASE_URL:-}" ]; then
    BASE_URL="${CHAT_API_BASE_URL}"
else
    if ! PUBLISHED_ADDRESS="$(
        docker compose port chat-api 8000 | head -n 1
    )"; then
        echo "docker_start: cannot query the published chat-api port" >&2
        show_diagnostics
        exit 1
    fi

    HOST_PORT="${PUBLISHED_ADDRESS##*:}"

    if [[ ! "${HOST_PORT}" =~ ^[0-9]+$ ]]; then
        echo "docker_start: cannot resolve the published chat-api port" >&2
        show_diagnostics
        exit 1
    fi

    BASE_URL="http://127.0.0.1:${HOST_PORT}"
fi

echo "docker_start: running release smoke test against ${BASE_URL}"
if ! "${PYTHON_BIN}" scripts/docker_smoke_test.py \
    --base-url "${BASE_URL}" \
    --wait-timeout-seconds "${CHAT_API_WAIT_TIMEOUT_SECONDS:-120}"
then
    show_diagnostics
    exit 1
fi

docker compose ps
echo "docker_start: chat-api is ready at ${BASE_URL}"
echo "docker_start: stop with 'docker compose down'"
