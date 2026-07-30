# Migrating an existing Swift Package Manager integration

The package product and imported module remain named `UXCam`. Application code
does not change, but the Git package identity changes from `uxcam-ios-sdk` to
`uxcam-ios`.

Migrate once a release (3.9.1 or later) is available in this repository;
until then, the existing `uxcam-ios-sdk` dependency continues to work.

## Xcode projects

1. Note every application target currently linked to the `UXCam` product.
2. Remove the `uxcam-ios-sdk` package dependency.
3. Add `https://github.com/uxcam/uxcam-ios`.
4. Select the required UXCam version.
5. Link the `UXCam` product to the same application targets.
6. Resolve package dependencies and commit the updated project and
   `Package.resolved`.
7. Build both a simulator and device destination.

## Package.swift consumers

Replace the dependency URL:

```swift
.package(
    url: "https://github.com/uxcam/uxcam-ios",
    from: "3.9.1" // the first version distributed from this repository
)
```

Then run `swift package resolve` and commit the updated `Package.resolved`.

## Compatibility

- The old URL remains available permanently for version 3.9.0 and earlier.
- Versions after 3.9.0 are released from `uxcam-ios`.
- Never include both package URLs in one dependency graph. They have different
  package identities but export the same `UXCam` product and module.
- CocoaPods users do not need to make any migration change.
