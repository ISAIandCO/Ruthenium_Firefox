#!/usr/bin/env python3
"""Extract one signing-certificate SHA-256 digest from apksigner output."""

from __future__ import annotations

import re
import sys


SIGNER_CERTIFICATE_SHA256 = re.compile(
    r"^(?:Signer #\d+|V\d+(?:\.\d+)? Signer):? "
    r"certificate SHA-256 digest: ([0-9A-Fa-f:]+)\s*$"
)


def parse_signer_certificate_sha256(output: str) -> str:
    """Return the sole certificate digest used by all reported APK signers."""

    digests: set[str] = set()
    for line in output.splitlines():
        match = SIGNER_CERTIFICATE_SHA256.fullmatch(line.strip())
        if not match:
            continue
        digest = match.group(1).replace(":", "").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"invalid signer certificate SHA-256 digest: {digest}")
        digests.add(digest)

    if not digests:
        raise ValueError("apksigner did not report a signer certificate SHA-256 digest")
    if len(digests) != 1:
        raise ValueError(
            "apksigner reported multiple signer certificate SHA-256 digests: "
            + ", ".join(sorted(digests))
        )
    return next(iter(digests))


def main() -> int:
    try:
        print(parse_signer_certificate_sha256(sys.stdin.read()))
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
