#!/bin/bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 EXPECTED_SHA RELEASE_PUBLISH_ENABLED POD_PUBLISH_ENABLED" >&2
  exit 2
fi

expected_sha="$1"
release_publish_enabled="$2"
pod_publish_enabled="$3"
output="${GITHUB_OUTPUT:-/dev/stdout}"
metadata="$(python3 Scripts/release.py metadata)"
version="$(jq -r .version <<<"$metadata")"
asset="$(jq -r .asset <<<"$metadata")"
repository="$(jq -r .repository <<<"$metadata")"
pod_publish="$(jq -r .cocoapods.publish <<<"$metadata")"

visibility="$(gh api "repos/$repository" --jq .visibility)"
if [[ "$pod_publish_enabled" == "true" && "$visibility" != "public" ]]; then
  echo "error: CocoaPods publication cannot be enabled while the repository is $visibility" >&2
  exit 1
fi

if release_json="$(gh release view "$version" \
    --repo "$repository" \
    --json tagName,isDraft,assets,targetCommitish,url 2>/dev/null)"; then
  if [[ "$(jq -r .isDraft <<<"$release_json")" == "true" ]]; then
    release_state="draft"
  else
    release_state="published"
  fi
  matching_assets="$(jq --arg asset "$asset" \
    '[.assets[] | select(.name == $asset)] | length' <<<"$release_json")"
  total_assets="$(jq '.assets | length' <<<"$release_json")"
  if [[ "$matching_assets" -ne 1 || "$total_assets" -ne 1 ]]; then
    echo "error: release $version must contain exactly one asset named $asset" >&2
    exit 1
  fi
  release_url="$(jq -r .url <<<"$release_json")"
else
  release_state="missing"
  release_url=""
fi

tag_state="missing"
if tag_json="$(gh api "repos/$repository/git/ref/tags/$version" 2>/dev/null)"; then
  object_type="$(jq -r .object.type <<<"$tag_json")"
  object_sha="$(jq -r .object.sha <<<"$tag_json")"
  for _ in 1 2 3 4 5; do
    if [[ "$object_type" != "tag" ]]; then
      break
    fi
    tag_json="$(gh api "repos/$repository/git/tags/$object_sha")"
    object_type="$(jq -r .object.type <<<"$tag_json")"
    object_sha="$(jq -r .object.sha <<<"$tag_json")"
  done
  if [[ "$object_type" != "commit" ]]; then
    echo "error: tag $version does not resolve to a commit" >&2
    exit 1
  fi
  if [[ "$object_sha" == "$expected_sha" ]]; then
    tag_state="target"
  elif [[ "$release_state" == "published" ]]; then
    tag_matches_release=true
    release_files=(
      "Package.swift"
      "UXCam.podspec"
      "UXCamWrapper/EmptyFile.swift"
      "release-metadata.json"
    )
    for release_file in "${release_files[@]}"; do
      committed_file="$(
        gh api "repos/$repository/contents/$release_file?ref=$object_sha" \
          --jq .content \
          | python3 -c 'import base64, sys; print(base64.b64decode(sys.stdin.read()).decode())'
      )"
      current_file="$(<"$release_file")"
      if [[ "$current_file" != "$committed_file" ]]; then
        tag_matches_release=false
        break
      fi
    done
    if [[ "$tag_matches_release" == "true" ]]; then
      tag_state="release"
    else
      tag_state="other"
    fi
  else
    tag_state="other"
  fi
fi

pod_response="$(mktemp)"
trap 'rm -f "$pod_response"' EXIT
if ! curl -fsSL --retry 3 --retry-all-errors \
    "https://trunk.cocoapods.org/api/v1/pods/UXCam" >"$pod_response"; then
  echo "error: could not determine CocoaPods trunk state" >&2
  exit 1
fi
if jq -e --arg version "$version" \
    'any(.versions[]?; .name == $version)' "$pod_response" >/dev/null; then
  pod_state="published"
else
  pod_state="missing"
fi

classification="$(python3 Scripts/release.py classify \
  --release-publish-enabled "$release_publish_enabled" \
  --pod-publish-enabled "$pod_publish_enabled" \
  --release-state "$release_state" \
  --tag-state "$tag_state" \
  --pod-state "$pod_state" \
  --pod-publish "$pod_publish")"

{
  echo "asset=$asset"
  echo "outcome=$(jq -r .outcome <<<"$classification")"
  echo "pod_state=$pod_state"
  echo "pod_publish=$pod_publish"
  echo "publish_pod=$(jq -r .publish_pod <<<"$classification")"
  echo "publish_release=$(jq -r .publish_release <<<"$classification")"
  echo "release_state=$release_state"
  echo "release_url=$release_url"
  echo "repository=$repository"
  echo "tag_state=$tag_state"
  echo "version=$version"
  echo "visibility=$visibility"
} >>"$output"

echo "Release state: $(jq -c . <<<"$classification")"
