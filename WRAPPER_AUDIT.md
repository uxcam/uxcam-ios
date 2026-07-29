# Wrapper and documentation reference audit

Audit date: 2026-07-29

The following maintained local projects reference the legacy SPM repository or
its raw binary URL:

| Project | Reference type | Migration action |
|---|---|---|
| `Android/uxcam-kmp` | `Package.swift`, Xcode project, generated project YAML, Gradle raw artifact download | Change the SPM package identity to `uxcam-ios`; change direct binary downloads to the new Release URL |
| `Ionic/cordova-uxcam` | `Package.swift` | Change URL and package identity to `uxcam-ios` |
| `Other/integration-mcp` | iOS documentation and generated snippets | Replace customer-facing SPM URL and package identity |
| `Ionic/analytics-app` | Application `Package.resolved` | Re-resolve after migration; this is a consumer, not a released wrapper |

These references intentionally remain unchanged while `uxcam-ios` is private:
ordinary SwiftPM binary targets cannot download a private GitHub Release asset.
Update each maintained source in its next release only after the anonymous
public package verification passes.

CocoaPods-only Flutter and React Native integrations do not need a package URL
change. CocoaPods continues under the existing `UXCam` pod name.
