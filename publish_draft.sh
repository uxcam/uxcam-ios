#!/bin/bash
set -euo pipefail

readonly repository="uxcam/uxcam-ios"

usage() {
  echo "usage: $0 VERSION /path/to/UXCam.xcframework.zip [--require-code-signature]" >&2
}

if [[ $# -lt 2 || $# -gt 3 ]]; then
  usage
  exit 2
fi
if [[ $# -eq 3 && "$3" != "--require-code-signature" ]]; then
  usage
  exit 2
fi

version="$1"
archive="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
if [[ "$(basename "$archive")" != "UXCam.xcframework.zip" ]]; then
  echo "error: asset must be named UXCam.xcframework.zip" >&2
  exit 1
fi

for command in gh git python3 swift; do
  if ! command -v "$command" >/dev/null; then
    echo "error: required command is missing: $command" >&2
    exit 1
  fi
done

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$root"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "error: start from a clean uxcam-ios checkout" >&2
  exit 1
fi
if gh release view "$version" --repo "$repository" >/dev/null 2>&1; then
  echo "error: release $version already exists; assets are never overwritten" >&2
  exit 1
fi

prepare_arguments=(
  --archive "$archive"
  --version "$version"
  --publish-pod
)
if [[ "${3:-}" == "--require-code-signature" ]]; then
  prepare_arguments+=(--require-code-signature)
fi
python3 Scripts/release.py prepare \
  "${prepare_arguments[@]}"
swift package dump-package >/dev/null

target="$(git rev-parse HEAD)"
gh release create "$version" \
  --repo "$repository" \
  --draft \
  --target "$target" \
  --title "v$version" \
  --generate-notes \
  "$archive"

cat <<EOF
Draft $version created with a validated asset.

Next:
  1. Review release-metadata.json, Package.swift, and UXCam.podspec.
  2. Open a PR containing those three changes.
  3. Merge it. The release workflow will revalidate the exact draft asset.

The repository variable PUBLIC_DISTRIBUTION_ENABLED must remain false while
the repository is private.
EOF
