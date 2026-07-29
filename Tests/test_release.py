import itertools
import json
import plistlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import Scripts.release as release_module
from Scripts.release import (
    ASSET_NAME,
    REPOSITORY,
    ReleaseError,
    classify_state,
    load_metadata,
    sha256,
    validate_archive,
    validate_manifests,
)


class ReleaseStateTests(unittest.TestCase):
    def classify(
        self,
        *,
        release_enabled=True,
        pod_enabled=True,
        release="published",
        tag="target",
        pod="published",
        pod_publish=True,
    ):
        return classify_state(
            release_publish_enabled=release_enabled,
            pod_publish_enabled=pod_enabled,
            release_state=release,
            tag_state=tag,
            pod_state=pod,
            pod_publish=pod_publish,
        )

    def test_private_draft_is_validation_only(self):
        result = self.classify(
            release_enabled=False,
            pod_enabled=False,
            release="draft",
            tag="missing",
            pod="missing",
        )
        self.assertEqual(result["outcome"], "validate-only")
        self.assertFalse(result["publish_release"])
        self.assertFalse(result["publish_pod"])

    def test_private_published_release_waits_for_cocoapods(self):
        result = self.classify(
            release_enabled=False, pod_enabled=False, pod="missing"
        )
        self.assertEqual(result["outcome"], "awaiting-cocoapods")

    def test_public_draft_publishes_release_and_missing_pod(self):
        result = self.classify(release="draft", tag="missing", pod="missing")
        self.assertEqual(result["outcome"], "publish-release-and-pod")
        self.assertTrue(result["publish_release"])
        self.assertTrue(result["publish_pod"])

    def test_bootstrap_publishes_release_but_not_existing_pod(self):
        result = self.classify(
            release_enabled=True,
            pod_enabled=False,
            release="draft",
            tag="missing",
            pod="published",
            pod_publish=False,
        )
        self.assertEqual(result["outcome"], "publish-release")
        self.assertTrue(result["publish_release"])
        self.assertFalse(result["publish_pod"])

    def test_retry_publishes_only_missing_pod(self):
        result = self.classify(release="published", pod="missing")
        self.assertEqual(result["outcome"], "publish-pod")
        self.assertFalse(result["publish_release"])
        self.assertTrue(result["publish_pod"])

    def test_complete_release_is_noop(self):
        result = self.classify()
        self.assertEqual(result["outcome"], "complete")
        self.assertFalse(result["publish_release"])
        self.assertFalse(result["publish_pod"])

    def test_non_publishable_pod_is_complete_when_release_exists(self):
        result = self.classify(pod="missing", pod_publish=False)
        self.assertEqual(result["outcome"], "complete")

    def test_private_release_can_publish_without_publishing_new_pod(self):
        result = self.classify(
            release_enabled=True,
            pod_enabled=False,
            release="draft",
            tag="missing",
            pod="missing",
        )
        self.assertEqual(result["outcome"], "publish-release")
        self.assertTrue(result["publish_release"])
        self.assertFalse(result["publish_pod"])

    def test_published_release_waits_for_cocoapods_gate(self):
        result = self.classify(pod_enabled=False, pod="missing")
        self.assertEqual(result["outcome"], "awaiting-cocoapods")

    def test_missing_release_fails(self):
        with self.assertRaisesRegex(ReleaseError, "Release is missing"):
            self.classify(release="missing", tag="missing", pod="missing")

    def test_published_release_without_tag_fails(self):
        with self.assertRaisesRegex(ReleaseError, "release surface"):
            self.classify(release="published", tag="missing")

    def test_published_immutable_tag_with_matching_release_surface_is_valid(self):
        result = self.classify(release="published", tag="release")
        self.assertEqual(result["outcome"], "complete")

    def test_tag_at_wrong_commit_fails(self):
        with self.assertRaisesRegex(ReleaseError, "different commit"):
            self.classify(release="draft", tag="other")

    def test_every_state_combination_preserves_publication_invariants(self):
        combinations = itertools.product(
            (False, True),
            (False, True),
            ("missing", "draft", "published"),
            ("missing", "target", "release", "other"),
            ("missing", "published"),
            (False, True),
        )
        for (
            release_enabled,
            pod_enabled,
            release_state,
            tag_state,
            pod_state,
            pod_publish,
        ) in combinations:
            context = (
                release_enabled,
                pod_enabled,
                release_state,
                tag_state,
                pod_state,
                pod_publish,
            )
            try:
                result = classify_state(
                    release_publish_enabled=release_enabled,
                    pod_publish_enabled=pod_enabled,
                    release_state=release_state,
                    tag_state=tag_state,
                    pod_state=pod_state,
                    pod_publish=pod_publish,
                )
            except ReleaseError:
                continue

            with self.subTest(context=context):
                if result["publish_release"]:
                    self.assertTrue(release_enabled)
                    self.assertEqual(release_state, "draft")
                if result["publish_pod"]:
                    self.assertTrue(pod_enabled)
                    self.assertTrue(pod_publish)
                    self.assertEqual(pod_state, "missing")
                    self.assertTrue(
                        release_state == "published"
                        or result["publish_release"]
                    )
                if release_state == "draft" and not release_enabled:
                    self.assertFalse(result["publish_release"])
                    self.assertFalse(result["publish_pod"])
                if release_state == "published":
                    self.assertFalse(result["publish_release"])


class RepositoryManifestTests(unittest.TestCase):
    def test_repository_manifests_are_synchronized(self):
        metadata = load_metadata()
        validate_manifests(metadata)


class RepositoryWorkflowTests(unittest.TestCase):
    def test_public_asset_keeps_canonical_basename(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/release.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('$RUNNER_TEMP/public/$ASSET', workflow)
        self.assertNotIn('$RUNNER_TEMP/public-$ASSET', workflow)

    def test_cocoapods_requires_both_publication_gates(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/release.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "vars.PUBLIC_DISTRIBUTION_ENABLED == 'true' && "
            "vars.COCOAPODS_PUBLISH_ENABLED == 'true'",
            workflow,
        )

    def test_publishable_release_builds_spm_consumers(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/release.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'Scripts/verify_local_integration.sh '
            '"$RUNNER_TEMP/release/$ASSET"',
            workflow,
        )
        self.assertIn(
            "- name: Verify SPM consumer builds\n"
            "        if: steps.state.outputs.pod_publish == 'true'",
            workflow,
        )


class ArchiveValidationTests(unittest.TestCase):
    def create_archive(
        self,
        root: Path,
        *,
        include_device=True,
        include_simulator=True,
        framework_version="3.9.0",
        unsafe_path=False,
    ) -> Path:
        archive_path = root / ASSET_NAME
        libraries = []
        if include_device:
            libraries.append(
                {
                    "LibraryIdentifier": "ios-arm64",
                    "LibraryPath": "UXCam.framework",
                    "SupportedArchitectures": ["arm64"],
                    "SupportedPlatform": "ios",
                }
            )
        if include_simulator:
            libraries.append(
                {
                    "LibraryIdentifier": "ios-arm64_x86_64-simulator",
                    "LibraryPath": "UXCam.framework",
                    "SupportedArchitectures": ["arm64", "x86_64"],
                    "SupportedPlatform": "ios",
                    "SupportedPlatformVariant": "simulator",
                }
            )

        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr(
                "UXCam.xcframework/Info.plist",
                plistlib.dumps({"AvailableLibraries": libraries}),
            )
            for library in libraries:
                archive.writestr(
                    "UXCam.xcframework/"
                    + library["LibraryIdentifier"]
                    + "/UXCam.framework/Info.plist",
                    plistlib.dumps(
                        {"CFBundleShortVersionString": framework_version}
                    ),
                )
            if unsafe_path:
                archive.writestr("../outside.txt", "unsafe")
        return archive_path

    def metadata(self, archive: Path):
        return {
            "asset": ASSET_NAME,
            "checksum": sha256(archive),
            "cocoapods": {
                "publish": False,
                "source": "https://example.invalid/UXCam.xcframework.zip",
            },
            "repository": REPOSITORY,
            "validation": {"requireCodeSignature": False},
            "version": "3.9.0",
        }

    def test_valid_device_and_simulator_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = self.create_archive(Path(directory))
            result = validate_archive(archive, self.metadata(archive))
            self.assertEqual(result["version"], "3.9.0")
            self.assertEqual(len(result["libraries"]), 2)

    def test_checksum_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = self.create_archive(Path(directory))
            metadata = self.metadata(archive)
            metadata["checksum"] = "0" * 64
            with self.assertRaisesRegex(ReleaseError, "Checksum mismatch"):
                validate_archive(archive, metadata)

    def test_noncanonical_archive_basename_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = self.create_archive(Path(directory))
            renamed = archive.with_name("public-UXCam.xcframework.zip")
            archive.rename(renamed)
            metadata = self.metadata(renamed)
            metadata["asset"] = ASSET_NAME
            with self.assertRaisesRegex(ReleaseError, "Archive basename"):
                validate_archive(renamed, metadata)

    def test_path_traversal_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = self.create_archive(Path(directory), unsafe_path=True)
            with self.assertRaisesRegex(ReleaseError, "Unsafe archive path"):
                validate_archive(archive, self.metadata(archive))

    def test_missing_simulator_slice_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = self.create_archive(Path(directory), include_simulator=False)
            with self.assertRaisesRegex(ReleaseError, "device and simulator"):
                validate_archive(archive, self.metadata(archive))

    def test_framework_version_drift_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = self.create_archive(Path(directory), framework_version="3.9.1")
            with self.assertRaisesRegex(ReleaseError, "versions do not match"):
                validate_archive(archive, self.metadata(archive))

    def test_prepare_failure_does_not_modify_manifests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.create_archive(root, framework_version="3.9.1")
            package_path = root / "Package.swift"
            podspec_path = root / "UXCam.podspec"
            metadata_path = root / "release-metadata.json"
            package_content = """// swift-tools-version:5.3
let version = "3.8.0"
let checksum = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
url: "https://github.com/uxcam/uxcam-ios/releases/download/\\(version)/UXCam.xcframework.zip"
"""
            podspec_content = """Pod::Spec.new do |s|
  s.version = '3.8.0'
  s.source = { :http => "https://example.invalid/old.zip" }
end
"""
            package_path.write_text(package_content, encoding="utf-8")
            podspec_path.write_text(podspec_content, encoding="utf-8")
            metadata_path.write_text("unchanged\n", encoding="utf-8")

            with (
                patch.object(release_module, "PACKAGE_PATH", package_path),
                patch.object(release_module, "PODSPEC_PATH", podspec_path),
                patch.object(release_module, "METADATA_PATH", metadata_path),
            ):
                with self.assertRaisesRegex(ReleaseError, "versions do not match"):
                    release_module.prepare_release(
                        archive,
                        "3.9.0",
                        None,
                        True,
                        False,
                    )

            self.assertEqual(package_path.read_text(encoding="utf-8"), package_content)
            self.assertEqual(podspec_path.read_text(encoding="utf-8"), podspec_content)
            self.assertEqual(metadata_path.read_text(encoding="utf-8"), "unchanged\n")

    def test_prepare_success_updates_all_manifests_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.create_archive(root, framework_version="3.9.1")
            package_path = root / "Package.swift"
            podspec_path = root / "UXCam.podspec"
            metadata_path = root / "release-metadata.json"
            package_path.write_text(
                """// swift-tools-version:5.3
let version = "3.8.0"
let checksum = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
url: "https://github.com/uxcam/uxcam-ios/releases/download/\\(version)/UXCam.xcframework.zip"
""",
                encoding="utf-8",
            )
            podspec_path.write_text(
                """Pod::Spec.new do |s|
  s.version = '3.8.0'
  s.source = { :http => "https://example.invalid/old.zip" }
end
""",
                encoding="utf-8",
            )
            metadata_path.write_text("{}\n", encoding="utf-8")
            package_path.chmod(0o644)
            podspec_path.chmod(0o644)
            metadata_path.chmod(0o644)

            with (
                patch.object(release_module, "PACKAGE_PATH", package_path),
                patch.object(release_module, "PODSPEC_PATH", podspec_path),
                patch.object(release_module, "METADATA_PATH", metadata_path),
            ):
                result = release_module.prepare_release(
                    archive,
                    "3.9.1",
                    None,
                    True,
                    True,
                )

            expected_url = (
                "https://github.com/uxcam/uxcam-ios/releases/download/"
                "3.9.1/UXCam.xcframework.zip"
            )
            self.assertEqual(result["version"], "3.9.1")
            self.assertTrue(result["cocoapods"]["publish"])
            self.assertTrue(result["validation"]["requireCodeSignature"])
            self.assertIn(
                'let version = "3.9.1"',
                package_path.read_text(encoding="utf-8"),
            )
            self.assertIn(expected_url, podspec_path.read_text(encoding="utf-8"))
            self.assertEqual(
                json.loads(metadata_path.read_text(encoding="utf-8")),
                result,
            )
            self.assertEqual(package_path.stat().st_mode & 0o777, 0o644)
            self.assertEqual(podspec_path.stat().st_mode & 0o777, 0o644)
            self.assertEqual(metadata_path.stat().st_mode & 0o777, 0o644)


if __name__ == "__main__":
    unittest.main()
