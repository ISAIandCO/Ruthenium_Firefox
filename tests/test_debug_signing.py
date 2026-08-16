from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = REPOSITORY_ROOT / "signing/debug-key-lock.json"
KEYSTORE_PATH = REPOSITORY_ROOT / "signing/rfirefox-debug.keystore"


class PublicDebugKeyTest(unittest.TestCase):
    def test_lock_file_is_canonical_and_describes_the_public_key(self) -> None:
        raw = LOCK_PATH.read_bytes()
        lock = json.loads(raw)
        canonical = (json.dumps(lock, indent=2, sort_keys=True) + "\n").encode()
        self.assertEqual(raw, canonical)
        self.assertEqual(lock["alias"], "androiddebugkey")
        self.assertEqual(lock["store_password"], "android")
        self.assertEqual(lock["key_password"], "android")

    @unittest.skipUnless(shutil.which("keytool"), "keytool is not installed")
    def test_committed_keystore_certificate_matches_the_lock(self) -> None:
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        certificate = subprocess.run(
            [
                "keytool",
                "-exportcert",
                "-keystore",
                str(KEYSTORE_PATH),
                "-storepass",
                lock["store_password"],
                "-alias",
                lock["alias"],
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
        self.assertEqual(
            hashlib.sha256(certificate).hexdigest(),
            lock["certificate_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
