from __future__ import annotations

import unittest

from scripts.parse_apksigner_output import parse_signer_certificate_sha256


EXPECTED_DIGEST = (
    "d7a19050129bbb6e7af6f29dc899a123757ca226ea0ee3c7395c43527592035f"
)


class ApksignerOutputTest(unittest.TestCase):
    def test_parses_current_build_tools_scheme_prefix(self) -> None:
        output = f"""Verifies
Number of signers: 1
V2 Signer: certificate DN: CN=Android Debug, O=RFirefox, C=RU
V2 Signer: certificate SHA-256 digest: {EXPECTED_DIGEST}
V2 Signer: public key SHA-256 digest: {'c' * 64}
"""
        self.assertEqual(parse_signer_certificate_sha256(output), EXPECTED_DIGEST)

    def test_parses_legacy_numbered_signer_prefix_and_normalizes_digest(self) -> None:
        colon_digest = ":".join(
            EXPECTED_DIGEST[index : index + 2].upper()
            for index in range(0, len(EXPECTED_DIGEST), 2)
        )
        output = f"Signer #1 certificate SHA-256 digest: {colon_digest}\n"
        self.assertEqual(parse_signer_certificate_sha256(output), EXPECTED_DIGEST)

    def test_accepts_same_certificate_reported_for_multiple_schemes(self) -> None:
        output = "\n".join(
            (
                f"V2 Signer: certificate SHA-256 digest: {EXPECTED_DIGEST}",
                f"V3.1 Signer: certificate SHA-256 digest: {EXPECTED_DIGEST}",
            )
        )
        self.assertEqual(parse_signer_certificate_sha256(output), EXPECTED_DIGEST)

    def test_rejects_missing_or_multiple_certificate_digests(self) -> None:
        with self.assertRaisesRegex(ValueError, "did not report"):
            parse_signer_certificate_sha256(
                f"V2 Signer: public key SHA-256 digest: {EXPECTED_DIGEST}\n"
            )

        with self.assertRaisesRegex(ValueError, "multiple"):
            parse_signer_certificate_sha256(
                "\n".join(
                    (
                        f"V2 Signer: certificate SHA-256 digest: {EXPECTED_DIGEST}",
                        f"V3 Signer: certificate SHA-256 digest: {'a' * 64}",
                    )
                )
            )


if __name__ == "__main__":
    unittest.main()
