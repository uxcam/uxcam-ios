# Release runbook

This repository is the distribution index. It contains manifests and release
automation, not the SDK archive.

## Safety gates

Three repository variables control automation and external publication:

| Variable | Initial value | Private staging value | Public production value |
|---|---:|---:|---:|
| `RELEASE_AUTOMATION_ENABLED` | `false` | `true` | `true` |
| `PUBLIC_DISTRIBUTION_ENABLED` | `false` | `false` | `true` |
| `COCOAPODS_PUBLISH_ENABLED` | `false` | `false` | `true` |

`COCOAPODS_PUBLISH_ENABLED=true` is rejected while the repository is private.
The CocoaPods token and Slack webhook must be configured before public launch.
The automation gate stays off only for the initial push, before the bootstrap
draft exists; it is also the emergency stop for future releases.

Harden-Runner and SARIF upload are conditionally enabled after the repository
is public. Their free tiers do not support private repositories, so private
staging uses pinned actions, least-privilege job permissions, and local zizmor
validation without pretending that those two services are active.

The workflow has these recoverable states:

| GitHub Release | CocoaPods | Result |
|---|---|---|
| Draft, publication disabled | Any | Validate only; keep draft |
| Draft, publication enabled | Missing | Validate, publish Release, publish pod |
| Draft, pod already exists | Published | Validate and publish only the Release |
| Published at expected commit | Missing | Retry CocoaPods only |
| Published at expected commit | Published | Successful no-op |
| Missing release/asset or wrong tag | Any | Fail without mutation |

## Prepare a normal release

1. Build and sign `UXCam.xcframework`.
2. Create the archive with the exact name `UXCam.xcframework.zip`.
3. Start from a clean `main` checkout of this repository.
4. Run:

   ```bash
   ./publish_draft.sh VERSION /absolute/path/UXCam.xcframework.zip
   ```

   The script validates the archive, calculates its checksum, updates all
   manifests, refuses to overwrite an existing release, and uploads one asset
   to a draft release.

   Add `--require-code-signature` to `publish_draft.sh` when signature
   validation is required for a future artifact. The unchanged 3.9.0 bootstrap
   records `false` because its device slice is unsigned and its simulator
   signature does not verify.

5. Open a PR containing `release-metadata.json`, `Package.swift`, and
   `UXCam.podspec`.
6. Merge after validation succeeds. With production gates enabled, the main
   workflow publishes the draft at the merge commit and pushes CocoaPods.

Never delete a published release, move a published version tag, replace an
asset, or reuse a version. Fix forward with a patch version.

## Private bootstrap

Version 3.9.0 already exists on CocoaPods and its published podspec references
the legacy repository. Therefore its metadata sets `cocoapods.publish=false`
and preserves the original podspec URL. The workflow skips CocoaPods lint for
this bootstrap-only Release; the same archive and podspec have already passed
CocoaPods lint locally and are already live on trunk. New publishable versions
must pass both the local pre-publication lint and public post-publication lint.

To publish only the private GitHub Release after validation, manually dispatch
`Validate and publish SDK release` with
`publish_private_github_release=true`. This creates the version tag without
attempting CocoaPods publication. The release remains accessible only to
authorized GitHub users while the repository is private.

## Recovery

The main workflow is idempotent. After fixing an external failure, dispatch it
again:

- If the Release is already published but CocoaPods is missing, only lint and
  CocoaPods publication run.
- If both are published, the workflow validates the archive and exits as a
  successful no-op.
- If `main` advanced after publication, the immutable tag remains valid only
  when the release metadata committed at that tag exactly matches current
  release metadata.
- If a tag points to different release metadata, stop and investigate.
  Automation will not move it.

## Public launch checklist

1. Confirm the private 3.9.0 release, tag, checksum, simulator build, and device
   build.
2. Configure `COCOAPODS_TRUNK_TOKEN` and `SLACK_WEBHOOK_URL`.
3. Make the repository public.
4. Confirm the Release asset is anonymously downloadable.
5. Run a clean, unauthenticated SPM resolution and `pod spec lint`.
6. Set `PUBLIC_DISTRIBUTION_ENABLED=true`.
7. Set `COCOAPODS_PUBLISH_ENABLED=true`.
8. Update customer documentation and the legacy repository notice.

The gates are changed only after the anonymous download test passes.
