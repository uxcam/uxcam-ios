import plistlib
import tempfile
import unittest
import zipfile
from pathlib import Path

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
        with self.assertRaisesRegex(ReleaseError, "release metadata"):
            self.classify(release="published", tag="missing")

    def test_published_immutable_tag_with_matching_metadata_is_valid(self):
        result = self.classify(release="published", tag="release")
        self.assertEqual(result["outcome"], "complete")

    def test_tag_at_wrong_commit_fails(self):
        with self.assertRaisesRegex(ReleaseError, "different commit"):
            self.classify(release="draft", tag="other")


class RepositoryManifestTests(unittest.TestCase):
    def test_repository_manifests_are_synchronized(self):
        metadata = load_metadata()
        validate_manifests(metadata)


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


if __name__ == "__main__":
    unittest.main()
