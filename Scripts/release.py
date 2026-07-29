#!/usr/bin/env python3
"""Validate, prepare, and classify UXCam distribution releases."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = ROOT / "release-metadata.json"
PACKAGE_PATH = ROOT / "Package.swift"
PODSPEC_PATH = ROOT / "UXCam.podspec"
VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
CHECKSUM_RE = re.compile(r"^[0-9a-f]{64}$")
ASSET_NAME = "UXCam.xcframework.zip"
REPOSITORY = "uxcam/uxcam-ios"
RELEASE_URL_TEMPLATE = (
    "https://github.com/uxcam/uxcam-ios/releases/download/{version}/"
    + ASSET_NAME
)


class ReleaseError(RuntimeError):
    """A release invariant was violated."""


def load_metadata(path: Path = METADATA_PATH) -> dict[str, Any]:
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseError(f"Cannot read {path}: {error}") from error

    required = {
        "asset",
        "checksum",
        "cocoapods",
        "repository",
        "validation",
        "version",
    }
    missing = required.difference(metadata)
    if missing:
        raise ReleaseError(f"Metadata is missing: {', '.join(sorted(missing))}")

    version = metadata["version"]
    checksum = metadata["checksum"]
    cocoapods = metadata["cocoapods"]
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        raise ReleaseError(f"Version must be an x.y.z release, got {version!r}")
    if not isinstance(checksum, str) or not CHECKSUM_RE.fullmatch(checksum):
        raise ReleaseError("Checksum must be a lowercase SHA-256 value")
    if metadata["asset"] != ASSET_NAME:
        raise ReleaseError(f"Release asset must be named {ASSET_NAME}")
    if metadata["repository"] != REPOSITORY:
        raise ReleaseError(f"Repository must be {REPOSITORY}")
    if not isinstance(cocoapods, dict):
        raise ReleaseError("cocoapods metadata must be an object")
    if not isinstance(cocoapods.get("publish"), bool):
        raise ReleaseError("cocoapods.publish must be true or false")
    source = cocoapods.get("source")
    if not isinstance(source, str) or not source.startswith("https://"):
        raise ReleaseError("cocoapods.source must be an HTTPS URL")
    if cocoapods["publish"] and source != RELEASE_URL_TEMPLATE.format(version=version):
        raise ReleaseError(
            "A publishable CocoaPods release must use the canonical GitHub Release URL"
        )
    validation = metadata["validation"]
    if not isinstance(validation, dict) or not isinstance(
        validation.get("requireCodeSignature"), bool
    ):
        raise ReleaseError("validation.requireCodeSignature must be true or false")
    return metadata


def _single_match(pattern: str, content: str, name: str) -> str:
    matches = re.findall(pattern, content, flags=re.MULTILINE)
    if len(matches) != 1:
        raise ReleaseError(f"Expected exactly one {name}; found {len(matches)}")
    return matches[0]


def _validate_manifest_contents(
    metadata: dict[str, Any], package: str, podspec: str
) -> None:
    package_version = _single_match(
        r'^let version = "([^"]+)"$', package, "Package.swift version"
    )
    package_checksum = _single_match(
        r'^let checksum = "([^"]+)"$', package, "Package.swift checksum"
    )
    pod_version = _single_match(
        r"^\s*s\.version\s*=\s*'([^']+)'$", podspec, "podspec version"
    )
    pod_source = _single_match(
        r'^\s*s\.source\s*=\s*\{\s*:http\s*=>\s*"([^"]+)"\s*\}$',
        podspec,
        "podspec source",
    )
    resolved_pod_source = pod_source.replace("#{s.version}", pod_version)

    expected = {
        "Package.swift version": (package_version, metadata["version"]),
        "Package.swift checksum": (package_checksum, metadata["checksum"]),
        "podspec version": (pod_version, metadata["version"]),
        "podspec source": (resolved_pod_source, metadata["cocoapods"]["source"]),
    }
    failures = [
        f"{name}: got {actual!r}, expected {wanted!r}"
        for name, (actual, wanted) in expected.items()
        if actual != wanted
    ]
    canonical_package_url = (
        'url: "https://github.com/uxcam/uxcam-ios/releases/download/'
        r'\(version)/UXCam.xcframework.zip"'
    )
    if canonical_package_url not in package:
        failures.append("Package.swift does not use the canonical Release asset URL")
    if failures:
        raise ReleaseError("Manifest drift detected:\n- " + "\n- ".join(failures))


def validate_manifests(metadata: dict[str, Any]) -> None:
    package = PACKAGE_PATH.read_text(encoding="utf-8")
    podspec = PODSPEC_PATH.read_text(encoding="utf-8")
    _validate_manifest_contents(metadata, package, podspec)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_zip_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if not members:
        raise ReleaseError("Archive is empty")
    if len(members) > 10_000:
        raise ReleaseError("Archive contains an unreasonable number of files")

    seen: set[str] = set()
    total_size = 0
    allowed_roots = {"UXCam.xcframework", "LICENSE"}
    for member in members:
        path = PurePosixPath(member.filename)
        if member.filename in seen:
            raise ReleaseError(f"Archive contains duplicate path: {member.filename}")
        seen.add(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ReleaseError(f"Unsafe archive path: {member.filename}")
        if not path.parts or path.parts[0] not in allowed_roots:
            raise ReleaseError(f"Unexpected top-level archive entry: {member.filename}")
        mode = member.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ReleaseError(f"Archive must not contain symlinks: {member.filename}")
        total_size += member.file_size
    if total_size > 1024 * 1024 * 1024:
        raise ReleaseError("Archive expands beyond the 1 GiB safety limit")
    return members


def validate_archive(path: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    if path.name != metadata["asset"]:
        raise ReleaseError(
            f"Archive basename must be {metadata['asset']}, got {path.name}"
        )
    if not path.is_file():
        raise ReleaseError(f"Archive does not exist: {path}")

    actual_checksum = sha256(path)
    if actual_checksum != metadata["checksum"]:
        raise ReleaseError(
            f"Checksum mismatch: got {actual_checksum}, expected {metadata['checksum']}"
        )

    try:
        with zipfile.ZipFile(path) as archive:
            members = _safe_zip_members(archive)
            member_names = {member.filename.rstrip("/") for member in members}
            xcframework_plist = "UXCam.xcframework/Info.plist"
            if xcframework_plist not in member_names:
                raise ReleaseError(f"Archive is missing {xcframework_plist}")
            container = plistlib.loads(archive.read(xcframework_plist))
            libraries = container.get("AvailableLibraries")
            if not isinstance(libraries, list) or not libraries:
                raise ReleaseError("XCFramework has no AvailableLibraries")

            saw_device = False
            saw_simulator = False
            framework_versions: set[str] = set()
            identifiers: list[str] = []
            for library in libraries:
                identifier = library.get("LibraryIdentifier")
                library_path = library.get("LibraryPath")
                platform = library.get("SupportedPlatform")
                variant = library.get("SupportedPlatformVariant")
                if not isinstance(identifier, str) or not isinstance(library_path, str):
                    raise ReleaseError("XCFramework library entry is incomplete")
                identifiers.append(identifier)
                if platform == "ios" and variant == "simulator":
                    saw_simulator = True
                if platform == "ios" and variant is None:
                    saw_device = True

                framework_plist = (
                    f"UXCam.xcframework/{identifier}/{library_path}/Info.plist"
                )
                if framework_plist not in member_names:
                    raise ReleaseError(f"Archive is missing {framework_plist}")
                plist = plistlib.loads(archive.read(framework_plist))
                framework_versions.add(str(plist.get("CFBundleShortVersionString", "")))

            if not saw_device or not saw_simulator:
                raise ReleaseError(
                    "XCFramework must contain iOS device and simulator libraries"
                )
            if framework_versions != {metadata["version"]}:
                raise ReleaseError(
                    "Framework versions do not match metadata: "
                    + ", ".join(sorted(framework_versions))
                )
    except (OSError, zipfile.BadZipFile, plistlib.InvalidFileException) as error:
        raise ReleaseError(f"Invalid XCFramework archive: {error}") from error

    return {
        "asset": path.name,
        "checksum": actual_checksum,
        "libraries": identifiers,
        "version": metadata["version"],
    }


def prepare_release(
    archive: Path,
    version: str,
    pod_source: Optional[str],
    pod_publish: bool,
    require_code_signature: bool,
) -> dict[str, Any]:
    if not VERSION_RE.fullmatch(version):
        raise ReleaseError(f"Version must be an x.y.z release, got {version!r}")
    if archive.name != ASSET_NAME:
        raise ReleaseError(f"Archive basename must be {ASSET_NAME}")
    if not archive.is_file():
        raise ReleaseError(f"Archive does not exist: {archive}")

    checksum = sha256(archive)
    canonical_source = RELEASE_URL_TEMPLATE.format(version=version)
    source = pod_source or canonical_source
    if pod_publish and source != canonical_source:
        raise ReleaseError("Published CocoaPods versions must use the canonical URL")

    metadata = {
        "asset": ASSET_NAME,
        "checksum": checksum,
        "cocoapods": {"publish": pod_publish, "source": source},
        "repository": REPOSITORY,
        "validation": {"requireCodeSignature": require_code_signature},
        "version": version,
    }
    validate_archive(archive, metadata)

    package = PACKAGE_PATH.read_text(encoding="utf-8")
    package, package_version_count = re.subn(
        r'^let version = "[^"]+"$', f'let version = "{version}"', package, count=1,
        flags=re.MULTILINE,
    )
    package, package_checksum_count = re.subn(
        r'^let checksum = "[^"]+"$',
        f'let checksum = "{checksum}"',
        package,
        count=1,
        flags=re.MULTILINE,
    )
    podspec = PODSPEC_PATH.read_text(encoding="utf-8")
    podspec, pod_version_count = re.subn(
        r"^(\s*s\.version\s*=\s*)'[^']+'$",
        rf"\g<1>'{version}'",
        podspec,
        count=1,
        flags=re.MULTILINE,
    )
    podspec, pod_source_count = re.subn(
        r'^(\s*s\.source\s*=\s*\{\s*:http\s*=>\s*)"[^"]+"(\s*\})$',
        rf'\g<1>"{source}"\g<2>',
        podspec,
        count=1,
        flags=re.MULTILINE,
    )
    substitutions = {
        "Package.swift version": package_version_count,
        "Package.swift checksum": package_checksum_count,
        "podspec version": pod_version_count,
        "podspec source": pod_source_count,
    }
    invalid_substitutions = [
        name for name, count in substitutions.items() if count != 1
    ]
    if invalid_substitutions:
        raise ReleaseError(
            "Could not prepare exactly one "
            + ", ".join(sorted(invalid_substitutions))
        )

    metadata_content = json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    _validate_manifest_contents(metadata, package, podspec)
    _atomic_write(PACKAGE_PATH, package)
    _atomic_write(PODSPEC_PATH, podspec)
    _atomic_write(METADATA_PATH, metadata_content)
    return metadata


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        stream.write(content)
        temporary_path = Path(stream.name)
    os.chmod(temporary_path, mode)
    os.replace(temporary_path, path)


def classify_state(
    *,
    release_publish_enabled: bool,
    pod_publish_enabled: bool,
    release_state: str,
    tag_state: str,
    pod_state: str,
    pod_publish: bool,
) -> dict[str, Any]:
    if release_state not in {"missing", "draft", "published"}:
        raise ReleaseError(f"Unknown release state: {release_state}")
    if tag_state not in {"missing", "target", "release", "other"}:
        raise ReleaseError(f"Unknown tag state: {tag_state}")
    if pod_state not in {"missing", "published"}:
        raise ReleaseError(f"Unknown CocoaPods state: {pod_state}")
    if release_state == "missing":
        raise ReleaseError("Release is missing; create its draft and exact asset first")
    if release_state == "published" and tag_state not in {"target", "release"}:
        raise ReleaseError(
            "Published release tag does not point at the expected release surface"
        )
    if release_state == "draft" and tag_state == "other":
        raise ReleaseError("Existing release tag points at a different commit")

    if release_state == "draft" and not release_publish_enabled:
        return {
            "outcome": "validate-only",
            "publish_pod": False,
            "publish_release": False,
        }

    publish_release = release_state == "draft" and release_publish_enabled
    publish_pod = (
        pod_publish
        and pod_state == "missing"
        and pod_publish_enabled
        and (release_state == "published" or publish_release)
    )
    if publish_release and publish_pod:
        outcome = "publish-release-and-pod"
    elif publish_release:
        outcome = "publish-release"
    elif publish_pod:
        outcome = "publish-pod"
    elif pod_publish and pod_state == "missing":
        outcome = "awaiting-cocoapods"
    else:
        outcome = "complete"
    return {
        "outcome": outcome,
        "publish_pod": publish_pod,
        "publish_release": publish_release,
    }


def _boolean(value: str) -> bool:
    normalized = value.lower()
    if normalized not in {"true", "false"}:
        raise argparse.ArgumentTypeError("expected true or false")
    return normalized == "true"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("metadata")
    subparsers.add_parser("validate-manifests")

    archive_parser = subparsers.add_parser("validate-archive")
    archive_parser.add_argument("--archive", type=Path, required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--archive", type=Path, required=True)
    prepare_parser.add_argument("--version", required=True)
    prepare_parser.add_argument("--pod-source")
    prepare_parser.add_argument("--publish-pod", action="store_true")
    prepare_parser.add_argument("--require-code-signature", action="store_true")

    classify_parser = subparsers.add_parser("classify")
    classify_parser.add_argument(
        "--release-publish-enabled", type=_boolean, required=True
    )
    classify_parser.add_argument("--pod-publish-enabled", type=_boolean, required=True)
    classify_parser.add_argument(
        "--release-state", choices=["missing", "draft", "published"], required=True
    )
    classify_parser.add_argument(
        "--tag-state", choices=["missing", "target", "release", "other"], required=True
    )
    classify_parser.add_argument(
        "--pod-state", choices=["missing", "published"], required=True
    )
    classify_parser.add_argument("--pod-publish", type=_boolean, required=True)
    return parser


def main() -> int:
    parser = build_parser()
    arguments = parser.parse_args()
    try:
        metadata = load_metadata()
        if arguments.command == "metadata":
            result: Any = metadata
        elif arguments.command == "validate-manifests":
            validate_manifests(metadata)
            result = {"status": "valid", "version": metadata["version"]}
        elif arguments.command == "validate-archive":
            validate_manifests(metadata)
            result = validate_archive(arguments.archive.resolve(), metadata)
        elif arguments.command == "prepare":
            result = prepare_release(
                arguments.archive.resolve(),
                arguments.version,
                arguments.pod_source,
                arguments.publish_pod,
                arguments.require_code_signature,
            )
        elif arguments.command == "classify":
            result = classify_state(
                release_publish_enabled=arguments.release_publish_enabled,
                pod_publish_enabled=arguments.pod_publish_enabled,
                release_state=arguments.release_state,
                tag_state=arguments.tag_state,
                pod_state=arguments.pod_state,
                pod_publish=arguments.pod_publish,
            )
        else:
            parser.error("unsupported command")
            return 2
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ReleaseError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
