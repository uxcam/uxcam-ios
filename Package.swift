// swift-tools-version:5.3
import PackageDescription

let version = "0.0.1"
let checksum = "4764880d860e61e521acff9761550fba9b8ae8dfeab6a1b3b2adc08e92a477af"

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
