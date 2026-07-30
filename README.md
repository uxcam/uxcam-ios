# UXCam SDK for iOS

Official distribution of the [UXCam](https://uxcam.com) iOS SDK for Swift
Package Manager and CocoaPods. The SDK binary ships as a GitHub Release
asset, so this repository stays small and fast to clone.

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

### CocoaPods

Add the pod to your Podfile:

```ruby
pod 'UXCam'
```

Then run `pod install`. The pod name and application integration are
unchanged.

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
