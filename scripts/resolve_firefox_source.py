#!/usr/bin/env python3
"""Resolve the latest stable Firefox for Android source revision."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from dataclasses import dataclass


PRODUCT_DETAILS_URL = "https://product-details.mozilla.org/1.0/firefox_versions.json"
STABLE_REPOSITORY = "https://hg-edge.mozilla.org/releases/mozilla-release"


@dataclass(frozen=True)
class SourceSelection:
    version: str
    tag: str
    revision: str
    repository: str = STABLE_REPOSITORY

    @property
    def archive_url(self) -> str:
        return f"{self.repository}/archive/{self.revision}.zip"


def fetch_json(url: str, timeout: int = 60) -> object:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Ruthenium-Firefox-source-resolver/1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"unexpected HTTP status {response.status} for {url}")
        return json.load(response)


def version_to_android_tag(version: str) -> str:
    if not re.fullmatch(r"[1-9][0-9]*\.[0-9]+(?:\.[0-9]+)?", version):
        raise ValueError(f"not a stable Firefox version: {version!r}")
    return f"FIREFOX-ANDROID_{version.replace('.', '_')}_RELEASE"


def select_stable(product_details: object, tags_document: object) -> SourceSelection:
    if not isinstance(product_details, dict):
        raise ValueError("product details must be a JSON object")
    version = product_details.get("LATEST_FIREFOX_VERSION")
    if not isinstance(version, str):
        raise ValueError("LATEST_FIREFOX_VERSION is missing")
    tag = version_to_android_tag(version)

    if not isinstance(tags_document, dict) or not isinstance(
        tags_document.get("tags"), list
    ):
        raise ValueError("Mercurial tags response is malformed")

    matches = [
        item
        for item in tags_document["tags"]
        if isinstance(item, dict) and item.get("tag") == tag
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {tag} tag, found {len(matches)}")
    revision = matches[0].get("node")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError(f"tag {tag} has an invalid revision")
    return SourceSelection(version=version, tag=tag, revision=revision)


def resolve_stable() -> SourceSelection:
    product_details = fetch_json(PRODUCT_DETAILS_URL)
    tags_document = fetch_json(f"{STABLE_REPOSITORY}/json-tags")
    return select_stable(product_details, tags_document)


def emit(selection: SourceSelection, output_format: str) -> None:
    values = {
        "version": selection.version,
        "tag": selection.tag,
        "revision": selection.revision,
        "repository": selection.repository,
        "archive_url": selection.archive_url,
    }
    if output_format == "json":
        json.dump(values, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return
    if output_format == "github-output":
        for key, value in values.items():
            print(f"{key}={value}")
        return
    for key, value in values.items():
        print(f"{key.upper()}={value}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--format",
        choices=("env", "json", "github-output"),
        default="env",
    )
    args = parser.parse_args()
    emit(resolve_stable(), args.format)


if __name__ == "__main__":
    main()
