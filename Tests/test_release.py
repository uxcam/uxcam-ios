import unittest

from Scripts.release import ReleaseError, classify_state, load_metadata, validate_manifests


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

    def test_private_published_release_is_validation_only(self):
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
        with self.assertRaisesRegex(ReleaseError, "does not point"):
            self.classify(release="published", tag="missing")

    def test_tag_at_wrong_commit_fails(self):
        with self.assertRaisesRegex(ReleaseError, "different commit"):
            self.classify(release="draft", tag="other")


class RepositoryManifestTests(unittest.TestCase):
    def test_repository_manifests_are_synchronized(self):
        metadata = load_metadata()
        validate_manifests(metadata)


if __name__ == "__main__":
    unittest.main()
