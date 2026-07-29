# Using Swift Package Manager

UXCam supports Swift Package Manager on Xcode 13 or newer.

## Add the package in Xcode

1. Select **File → Add Package Dependencies**.
2. After UXCam announces the public migration, enter
   `https://github.com/uxcam/uxcam-ios`.
3. Select a version-based dependency rule.
4. Add the `UXCam` product to the required application targets.

![Add package dependency](docs/resources/SPM-add-package.png)

![Select version rule](docs/resources/SPM-select-branch.png)

![Select application targets](docs/resources/SPM-select-targets.png)

During private migration testing, GitHub authentication and SwiftPM binary
artifact credentials are required. Customer applications should keep using
`https://github.com/uxcam/uxcam-ios-sdk` until the new repository is public.

See [MIGRATION.md](MIGRATION.md) before changing an existing dependency.
