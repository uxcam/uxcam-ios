#!/bin/bash
set -euo pipefail

readonly repository="uxcam/uxcam-ios"
readonly branch="main"

for command in gh jq; do
  if ! command -v "$command" >/dev/null; then
    echo "error: required command is missing: $command" >&2
    exit 1
  fi
done

visibility="$(gh api "repos/$repository" --jq .visibility)"
if [[ "$visibility" != "public" ]]; then
  echo "error: branch protection is unavailable on this private repository's current plan" >&2
  exit 1
fi

is_admin="$(gh api "repos/$repository" --jq .permissions.admin)"
if [[ "$is_admin" != "true" ]]; then
  echo "error: repository admin permission is required" >&2
  exit 1
fi

gh api --method PUT "repos/$repository/branches/$branch/protection" \
  --input - >/dev/null <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Manifests, tooling, and repository size",
      "Audit workflows"
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "require_last_push_approval": true,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": false
}
JSON

protection="$(gh api "repos/$repository/branches/$branch/protection")"
jq -e '
  .required_status_checks.strict == true
  and .required_pull_request_reviews.dismiss_stale_reviews == true
  and .required_pull_request_reviews.require_code_owner_reviews == true
  and .required_pull_request_reviews.require_last_push_approval == true
  and .required_pull_request_reviews.required_approving_review_count == 1
  and .required_conversation_resolution.enabled == true
  and .allow_force_pushes.enabled == false
  and .allow_deletions.enabled == false
' <<<"$protection" >/dev/null

echo "Branch protection verified for $repository:$branch"
