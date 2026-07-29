# UXCam SDK for iOS

This lightweight repository distributes the UXCam iOS SDK through Swift
Package Manager and CocoaPods. The SDK binary is stored in GitHub Releases;
binary archives are never committed to this Git repository.

> **Migration staging:** This repository is private while the new release path
> is being verified. Keep using
> [`uxcam/uxcam-ios-sdk`](https://github.com/uxcam/uxcam-ios-sdk) until UXCam
> announces that this repository is public.

## Swift Package Manager

After the public launch, add this package URL in Xcode:

```text
https://github.com/uxcam/uxcam-ios
```

Select the `UXCam` product and a version-based dependency rule. Do not add both
`uxcam-ios` and `uxcam-ios-sdk` to the same dependency graph because both
packages expose the same product and module.

Existing SPM users should follow [MIGRATION.md](MIGRATION.md).

## CocoaPods

Add the existing pod to the application Podfile:

```ruby
pod 'UXCam'
```

Then run `pod install` or `pod update UXCam`. CocoaPods support is continuing;
the pod name and application integration do not change.

## Integration

Get the application key from the UXCam dashboard.

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
configuration and privacy guidance.

## Maintainers

See [RELEASING.md](RELEASING.md) for the release state machine, private staging
gates, recovery procedures, and public launch checklist.
