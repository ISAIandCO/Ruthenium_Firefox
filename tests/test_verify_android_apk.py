from __future__ import annotations

import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.verify_android_apk import (
    ABI_ELF_IDENTITIES,
    REQUIRED_GECKO_LIBRARIES,
    ApkValidationError,
    validate_apk,
)


def elf_header(elf_class: int, machine: int) -> bytes:
    header = bytearray(20)
    header[:4] = b"\x7fELF"
    header[4] = elf_class
    header[5] = 1
    struct.pack_into("<H", header, 18, machine)
    return bytes(header)


class AndroidApkValidationTest(unittest.TestCase):
    def write_apk(
        self,
        path: Path,
        abi: str,
        *,
        machine: int | None = None,
        extra_abi: str | None = None,
        omit: str | None = None,
    ) -> None:
        elf_class, expected_machine, _ = ABI_ELF_IDENTITIES[abi]
        with zipfile.ZipFile(path, "w") as archive:
            for library in REQUIRED_GECKO_LIBRARIES:
                if library == omit:
                    continue
                content = (
                    elf_header(elf_class, machine or expected_machine)
                    if library == "libxul.so"
                    else b"native"
                )
                archive.writestr(f"lib/{abi}/{library}", content)
            if extra_abi:
                archive.writestr(f"lib/{extra_abi}/libextra.so", b"native")

    def test_accepts_matching_complete_gecko_split(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / "app.apk"
            self.write_apk(apk, "arm64-v8a")
            result = validate_apk(apk, "arm64-v8a", minimum_xul_size=0)
            self.assertEqual(result["elf"], "ELF64/AArch64")

    def test_rejects_missing_gecko_library(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / "app.apk"
            self.write_apk(apk, "armeabi-v7a", omit="libxul.so")
            with self.assertRaisesRegex(ApkValidationError, "libxul.so"):
                validate_apk(apk, "armeabi-v7a", minimum_xul_size=0)

    def test_rejects_wrong_elf_machine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / "app.apk"
            self.write_apk(apk, "arm64-v8a", machine=62)
            with self.assertRaisesRegex(ApkValidationError, "expected ELF64/AArch64"):
                validate_apk(apk, "arm64-v8a", minimum_xul_size=0)

    def test_rejects_multiple_native_abis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / "app.apk"
            self.write_apk(apk, "x86_64", extra_abi="arm64-v8a")
            with self.assertRaisesRegex(ApkValidationError, "expected only native ABI"):
                validate_apk(apk, "x86_64", minimum_xul_size=0)


if __name__ == "__main__":
    unittest.main()
