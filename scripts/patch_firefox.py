#!/usr/bin/env python3
"""Apply the Ruthenium scoped CA and Android product patches to Firefox."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import shutil
import urllib.request
from pathlib import Path
from typing import Callable


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CERTIFICATE_PATH = REPOSITORY_ROOT / "certificates/russian_trusted_root_ca.pem"
CERTIFICATE_LOCK_PATH = REPOSITORY_ROOT / "certificates/ministry-ca-lock.json"

CERT_VERIFIER_CPP = Path("security/certverifier/CertVerifier.cpp")
CERT_VERIFIER_H = Path("security/certverifier/CertVerifier.h")
TRUST_DOMAIN_CPP = Path("security/certverifier/NSSCertDBTrustDomain.cpp")
TRUST_DOMAIN_H = Path("security/certverifier/NSSCertDBTrustDomain.h")
GENERATED_HEADER = Path("security/certverifier/RutheniumRoot.h")
FENIX_GRADLE = Path("mobile/android/fenix/app/build.gradle")
FENIX_STRINGS = Path(
    "mobile/android/fenix/app/src/main/res/values/static_strings.xml"
)
FENIX_RELEASE_STRINGS = Path(
    "mobile/android/fenix/app/src/release/res/values/static_strings.xml"
)
FENIX_LAUNCHER_FOREGROUND = Path(
    "mobile/android/fenix/app/src/main/res/drawable/ic_launcher_foreground.xml"
)
FENIX_RELEASE_LAUNCHER_FOREGROUND = Path(
    "mobile/android/fenix/app/src/release/res/drawable/ic_launcher_foreground.xml"
)
FENIX_LAUNCHER_MONOCHROME = Path(
    "mobile/android/fenix/app/src/main/res/drawable/ic_launcher_monochrome.xml"
)

ICON_SOURCE_DIR = REPOSITORY_ROOT / "branding/android"
ICON_DENSITIES = ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi")
FENIX_LEGACY_ICONS = tuple(
    (
        ICON_SOURCE_DIR / f"rfirefox-{density}.webp",
        Path(
            f"mobile/android/fenix/app/src/release/res/mipmap-{density}/"
            "ic_launcher.webp"
        ),
    )
    for density in ICON_DENSITIES
) + tuple(
    (
        ICON_SOURCE_DIR / f"rfirefox-round-{density}.webp",
        Path(
            f"mobile/android/fenix/app/src/release/res/mipmap-{density}/"
            "ic_launcher_round.webp"
        ),
    )
    for density in ICON_DENSITIES
)

TEXT_TARGETS = (
    CERT_VERIFIER_CPP,
    CERT_VERIFIER_H,
    TRUST_DOMAIN_CPP,
    TRUST_DOMAIN_H,
    FENIX_GRADLE,
    FENIX_STRINGS,
    FENIX_RELEASE_STRINGS,
    FENIX_LAUNCHER_FOREGROUND,
    FENIX_RELEASE_LAUNCHER_FOREGROUND,
    FENIX_LAUNCHER_MONOCHROME,
)

BEGIN_MARKER = "// BEGIN Ruthenium scoped Russian CA"
END_MARKER = "// END Ruthenium scoped Russian CA"


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load_certificate_lock(path: Path = CERTIFICATE_LOCK_PATH) -> dict[str, str]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8", "strict"))
    if not isinstance(value, dict) or canonical_json(value) != raw:
        raise ValueError("certificate lock must be canonical JSON")
    if set(value) != {"der_sha256", "primary_url", "secondary_url"}:
        raise ValueError("certificate lock has unexpected fields")
    if not isinstance(value["der_sha256"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", value["der_sha256"]
    ):
        raise ValueError("certificate lock has an invalid SHA-256")
    for key in ("primary_url", "secondary_url"):
        if not isinstance(value[key], str) or not value[key].startswith("https://"):
            raise ValueError(f"certificate lock has an invalid {key}")
    return value  # type: ignore[return-value]


def decode_pem(pem: str) -> bytes:
    begin = "-----BEGIN CERTIFICATE-----"
    end = "-----END CERTIFICATE-----"
    if pem.count(begin) != 1 or pem.count(end) != 1:
        raise ValueError("expected exactly one PEM certificate")
    encoded = pem.split(begin, 1)[1].split(end, 1)[0]
    try:
        return base64.b64decode("".join(encoded.split()), validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("invalid PEM certificate") from error


def load_verified_certificate(
    certificate_path: Path = CERTIFICATE_PATH,
    lock_path: Path = CERTIFICATE_LOCK_PATH,
) -> bytes:
    der = decode_pem(certificate_path.read_text(encoding="ascii"))
    expected = load_certificate_lock(lock_path)["der_sha256"]
    actual = hashlib.sha256(der).hexdigest()
    if actual != expected:
        raise ValueError(f"unexpected certificate SHA-256: {actual}")
    return der


def encoded_name_constraints() -> bytes:
    """Return RFC 5280 constraints for .ru/.xn--p1ai/.su and no IP SANs."""

    def tlv(tag: int, content: bytes) -> bytes:
        if len(content) >= 128:
            raise ValueError("constraint element is unexpectedly large")
        return bytes((tag, len(content))) + content

    def subtree(general_name_tag: int, value: bytes) -> bytes:
        return tlv(0x30, tlv(general_name_tag, value))

    permitted = b"".join(
        subtree(0x82, suffix) for suffix in (b".ru", b".xn--p1ai", b".su")
    )
    # RFC 5280 encodes an IP constraint as address || mask. An all-zero mask
    # covers the entire address family, so excluding it rejects every IP SAN.
    excluded = subtree(0x87, b"\0" * 8) + subtree(0x87, b"\0" * 32)
    return tlv(0x30, tlv(0xA0, permitted) + tlv(0xA1, excluded))


def format_cpp_array(name: str, data: bytes) -> str:
    lines = []
    for offset in range(0, len(data), 12):
        chunk = data[offset : offset + 12]
        lines.append("    " + ", ".join(f"0x{byte:02x}" for byte in chunk) + ",")
    return f"inline constexpr uint8_t {name}[] = {{\n" + "\n".join(lines) + "\n};"


def generated_header(der: bytes) -> str:
    digest = hashlib.sha256(der).hexdigest()
    return f"""/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

#ifndef security_certverifier_RutheniumRoot_h
#define security_certverifier_RutheniumRoot_h

#include <stdint.h>

// Russian Trusted Root CA, DER SHA-256: {digest}
{format_cpp_array("kRutheniumRussianRootDER", der)}

// Permitted DNS subtrees: .ru, .xn--p1ai (.рф), .su.
// Excluded IP subtrees: all IPv4 and all IPv6 addresses.
{format_cpp_array("kRutheniumNameConstraintsDER", encoded_name_constraints())}

#endif  // security_certverifier_RutheniumRoot_h
"""


def replace_once(source: str, old: str, new: str, description: str) -> str:
    if new in source:
        return source
    count = source.count(old)
    if count != 1:
        raise ValueError(f"{description}: expected one anchor, found {count}")
    return source.replace(old, new, 1)


def patch_cert_verifier_h(source: str) -> str:
    old = """  nsTArray<mozilla::pkix::Input> mThirdPartyIntermediateInputs;

  // We only have a forward declarations of these classes (see above)"""
    new = f"""  nsTArray<mozilla::pkix::Input> mThirdPartyIntermediateInputs;

  {BEGIN_MARKER}
  // Only TLSServer verification receives this extra root. The additional
  // RFC 5280 constraints are supplied while the path is built.
  nsTArray<mozilla::pkix::Input> mTLSServerRootInputs;
  mozilla::pkix::Input mRutheniumRootInput;
  mozilla::pkix::Input mRutheniumNameConstraintsInput;
  bool mRutheniumScopedTrustInitialized = false;
  {END_MARKER}

  // We only have a forward declarations of these classes (see above)"""
    return replace_once(source, old, new, "CertVerifier members")


def patch_cert_verifier_cpp(source: str) -> str:
    source = replace_once(
        source,
        '#include "CertVerifier.h"\n',
        '#include "CertVerifier.h"\n\n#include "RutheniumRoot.h"\n',
        "Ruthenium header include",
    )

    destructor = "\nCertVerifier::~CertVerifier() = default;"
    position = source.find(destructor)
    if position == -1:
        raise ValueError("CertVerifier destructor anchor was not found")
    constructor_close = source.rfind("\n}", 0, position)
    if constructor_close == -1:
        raise ValueError("CertVerifier constructor end was not found")
    init_block = f"""

  {BEGIN_MARKER}
  mTLSServerRootInputs = mThirdPartyRootInputs.Clone();
  if (mRutheniumRootInput.Init(kRutheniumRussianRootDER,
                                sizeof(kRutheniumRussianRootDER)) == Success &&
      mRutheniumNameConstraintsInput.Init(
          kRutheniumNameConstraintsDER,
          sizeof(kRutheniumNameConstraintsDER)) == Success) {{
    mTLSServerRootInputs.AppendElement(mRutheniumRootInput);
    mRutheniumScopedTrustInitialized = true;
  }}
  {END_MARKER}"""
    if BEGIN_MARKER not in source[:position]:
        source = source[:constructor_close] + init_block + source[constructor_close:]

    start = source.find("    case VerifyUsage::TLSServer: {")
    end = source.find("    case VerifyUsage::EmailCA:", start)
    if start == -1 or end == -1:
        raise ValueError("TLSServer verification section was not found")
    section = source[start:end]
    if "mTLSServerRootInputs" not in section:
        count = section.count("originAttributes, mThirdPartyRootInputs,")
        if count != 2:
            raise ValueError(f"expected two TLSServer root arguments, found {count}")
        section = section.replace(
            "originAttributes, mThirdPartyRootInputs,",
            "originAttributes, mTLSServerRootInputs,",
        )

        old_tail = "mCTVerifier, builtChain, pinningTelemetryInfo, hostname);"
        count = section.count(old_tail)
        if count != 2:
            raise ValueError(f"expected two TLSServer constructor tails, found {count}")
        new_tail = """mCTVerifier, builtChain, pinningTelemetryInfo, hostname,
            mRutheniumScopedTrustInitialized ? &mRutheniumRootInput : nullptr,
            mRutheniumScopedTrustInitialized
                ? &mRutheniumNameConstraintsInput
                : nullptr);"""
        section = section.replace(old_tail, new_tail)
        source = source[:start] + section + source[end:]
    return source


def patch_trust_domain_h(source: str) -> str:
    old_signature = """      /*out*/ nsTArray<nsTArray<uint8_t>>& builtChain,
      /*optional*/ PinningTelemetryInfo* pinningTelemetryInfo = nullptr,
      /*optional*/ const char* hostname = nullptr);"""
    new_signature = """      /*out*/ nsTArray<nsTArray<uint8_t>>& builtChain,
      /*optional*/ PinningTelemetryInfo* pinningTelemetryInfo = nullptr,
      /*optional*/ const char* hostname = nullptr,
      /*optional*/ const mozilla::pkix::Input* constrainedRoot = nullptr,
      /*optional*/ const mozilla::pkix::Input* additionalNameConstraints =
          nullptr);"""
    source = replace_once(
        source, old_signature, new_signature, "TrustDomain constructor declaration"
    )

    old_members = """  const nsTArray<mozilla::pkix::Input>&
      mThirdPartyIntermediateInputs;                              // non-owning
  const Maybe<nsTArray<nsTArray<uint8_t>>>& mExtraCertificates;"""
    new_members = f"""  const nsTArray<mozilla::pkix::Input>&
      mThirdPartyIntermediateInputs;                              // non-owning
  {BEGIN_MARKER}
  const mozilla::pkix::Input* mConstrainedRoot;              // non-owning
  const mozilla::pkix::Input* mAdditionalNameConstraints;    // non-owning
  {END_MARKER}
  const Maybe<nsTArray<nsTArray<uint8_t>>>& mExtraCertificates;"""
    return replace_once(source, old_members, new_members, "TrustDomain members")


def patch_trust_domain_cpp(source: str) -> str:
    old_signature = """    /*out*/ nsTArray<nsTArray<uint8_t>>& builtChain,
    /*optional*/ PinningTelemetryInfo* pinningTelemetryInfo,
    /*optional*/ const char* hostname)"""
    new_signature = """    /*out*/ nsTArray<nsTArray<uint8_t>>& builtChain,
    /*optional*/ PinningTelemetryInfo* pinningTelemetryInfo,
    /*optional*/ const char* hostname,
    /*optional*/ const Input* constrainedRoot,
    /*optional*/ const Input* additionalNameConstraints)"""
    source = replace_once(
        source, old_signature, new_signature, "TrustDomain constructor definition"
    )
    source = replace_once(
        source,
        """      mThirdPartyIntermediateInputs(thirdPartyIntermediateInputs),
      mExtraCertificates(extraCertificates),""",
        """      mThirdPartyIntermediateInputs(thirdPartyIntermediateInputs),
      mConstrainedRoot(constrainedRoot),
      mAdditionalNameConstraints(additionalNameConstraints),
      mExtraCertificates(extraCertificates),""",
        "TrustDomain constructor initialization",
    )

    old_pointer = "  Input* nameConstraintsInputPtr = nullptr;"
    source = replace_once(
        source,
        old_pointer,
        "  const Input* nameConstraintsInputPtr = nullptr;",
        "name constraints pointer constness",
    )
    anchor = """  } else if (PR_GetError() != SEC_ERROR_EXTENSION_NOT_FOUND) {
    return Result::FATAL_ERROR_LIBRARY_FAILURE;
  }

  // First try all relevant certificates known to Gecko"""
    block = f"""  }} else if (PR_GetError() != SEC_ERROR_EXTENSION_NOT_FOUND) {{
    return Result::FATAL_ERROR_LIBRARY_FAILURE;
  }}

  {BEGIN_MARKER}
  if (mConstrainedRoot && mAdditionalNameConstraints) {{
    BackCert constrainedRoot(*mConstrainedRoot, EndEntityOrCA::MustBeCA,
                             nullptr);
    Result rv = constrainedRoot.Init();
    if (rv != Success) {{
      return rv;
    }}
    if (InputsAreEqual(encodedIssuerName, constrainedRoot.GetSubject())) {{
      // Two independent constraint sets would have to be intersected. Fail
      // closed if NSS ever adds imposed constraints for this same subject.
      if (nameConstraintsInputPtr) {{
        return Result::ERROR_UNKNOWN_ISSUER;
      }}
      nameConstraintsInputPtr = mAdditionalNameConstraints;
    }}
  }}
  {END_MARKER}

  // First try all relevant certificates known to Gecko"""
    return replace_once(source, anchor, block, "scoped root name constraints")


def patch_fenix_gradle(source: str) -> str:
    source = replace_once(
        source,
        '        applicationId "org.mozilla"',
        '        applicationId "app.ruthenium"',
        "Fenix application ID",
    )
    start = source.find("        release releaseTemplate >> {")
    end = source.find("        benchmark releaseTemplate >> {", start)
    if start == -1 or end == -1:
        raise ValueError("Fenix release build type was not found")
    section = source[start:end]
    section = replace_once(
        section,
        "        release releaseTemplate >> {\n",
        """        release releaseTemplate >> {
            // RFirefox development releases use the public debug key that is
            // pinned and passed in by the build tooling repository.
            def rfirefoxDebugKeystore = System.getenv("RFIREFOX_DEBUG_KEYSTORE")
            if (!rfirefoxDebugKeystore) {
                throw new GradleException("RFIREFOX_DEBUG_KEYSTORE is required")
            }
            signingConfigs.debug.storeFile = project.file(rfirefoxDebugKeystore)
            signingConfigs.debug.storePassword = "android"
            signingConfigs.debug.keyAlias = "androiddebugkey"
            signingConfigs.debug.keyPassword = "android"
            signingConfig = signingConfigs.debug
""",
        "Fenix release debug signing",
    )
    replacements = {
        'def deepLinkSchemeValue = "fenix"':
            'def deepLinkSchemeValue = "ruthenium"',
        '"sharedUserId": "org.mozilla.firefox.sharedID"':
            '"sharedUserId": "app.ruthenium.firefox.sharedID"',
    }
    for old, new in replacements.items():
        if new not in section:
            if section.count(old) != 1:
                raise ValueError(f"Fenix release branding anchor is ambiguous: {old}")
            section = section.replace(old, new, 1)
    return source[:start] + section + source[end:]


def patch_fenix_strings(source: str) -> str:
    replacements = {
        '<string name="app_name" translatable="false">Firefox Fenix</string>':
            '<string name="app_name" translatable="false">RFirefox</string>',
        '<string name="firefox" translatable="false">Firefox</string>':
            '<string name="firefox" translatable="false">RFirefox</string>',
        '<string name="app_name_firefox" tools:ignore="BrandUsage">Firefox</string>':
            '<string name="app_name_firefox" tools:ignore="BrandUsage">RFirefox</string>',
    }
    for old, new in replacements.items():
        source = replace_once(source, old, new, "Fenix application name")
    return source


def patch_fenix_release_strings(source: str) -> str:
    return replace_once(
        source,
        '<string name="app_name" translatable="false">Firefox</string>',
        '<string name="app_name" translatable="false">RFirefox</string>',
        "Fenix release application name",
    )


RFIREFOX_R_PATH = (
    "M22,62h10.8c5.6,0 9.2,3.2 9.2,8c0,4 -2.4,6.8 -6,8l6.8,8h-6.4"
    "l-6,-7.2h-2.8V86H22zM27.6,66.8V74h4.8c2.4,0 4,-1.2 4,-3.6"
    "s-1.6,-3.6 -4,-3.6z"
)

RFIREFOX_ADAPTIVE_BADGE = f"""  <!-- RFirefox launcher badge. Keep the upstream Firefox artwork unchanged. -->
  <path
      android:pathData="{RFIREFOX_R_PATH}"
      android:fillColor="#FFFFFFFF"
      android:fillType="evenOdd"
      android:strokeColor="#CC171D33"
      android:strokeWidth="1.2"
      android:strokeLineJoin="round" />
"""

RFIREFOX_MONOCHROME_BADGE = f"""  <!-- RFirefox launcher badge. -->
  <path
      android:pathData="{RFIREFOX_R_PATH}"
      android:fillColor="#20123A"
      android:fillType="evenOdd" />
"""


def patch_fenix_launcher_foreground(source: str) -> str:
    if "<!-- RFirefox launcher badge." in source:
        return source
    required = ('<vector xmlns:android=', 'android:viewportWidth="108"', '<path')
    if not all(anchor in source for anchor in required):
        raise ValueError("Fenix launcher foreground has an unexpected format")
    return replace_once(
        source,
        "</vector>\n",
        RFIREFOX_ADAPTIVE_BADGE + "</vector>\n",
        "Fenix launcher R badge",
    )


def patch_fenix_launcher_monochrome(source: str) -> str:
    if "<!-- RFirefox launcher badge." in source:
        return source
    required = ('<vector xmlns:android=', 'android:viewportWidth="108"', '<path')
    if not all(anchor in source for anchor in required):
        raise ValueError("Fenix monochrome launcher has an unexpected format")
    return replace_once(
        source,
        "</vector>\n",
        RFIREFOX_MONOCHROME_BADGE + "</vector>\n",
        "Fenix monochrome launcher R badge",
    )


TRANSFORMS: dict[Path, Callable[[str], str]] = {
    CERT_VERIFIER_CPP: patch_cert_verifier_cpp,
    CERT_VERIFIER_H: patch_cert_verifier_h,
    TRUST_DOMAIN_CPP: patch_trust_domain_cpp,
    TRUST_DOMAIN_H: patch_trust_domain_h,
    FENIX_GRADLE: patch_fenix_gradle,
    FENIX_STRINGS: patch_fenix_strings,
    FENIX_RELEASE_STRINGS: patch_fenix_release_strings,
    FENIX_LAUNCHER_FOREGROUND: patch_fenix_launcher_foreground,
    FENIX_RELEASE_LAUNCHER_FOREGROUND: patch_fenix_launcher_foreground,
    FENIX_LAUNCHER_MONOCHROME: patch_fenix_launcher_monochrome,
}


def patch_checkout(source_root: Path, der: bytes) -> list[Path]:
    changed: list[Path] = []
    for relative_path, transform in TRANSFORMS.items():
        path = source_root / relative_path
        original = path.read_text(encoding="utf-8")
        patched = transform(original)
        if patched != original:
            path.write_text(patched, encoding="utf-8")
            changed.append(relative_path)
    header_path = source_root / GENERATED_HEADER
    header = generated_header(der)
    if not header_path.exists() or header_path.read_text(encoding="utf-8") != header:
        header_path.write_text(header, encoding="utf-8")
        changed.append(GENERATED_HEADER)
    changed.extend(copy_branding_icons(source_root))
    return changed


def copy_branding_icons(source_root: Path) -> list[Path]:
    changed: list[Path] = []
    for asset_path, relative_path in FENIX_LEGACY_ICONS:
        if not asset_path.is_file():
            raise ValueError(f"launcher icon asset is missing: {asset_path}")
        destination = source_root / relative_path
        if not destination.is_file():
            raise ValueError(f"upstream launcher icon is missing: {relative_path}")
        if destination.read_bytes() != asset_path.read_bytes():
            shutil.copyfile(asset_path, destination)
            changed.append(relative_path)
    return changed


def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": "Ruthenium-Firefox-patch-check/1"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", "strict")


def check_remote(raw_base_url: str, der: bytes) -> None:
    for relative_path, transform in TRANSFORMS.items():
        source = fetch_text(f"{raw_base_url.rstrip('/')}/{relative_path.as_posix()}")
        patched = transform(source)
        if patched == source:
            raise ValueError(f"remote source already appears patched: {relative_path}")
        if transform(patched) != patched:
            raise ValueError(f"patch is not idempotent: {relative_path}")
    header = generated_header(der)
    if hashlib.sha256(der).hexdigest() not in header:
        raise ValueError("generated header does not record the certificate digest")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument(
        "--check-remote",
        metavar="RAW_BASE_URL",
        help="validate all text transforms against an hg raw-file base URL",
    )
    parser.add_argument("--list-targets", action="store_true")
    args = parser.parse_args()

    if args.list_targets:
        for path in (
            *TEXT_TARGETS,
            *(path for _, path in FENIX_LEGACY_ICONS),
            GENERATED_HEADER,
        ):
            print(path)
        return

    der = load_verified_certificate()
    if args.check_remote:
        check_remote(args.check_remote, der)
        print("Ruthenium patch compatibility passed")
        return
    if args.source is None:
        parser.error("--source is required unless --check-remote or --list-targets is used")
    changed = patch_checkout(args.source.resolve(), der)
    if changed:
        print("patched:")
        for path in changed:
            print(f"  {path}")
    else:
        print("already patched")


if __name__ == "__main__":
    main()
