from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPOSITORY_ROOT / ".github/workflows/build-android.yml"
BOOTSTRAP_SCRIPT = REPOSITORY_ROOT / "scripts/run_bootstrap_with_heartbeat.sh"


class ReleaseWorkflowPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_full_build_is_not_triggered_by_repository_changes(self) -> None:
        trigger_section = self.workflow.split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch:", trigger_section)
        self.assertIn("schedule:", trigger_section)
        self.assertNotIn("push:", trigger_section)
        self.assertNotIn("pull_request:", trigger_section)

    def test_release_uses_committed_debug_key_and_debug_version_suffix(self) -> None:
        self.assertNotIn("-PdisableDebugSigning", self.workflow)
        self.assertNotIn('"$apksigner" sign', self.workflow)
        self.assertIn('"$apksigner" verify', self.workflow)
        self.assertIn("signing/rfirefox-debug.keystore", self.workflow)
        self.assertIn("d7a19050129bbb6e7af6f29dc899a123757ca226ea0ee3c7395c43527592035f", self.workflow)
        self.assertIn('release_tag="${FIREFOX_VERSION}_debug"', self.workflow)
        self.assertIn('--title "$RELEASE_TAG"', self.workflow)
        self.assertIn('gh release create "$RELEASE_TAG"', self.workflow)

    def test_existing_firefox_release_skips_the_expensive_build(self) -> None:
        self.assertIn("release_exists:", self.workflow)
        self.assertIn("needs.resolve.outputs.release_exists != 'true'", self.workflow)

    def test_bootstrap_has_live_diagnostics_without_an_extra_timeout(self) -> None:
        bootstrap_script = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")

        self.assertNotIn("timeout-minutes: 100", self.workflow)
        self.assertNotIn("RFIREFOX_BOOTSTRAP_TIMEOUT", self.workflow)
        self.assertIn("run_bootstrap_with_heartbeat.sh", self.workflow)
        self.assertIn("Upload bootstrap diagnostics", self.workflow)
        self.assertIn("if: ${{ always() }}", self.workflow)
        self.assertNotIn("timeout --", bootstrap_script)
        self.assertIn("PYTHONUNBUFFERED=1 stdbuf", bootstrap_script)
        self.assertIn("Firefox bootstrap heartbeat", bootstrap_script)
        self.assertIn("bootstrap.log", bootstrap_script)
        self.assertIn("summary.txt", bootstrap_script)

    def test_bootstrap_creates_the_default_mozconfig_before_building(self) -> None:
        bootstrap_script = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            'echo "MOZCONFIG=$RUNNER_TEMP/firefox-source/mozconfig"', self.workflow
        )
        self.assertNotIn(
            'echo "MOZCONFIG=$RUNNER_TEMP/firefox-source/.mozconfig"', self.workflow
        )
        self.assertIn(
            "unset MOZCONFIG ANDROID_HOME ANDROID_SDK_ROOT", bootstrap_script
        )
        self.assertLess(
            bootstrap_script.index("unset MOZCONFIG"),
            bootstrap_script.index("./mach --no-interactive bootstrap"),
        )


if __name__ == "__main__":
    unittest.main()
