#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  printf 'Missing %s. Copy .env.example and configure it first.\n' "$ENV_FILE" >&2
  exit 1
fi

if ! command -v op >/dev/null 2>&1; then
  printf '1Password CLI (op) is required. Install it and sign in before continuing.\n' >&2
  exit 1
fi

resolved_env="$(mktemp "${TMPDIR:-/tmp}/audiobookbay-automated.env.XXXXXX")"
trap 'rm -f "$resolved_env"' EXIT

op inject --in-file "$ENV_FILE" --out-file "$resolved_env"
APP_ENV_FILE="$resolved_env" docker compose --env-file "$ENV_FILE" -f "$ROOT_DIR/docker-compose.yaml" "$@"
