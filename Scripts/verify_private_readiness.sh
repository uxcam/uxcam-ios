#!/bin/bash
set -euo pipefail

readonly repository="uxcam/uxcam-ios"
readonly legacy_repository="uxcam/uxcam-ios-sdk"
readonly maximum_pack_bytes=$((5 * 1024 * 1024))

for command in curl gh git jq pod python3 swift xcodebuild; do
  if ! command -v "$command" >/dev/null; then
    echo "error: required command is missing: $command" >&2
    exit 1
  fi
done

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
Scripts/validate_repository.sh

metadata="$(python3 Scripts/release.py metadata)"
version="$(jq -r .version <<<"$metadata")"
asset="$(jq -r .asset <<<"$metadata")"
checksum="$(jq -r .checksum <<<"$metadata")"

repository_json="$(gh api "repos/$repository")"
if [[ "$(jq -r .visibility <<<"$repository_json")" != "private" ]]; then
  echo "error: private readiness requires $repository to remain private" >&2
  exit 1
fi
if [[ "$(jq -r .default_branch <<<"$repository_json")" != "main" ]]; then
  echo "error: default branch must be main" >&2
  exit 1
fi

variables="$(gh variable list --repo "$repository" --json name,value)"
variable_value() {
  jq -r --arg name "$1" '.[] | select(.name == $name) | .value' <<<"$variables"
}
if [[ "$(variable_value RELEASE_AUTOMATION_ENABLED)" != "true" ]]; then
  echo "error: RELEASE_AUTOMATION_ENABLED must be true" >&2
  exit 1
fi
if [[ "$(variable_value PUBLIC_DISTRIBUTION_ENABLED)" != "false" ||
      "$(variable_value COCOAPODS_PUBLISH_ENABLED)" != "false" ]]; then
  echo "error: public and CocoaPods publication gates must be false" >&2
  exit 1
fi

gh api "repos/$repository/immutable-releases" \
  --jq 'select(.enabled == true)' >/dev/null

release="$(gh release view "$version" \
  --repo "$repository" \
  --json isDraft,isImmutable,assets)"
jq -e \
  --arg asset "$asset" \
  --arg digest "sha256:$checksum" '
    .isDraft == false
    and .isImmutable == true
    and (.assets | length) == 1
    and .assets[0].name == $asset
    and .assets[0].digest == $digest
  ' <<<"$release" >/dev/null

readiness_dir="$(mktemp -d)"
trap 'rm -rf -- "$readiness_dir"' EXIT
state_output="$readiness_dir/release-state"
GITHUB_OUTPUT="$state_output" Scripts/inspect_remote_state.sh \
  "$(git rev-parse HEAD)" \
  "false" \
  "false"
if [[ "$(sed -n 's/^outcome=//p' "$state_output")" != "complete" ||
      "$(sed -n 's/^release_state=//p' "$state_output")" != "published" ||
      "$(sed -n 's/^visibility=//p' "$state_output")" != "private" ]]; then
  echo "error: private release reconciliation is not complete" >&2
  exit 1
fi
tag_state="$(sed -n 's/^tag_state=//p' "$state_output")"
if [[ "$tag_state" != "target" && "$tag_state" != "release" ]]; then
  echo "error: release tag does not match the release surface" >&2
  exit 1
fi

private_asset="$readiness_dir/$asset"
gh release download "$version" \
  --repo "$repository" \
  --pattern "$asset" \
  --dir "$readiness_dir"
python3 Scripts/release.py validate-archive --archive "$private_asset"
gh release verify-asset "$version" "$private_asset" --repo "$repository"

anonymous_status="$(
  curl --location --silent --show-error \
    --output /dev/null \
    --write-out '%{http_code}' \
    "https://github.com/$repository/releases/download/$version/$asset"
)"
if [[ "$anonymous_status" == "200" ]]; then
  echo "error: private Release asset is unexpectedly downloadable anonymously" >&2
  exit 1
fi

gh repo clone "$repository" "$readiness_dir/repository.git" \
  -- --mirror --quiet
pack_bytes="$(
  git -C "$readiness_dir/repository.git" count-objects -v \
    | awk -F': ' '$1 == "size-pack" { print $2 * 1024 }'
)"
if [[ -z "$pack_bytes" || "$pack_bytes" -gt "$maximum_pack_bytes" ]]; then
  echo "error: full Git pack is ${pack_bytes:-unknown} bytes; limit is $maximum_pack_bytes" >&2
  exit 1
fi

legacy_json="$(gh api "repos/$legacy_repository")"
if [[ "$(jq -r .visibility <<<"$legacy_json")" != "public" ||
      "$(jq -r .archived <<<"$legacy_json")" != "false" ]]; then
  echo "error: the legacy repository must remain public and unarchived" >&2
  exit 1
fi
gh api "repos/$legacy_repository/git/ref/tags/$version" >/dev/null

Scripts/verify_local_integration.sh "$private_asset"
pod spec lint UXCam.podspec --allow-warnings --fail-fast

echo "Private readiness verified"
echo "Version: $version"
echo "Full Git pack: $pack_bytes bytes"
echo "Anonymous asset HTTP status: $anonymous_status"
echo "Publication gates remain disabled"
