// swift-tools-version:5.3
import PackageDescription

let version = "3.10.0"
let checksum = "492517f73765d2ba2ef59712a3310bb8824a6cc503b9af19050a14c2b1902dca"

let package = Package(
    name: "UXCam",
    platforms: [
        .iOS(.v12)
    ],
    products: [
        .library(
            name: "UXCam",
            targets: ["UXCamWrapper", "UXCam"]
        )
    ],
    targets: [
        // The wrapper carries linker settings that SwiftPM binary targets cannot declare.
        .target(
            name: "UXCamWrapper",
            path: "UXCamWrapper",
            exclude: ["README.md"],
            linkerSettings: [
                .linkedFramework("AVFoundation"),
                .linkedFramework("CoreGraphics"),
                .linkedFramework("CoreMedia"),
                .linkedFramework("CoreVideo"),
                .linkedFramework("CoreTelephony"),
                .linkedFramework("MobileCoreServices"),
                .linkedFramework("QuartzCore"),
                .linkedFramework("Security"),
                .linkedFramework("SystemConfiguration"),
                .linkedFramework("WebKit"),
                .linkedLibrary("z"),
                .linkedLibrary("iconv"),
                .linkedLibrary("c++")
            ]
        ),
        .binaryTarget(
            name: "UXCam",
            url: "https://github.com/uxcam/uxcam-ios/releases/download/\(version)/UXCam.xcframework.zip",
            checksum: checksum
        )
    ]
)
