#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /path/to/UXCam.xcframework.zip" >&2
  exit 2
fi

for command in ditto python3 swift xcodebuild; do
  if ! command -v "$command" >/dev/null; then
    echo "error: required command is missing: $command" >&2
    exit 1
  fi
done

archive="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
python3 Scripts/release.py validate-archive --archive "$archive"

integration_dir="$(mktemp -d)"
trap 'rm -rf "$integration_dir"' EXIT
distribution="$integration_dir/distribution"
consumer="$integration_dir/consumer"
mkdir -p "$distribution/UXCamWrapper" "$consumer/Sources/LocalUXCamConsumer"
cp Package.swift "$distribution/Package.swift"
cp UXCamWrapper/EmptyFile.swift "$distribution/UXCamWrapper/EmptyFile.swift"
cp UXCamWrapper/README.md "$distribution/UXCamWrapper/README.md"
ditto -x -k "$archive" "$distribution"

python3 - "$distribution/Package.swift" "$consumer" <<'PY'
from pathlib import Path
import re
import sys

distribution_manifest = Path(sys.argv[1])
consumer = Path(sys.argv[2])
manifest = distribution_manifest.read_text(encoding="utf-8")
manifest, count = re.subn(
    r"""        \.binaryTarget\(
            name: "UXCam",
            url: "[^"]+",
            checksum: checksum
        \)""",
    """        .binaryTarget(
            name: "UXCam",
            path: "UXCam.xcframework"
        )""",
    manifest,
    count=1,
)
if count != 1:
    raise SystemExit("could not substitute the local binary target")
distribution_manifest.write_text(manifest, encoding="utf-8")

(consumer / "Package.swift").write_text(
    """// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "LocalUXCamConsumer",
    platforms: [.iOS(.v12)],
    dependencies: [.package(path: "../distribution")],
    targets: [
        .executableTarget(
            name: "LocalUXCamConsumer",
            dependencies: [.product(name: "UXCam", package: "distribution")]
        )
    ]
)
""",
    encoding="utf-8",
)
(consumer / "Sources/LocalUXCamConsumer/main.swift").write_text(
    'import UXCam\nprint("UXCam local integration built")\n',
    encoding="utf-8",
)
PY

swift package --package-path "$consumer" resolve
(
  cd "$consumer"
  xcodebuild \
    -quiet \
    -scheme LocalUXCamConsumer \
    -destination 'generic/platform=iOS Simulator' \
    -derivedDataPath "$integration_dir/DerivedData-simulator" \
    CODE_SIGNING_ALLOWED=NO \
    build
  xcodebuild \
    -quiet \
    -scheme LocalUXCamConsumer \
    -destination 'generic/platform=iOS' \
    -derivedDataPath "$integration_dir/DerivedData-device" \
    CODE_SIGNING_ALLOWED=NO \
    build
)

echo "Local SPM integration passed for simulator and device"
