# UXCam SDK for iOS

Official distribution of the [UXCam](https://uxcam.com) iOS SDK for Swift
Package Manager. The SDK binary ships as a GitHub Release asset
(`UXCam.xcframework.zip`), so this repository stays small and fast to clone.
The same asset can be embedded directly as an XCFramework.

## Requirements

- iOS 12.0 or later
- Xcode 13 or newer for Swift Package Manager

## Installation

### Swift Package Manager

In Xcode, select **File → Add Package Dependencies…** and enter:

```text
https://github.com/uxcam/uxcam-ios
```

Choose a version-based dependency rule and add the `UXCam` product to your
application targets. Step-by-step screenshots are in
[SwiftPM-README.md](SwiftPM-README.md).

Or declare the dependency in `Package.swift`:

```swift
.package(url: "https://github.com/uxcam/uxcam-ios", from: "3.9.1")
```

Migrating from `uxcam-ios-sdk`? Follow [MIGRATION.md](MIGRATION.md), and never
include both package URLs in the same dependency graph — they expose the same
`UXCam` product and module.

### XCFramework

Download `UXCam.xcframework.zip` from the
[Releases](https://github.com/uxcam/uxcam-ios/releases) page, unzip it, and
drag `UXCam.xcframework` into your application target (**Do Not Embed**; it is
a static framework). Link `libz`, `libiconv` and `libc++`.

### CocoaPods

UXCam is no longer published to CocoaPods: the CocoaPods trunk stops
accepting new versions, so the last published pod receives no further
updates. Move to Swift Package Manager — see
[MIGRATION.md](MIGRATION.md#migrating-from-cocoapods).

## Quick start

Get the application key from the [UXCam dashboard](https://app.uxcam.com).

### Swift

```swift
import UXCam

UXCam.optIntoSchematicRecordings()
let configuration = UXCamConfiguration(appKey: "YourAppKey")
UXCam.start(with: configuration)
```

### Objective-C

```objective-c
#import <UXCam/UXCam.h>

[UXCam optIntoSchematicRecordings];
UXCamConfiguration *configuration =
    [[UXCamConfiguration alloc] initWithAppKey:@"YourAppKey"];
[UXCam startWithConfiguration:configuration];
```

See the [UXCam iOS documentation](https://developer.uxcam.com/docs/ios) for
configuration, privacy, and feature guidance.

## License

See [LICENSE](LICENSE).
