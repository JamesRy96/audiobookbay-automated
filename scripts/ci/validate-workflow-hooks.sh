#!/usr/bin/env bash
set -euo pipefail

config_hooks=()
workflow_hooks=()
while IFS= read -r hook; do
  config_hooks+=("$hook")
done < <(awk '/^      - id: / { print $3 }' .pre-commit-config.yaml | sort -u)

while IFS= read -r hook; do
  workflow_hooks+=("$hook")
done < <(sed -nE 's/.*pre-commit run ([^ ]+).*/\1/p' .github/workflows/ci.yml | sort -u)

for hook in "${config_hooks[@]}"; do
  if [[ ! " ${workflow_hooks[*]} " == *" $hook "* ]]; then
    printf 'Hook is configured but not invoked by Actions: %s\n' "$hook" >&2
    exit 1
  fi
done

for hook in "${workflow_hooks[@]}"; do
  if [[ ! " ${config_hooks[*]} " == *" $hook "* ]]; then
    printf 'Actions invokes an unknown pre-commit hook: %s\n' "$hook" >&2
    exit 1
  fi
done

printf 'Validated %d pre-commit hooks against the Actions workflow.\n' "${#config_hooks[@]}"
