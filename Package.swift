// swift-tools-version:5.3
import PackageDescription

let version = "3.10.2"
let checksum = "a879bdd7c82ac0b64e2d1258f7cb5bf42ce53809cbcf5dca21b275f349c02896"

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
