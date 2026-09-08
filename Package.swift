// swift-tools-version:5.3
import PackageDescription

let version = "3.11.0"
let checksum = "cf3bb3758e23038b809ed29bbe59f3a987f41460aa22cbfa709e71728b54213b"

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
