#!/usr/bin/env bash
# Add a new version to an agent from a local schema-v1 export file.
# For payloads too big to send inline through update_agent: the file goes straight to the
# backend, never through the model's context.
#
# Usage: import_version.sh <agent_key> <new_version> <from_version> <payload.json>
# Needs: CRAFTER_HOST (no trailing slash) and CRAFTER_API_KEY (drm_pub_xxx.drm_sk_xxx), jq, curl.
set -euo pipefail

[ $# -eq 4 ] || { echo "usage: $0 <agent_key> <new_version> <from_version> <payload.json>" >&2; exit 2; }
key=$1 new=$2 from=$3 file=$4
host=${CRAFTER_HOST:-}
api_key=${CRAFTER_API_KEY:-}
[ -n "$host" ] && [ -n "$api_key" ] || { echo "set CRAFTER_HOST and CRAFTER_API_KEY" >&2; exit 2; }

# Key goes in via a curl config on a file descriptor, so it never shows up in `ps`.
jq -c --arg v "$new" --arg f "$from" \
  '{version_number: $v, created_from_version_number: $f, payload: (.version.version_number = $v)}' "$file" |
  curl -sS --fail-with-body -X POST "${host%/}/api/agent-crafter/agents/$key/versions/import" \
    -K <(printf 'header = "Authorization: ApiKey %s"\n' "$api_key") \
    -H 'Content-Type: application/json' -H 'Accept: application/json' \
    --data-binary @-
echo
