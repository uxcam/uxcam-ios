#!/bin/bash
set -euo pipefail

readonly repository="uxcam/uxcam-ios"
readonly maximum_pack_bytes=$((5 * 1024 * 1024))

for command in curl gh git jq pod python3 swift xcodebuild; do
  if ! command -v "$command" >/dev/null; then
    echo "error: required command is missing: $command" >&2
    exit 1
  fi
done

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
metadata="$(python3 Scripts/release.py metadata)"
version="$(jq -r .version <<<"$metadata")"
asset="$(jq -r .asset <<<"$metadata")"
checksum="$(jq -r .checksum <<<"$metadata")"

visibility="$(gh api "repos/$repository" --jq .visibility)"
if [[ "$visibility" != "public" ]]; then
  echo "error: public readiness cannot pass while $repository is $visibility" >&2
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
  echo "error: public and CocoaPods publication gates must remain false during readiness checks" >&2
  exit 1
fi

secret_names="$(gh secret list --repo "$repository" --json name --jq '.[].name')"
for secret_name in COCOAPODS_TRUNK_TOKEN SLACK_WEBHOOK_URL; do
  if ! grep -Fxq "$secret_name" <<<"$secret_names"; then
    echo "error: required repository secret is missing: $secret_name" >&2
    exit 1
  fi
done

gh api "repos/$repository/immutable-releases" --jq 'select(.enabled == true)' >/dev/null
gh api "repos/$repository/branches/main/protection" >/dev/null
for workflow in .github/workflows/*.yml; do
  if ! grep -q 'step-security/harden-runner@' "$workflow"; then
    echo "error: Harden-Runner is not restored in $workflow" >&2
    exit 1
  fi
done

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
public_asset="$readiness_dir/$asset"
curl --fail --location --retry 3 --retry-all-errors \
  "https://github.com/$repository/releases/download/$version/$asset" \
  --output "$public_asset"
python3 Scripts/release.py validate-archive --archive "$public_asset"
gh release verify-asset "$version" "$public_asset" --repo "$repository"

git -c credential.helper= -c http.extraHeader= clone \
  --mirror \
  "https://github.com/$repository.git" \
  "$readiness_dir/repository.git" >/dev/null
pack_bytes="$(
  git -C "$readiness_dir/repository.git" count-objects -v \
    | awk -F': ' '$1 == "size-pack" { print $2 * 1024 }'
)"
if [[ -z "$pack_bytes" || "$pack_bytes" -gt "$maximum_pack_bytes" ]]; then
  echo "error: full Git pack is ${pack_bytes:-unknown} bytes; limit is $maximum_pack_bytes" >&2
  exit 1
fi

consumer="$readiness_dir/PublicUXCamConsumer"
mkdir -p "$consumer/Sources/PublicUXCamConsumer"
python3 - "$consumer" "$version" <<'PY'
from pathlib import Path
import sys

consumer = Path(sys.argv[1])
version = sys.argv[2]
(consumer / "Package.swift").write_text(
    f"""// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "PublicUXCamConsumer",
    platforms: [.iOS(.v12)],
    dependencies: [
        .package(url: "https://github.com/uxcam/uxcam-ios", exact: "{version}")
    ],
    targets: [
        .executableTarget(
            name: "PublicUXCamConsumer",
            dependencies: [.product(name: "UXCam", package: "uxcam-ios")]
        )
    ]
)
""",
    encoding="utf-8",
)
(consumer / "Sources/PublicUXCamConsumer/main.swift").write_text(
    'import UXCam\nprint("UXCam public package resolved")\n',
    encoding="utf-8",
)
PY

swift package \
  --package-path "$consumer" \
  --disable-netrc \
  --disable-keychain \
  resolve

(
  cd "$consumer"
  xcodebuild \
    -scheme PublicUXCamConsumer \
    -destination 'generic/platform=iOS Simulator' \
    -derivedDataPath "$readiness_dir/DerivedData-simulator" \
    CODE_SIGNING_ALLOWED=NO \
    build
  xcodebuild \
    -scheme PublicUXCamConsumer \
    -destination 'generic/platform=iOS' \
    -derivedDataPath "$readiness_dir/DerivedData-device" \
    CODE_SIGNING_ALLOWED=NO \
    build
)

pod spec lint UXCam.podspec --allow-warnings --fail-fast

echo "Public readiness verified"
echo "Version: $version"
echo "Full Git pack: $pack_bytes bytes"
echo "Publication gates remain disabled"
