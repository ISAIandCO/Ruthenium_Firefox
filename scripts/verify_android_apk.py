#!/usr/bin/env python3
"""Fail closed when an Android ABI split does not contain a usable Gecko engine."""

from __future__ import annotations

import argparse
import struct
import zipfile
from pathlib import Path


REQUIRED_GECKO_LIBRARIES = (
    "libxul.so",
    "libmozglue.so",
    "libnss3.so",
    "libfreebl3.so",
    "libsoftokn3.so",
)
MINIMUM_XUL_SIZE = 32 * 1024 * 1024
ABI_ELF_IDENTITIES = {
    "armeabi-v7a": (1, 40, "ELF32/ARM"),
    "arm64-v8a": (2, 183, "ELF64/AArch64"),
    "x86": (1, 3, "ELF32/x86"),
    "x86_64": (2, 62, "ELF64/x86-64"),
}


class ApkValidationError(ValueError):
    """The APK cannot run Gecko on the requested ABI."""


def _read_elf_identity(header: bytes) -> tuple[int, int]:
    if len(header) < 20 or header[:4] != b"\x7fELF":
        raise ApkValidationError("libxul.so does not have an ELF header")
    elf_class = header[4]
    byte_order = header[5]
    if byte_order != 1:
        raise ApkValidationError("libxul.so is not little-endian ELF")
    machine = struct.unpack_from("<H", header, 18)[0]
    return elf_class, machine


def validate_apk(
    apk_path: Path,
    abi: str,
    *,
    minimum_xul_size: int = MINIMUM_XUL_SIZE,
) -> dict[str, int | str]:
    if abi not in ABI_ELF_IDENTITIES:
        raise ApkValidationError(f"unsupported ABI: {abi}")
    if not apk_path.is_file():
        raise ApkValidationError(f"APK does not exist: {apk_path}")

    with zipfile.ZipFile(apk_path) as archive:
        names = set(archive.namelist())
        native_abis = {
            parts[1]
            for name in names
            if name.startswith("lib/") and name.endswith(".so")
            if len(parts := name.split("/")) == 3
        }
        if native_abis != {abi}:
            found = ", ".join(sorted(native_abis)) or "none"
            raise ApkValidationError(
                f"expected only native ABI {abi}, found: {found}"
            )

        missing = [
            library
            for library in REQUIRED_GECKO_LIBRARIES
            if f"lib/{abi}/{library}" not in names
        ]
        if missing:
            raise ApkValidationError(
                "missing required Gecko libraries: " + ", ".join(missing)
            )

        xul_name = f"lib/{abi}/libxul.so"
        xul_info = archive.getinfo(xul_name)
        if xul_info.file_size < minimum_xul_size:
            raise ApkValidationError(
                f"{xul_name} is unexpectedly small: {xul_info.file_size} bytes"
            )
        with archive.open(xul_info) as xul:
            elf_class, machine = _read_elf_identity(xul.read(20))

        expected_class, expected_machine, identity_name = ABI_ELF_IDENTITIES[abi]
        if (elf_class, machine) != (expected_class, expected_machine):
            raise ApkValidationError(
                f"{xul_name} has ELF class/machine {elf_class}/{machine}; "
                f"expected {identity_name}"
            )

        native_library_count = sum(
            name.startswith(f"lib/{abi}/") and name.endswith(".so")
            for name in names
        )

    return {
        "abi": abi,
        "elf": identity_name,
        "native_library_count": native_library_count,
        "xul_size": xul_info.file_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", required=True, type=Path)
    parser.add_argument("--abi", required=True, choices=sorted(ABI_ELF_IDENTITIES))
    args = parser.parse_args()
    try:
        result = validate_apk(args.apk, args.abi)
    except (ApkValidationError, OSError, zipfile.BadZipFile) as error:
        parser.exit(1, f"error: {error}\n")
    print(
        "verified {abi}: {elf}, {native_library_count} native libraries, "
        "libxul.so={xul_size} bytes".format(**result)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
