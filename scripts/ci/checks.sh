#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# shellcheck disable=SC1091
source "$ROOT_DIR/scripts/ci/tool-versions.env"

run_hook() {
  local hook="$1"
  shift
  local targets=("$@")
  if ((${#targets[@]} == 0)); then
    targets=(.)
  fi
  local semgrep_targets=("${targets[@]}")
  if [[ "$hook" == semgrep && "$#" -eq 0 ]]; then
    mapfile -t semgrep_targets < <(
      git ls-files | awk '$0 ~ /\.py$/ { print }'
    )
  fi

  case "$hook" in
    ruff-check)
      uvx --from "ruff==${RUFF_VERSION}" ruff check "${targets[@]}"
      ;;
    ruff-format)
      uvx --from "ruff==${RUFF_VERSION}" ruff format "${targets[@]}"
      ;;
    ruff-format-check)
      uvx --from "ruff==${RUFF_VERSION}" ruff format --check "${targets[@]}"
      ;;
    pytest)
      uv run --extra test pytest -q
      ;;
    bandit)
      if (($#)); then
        uvx --from "bandit[toml]==${BANDIT_VERSION}" bandit -ll -ii \
          "$@"
      else
        uvx --from "bandit[toml]==${BANDIT_VERSION}" bandit -r \
          app -ll -ii
      fi
      ;;
    semgrep)
      uvx --from "semgrep==${SEMGREP_VERSION}" semgrep scan \
        --config=p/python --config=p/security-audit --error \
        "${semgrep_targets[@]}"
      ;;
    pip-audit)
      uv export --frozen --no-dev \
        --no-emit-project --format requirements-txt |
        uvx --from "pip-audit==${PIP_AUDIT_VERSION}" pip-audit \
          --strict -r /dev/stdin
      ;;
    hadolint)
      local dockerfile="Dockerfile"
      if (($#)); then
        dockerfile="$1"
      fi
      docker run --rm -i -v "$ROOT_DIR:/src:ro" \
        "ghcr.io/hadolint/hadolint:v${HADOLINT_VERSION}" \
        hadolint --config /src/.hadolint.yaml "/src/$dockerfile"
      ;;
    trivy-config)
      docker run --rm -v "$ROOT_DIR:/src:ro" \
        -v "${TRIVY_CACHE_DIR:-/tmp/trivy-cache}:/tmp/trivy-cache" \
        "aquasec/trivy:${TRIVY_VERSION}" config \
        --config /src/trivy.yaml --ignorefile /src/.trivyignore \
        --cache-dir /tmp/trivy-cache --skip-version-check \
        /src
      ;;
    trivy-fs)
      docker run --rm -v "$ROOT_DIR:/src:ro" \
        -v "${TRIVY_CACHE_DIR:-/tmp/trivy-cache}:/tmp/trivy-cache" \
        "aquasec/trivy:${TRIVY_VERSION}" fs \
        --config /src/trivy.yaml --scanners vuln,secret \
        --cache-dir /tmp/trivy-cache --skip-version-check \
        /src
      ;;
    detect-secrets)
      if (($#)); then
        uvx --from "detect-secrets==${DETECT_SECRETS_VERSION}" \
          detect-secrets-hook --baseline .secrets.baseline "$@"
      else
        git ls-files -z ':!.secrets.baseline' \
          ':!uv.lock' |
          xargs -0 -r uvx --from "detect-secrets==${DETECT_SECRETS_VERSION}" \
            detect-secrets-hook --baseline .secrets.baseline
      fi
      ;;
    trufflehog)
      local base_sha="${TRUFFLEHOG_BASE_SHA:-HEAD}"
      if [[ "$base_sha" =~ ^0+$ ]]; then
        base_sha="$(git rev-list --max-parents=0 HEAD | tail -n 1)"
      fi
      docker run --rm -v "$ROOT_DIR:/src:ro" \
        "trufflesecurity/trufflehog:${TRUFFLEHOG_VERSION}" git file:///src \
        --since-commit "$base_sha" --results=unknown,unverified \
        --fail --no-verification --trust-local-git-config
      ;;
    *)
      printf 'Unknown check: %s\n' "$hook" >&2
      exit 2
      ;;
  esac
}

case "${1:-}" in
  quality)
    run_hook ruff-check "${@:2}"
    run_hook ruff-format-check
    run_hook pytest
    ;;
  python-security)
    run_hook bandit "${@:2}"
    run_hook semgrep "${@:2}"
    ;;
  dependencies)
    run_hook pip-audit
    ;;
  containers)
    run_hook hadolint "${@:2}"
    run_hook trivy-config
    run_hook trivy-fs
    ;;
  secrets)
    run_hook detect-secrets "${@:2}"
    run_hook trufflehog
    ;;
  ruff-check|ruff-format|ruff-format-check|pytest|bandit|semgrep|pip-audit|hadolint|trivy-config|trivy-fs|detect-secrets|trufflehog)
    run_hook "$@"
    ;;
  *)
    printf 'Usage: %s {quality|python-security|dependencies|containers|secrets|hook} [files...]\n' "$0" >&2
    exit 2
    ;;
esac
