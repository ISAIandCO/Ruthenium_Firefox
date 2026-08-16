from __future__ import annotations

import unittest

from scripts.resolve_firefox_source import select_stable, version_to_android_tag


class FirefoxSourceResolverTest(unittest.TestCase):
    def test_android_release_tag(self) -> None:
        self.assertEqual(
            version_to_android_tag("153.0.4"),
            "FIREFOX-ANDROID_153_0_4_RELEASE",
        )

    def test_beta_and_nightly_versions_are_rejected(self) -> None:
        for version in ("154.0b10", "156.0a1", "153esr", "latest"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                version_to_android_tag(version)

    def test_selection_requires_exact_mobile_release_tag(self) -> None:
        revision = "a" * 40
        selection = select_stable(
            {"LATEST_FIREFOX_VERSION": "153.0.4"},
            {
                "tags": [
                    {"tag": "FIREFOX_153_0_4_RELEASE", "node": "b" * 40},
                    {
                        "tag": "FIREFOX-ANDROID_153_0_4_RELEASE",
                        "node": revision,
                    },
                ]
            },
        )
        self.assertEqual(selection.version, "153.0.4")
        self.assertEqual(selection.revision, revision)
        self.assertIn(revision, selection.archive_url)

    def test_duplicate_or_missing_tags_fail_closed(self) -> None:
        details = {"LATEST_FIREFOX_VERSION": "153.0.4"}
        with self.assertRaises(ValueError):
            select_stable(details, {"tags": []})
        duplicate = {
            "tag": "FIREFOX-ANDROID_153_0_4_RELEASE",
            "node": "c" * 40,
        }
        with self.assertRaises(ValueError):
            select_stable(details, {"tags": [duplicate, duplicate]})


if __name__ == "__main__":
    unittest.main()
