from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ADDON_ID = "iclr-paper-search@mynews.local"
UPDATE_URL = "https://c5t8fbt-wy.github.io/paper-evidence-search-updates/updates.json"
REPOSITORY = "C5T8fBt-WY/paper-evidence-search-updates"
_VERSION_PATTERN = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
)


class UpdateSiteError(ValueError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UpdateSiteError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise UpdateSiteError(f"Expected a JSON object in {path}")
    return payload


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def validate_release(metadata_path: Path) -> dict[str, Any]:
    metadata = _read_json(metadata_path)
    version = metadata.get("version")
    if not isinstance(version, str) or _VERSION_PATTERN.fullmatch(version) is None:
        raise UpdateSiteError(f"Invalid version in {metadata_path}")
    asset_name = f"paper-evidence-search-{version}.xpi"
    release_tag = f"firefox-v{version}"
    update_link = (
        f"https://github.com/{REPOSITORY}/releases/download/{release_tag}/{asset_name}"
    )
    expected = {
        "schema_version": 1,
        "addon_id": ADDON_ID,
        "version": version,
        "update_url": UPDATE_URL,
        "release_tag": release_tag,
        "asset_name": asset_name,
        "update_link": update_link,
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise UpdateSiteError(f"Unexpected {key} in {metadata_path}")
    if metadata_path.parent.name != version:
        raise UpdateSiteError(f"Version directory does not match {version}")
    asset_path = metadata_path.parent / asset_name
    try:
        payload = asset_path.read_bytes()
    except OSError as exc:
        raise UpdateSiteError(f"Cannot read {asset_path}: {exc}") from exc
    if metadata.get("size") != len(payload):
        raise UpdateSiteError(f"Size mismatch for {asset_path}")
    if metadata.get("sha256") != _sha256(payload):
        raise UpdateSiteError(f"SHA-256 mismatch for {asset_path}")
    return metadata


def build_site(repository: Path, output: Path, *, tag: str) -> dict[str, Any]:
    releases = [
        validate_release(path)
        for path in sorted((repository / "incoming").glob("*/release.json"))
    ]
    if not releases:
        raise UpdateSiteError("No Firefox releases are staged")
    if tag not in {release["release_tag"] for release in releases}:
        raise UpdateSiteError(f"Tag {tag!r} has no matching staged release")
    releases.sort(
        key=lambda release: tuple(int(part) for part in release["version"].split("."))
    )
    if releases[-1]["release_tag"] != tag:
        raise UpdateSiteError(
            f"Tag {tag!r} does not identify the newest staged version"
        )
    updates = [
        {
            "version": release["version"],
            "update_link": release["update_link"],
            "update_hash": f"sha256:{release['sha256']}",
        }
        for release in releases
    ]
    payload = {"addons": {ADDON_ID: {"updates": updates}}}
    output.mkdir(parents=True, exist_ok=True)
    (output / "updates.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    latest = releases[-1]
    release_link = html.escape(latest["update_link"], quote=True)
    (output / "index.html").write_text(
        '<!doctype html><meta charset="utf-8">'
        "<title>Paper Evidence Search updates</title>"
        "<h1>Paper Evidence Search updates</h1>"
        "<p>This is the public, unlisted Firefox update channel.</p>"
        f'<p>Latest signed release: <a href="{release_link}">'
        f"{html.escape(latest['version'])}</a></p>\n",
        encoding="utf-8",
    )
    return payload


def _download_until(url: str, *, timeout_seconds: float) -> bytes:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "paper-evidence-search-cd"}
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.read()
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
            time.sleep(2)
    raise UpdateSiteError(f"Timed out downloading {url}: {last_error}")


def verify_release(metadata_path: Path, *, timeout_seconds: float) -> None:
    metadata = validate_release(metadata_path)
    payload = _download_until(metadata["update_link"], timeout_seconds=timeout_seconds)
    if len(payload) != metadata["size"] or _sha256(payload) != metadata["sha256"]:
        raise UpdateSiteError("Public release asset differs from the staged signed XPI")


def verify_exact_url(url: str, expected_path: Path, *, timeout_seconds: float) -> None:
    expected = expected_path.read_bytes()
    actual = _download_until(url, timeout_seconds=timeout_seconds)
    if actual != expected:
        raise UpdateSiteError(f"Public content at {url} does not match {expected_path}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and verify the Firefox update site"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--repository", type=Path, default=Path.cwd())
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--tag", required=True)
    release = commands.add_parser("verify-release")
    release.add_argument("--metadata", type=Path, required=True)
    release.add_argument("--timeout-seconds", type=float, default=180)
    exact = commands.add_parser("verify-url")
    exact.add_argument("--url", required=True)
    exact.add_argument("--expected", type=Path, required=True)
    exact.add_argument("--timeout-seconds", type=float, default=180)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "build":
        build_site(args.repository, args.output, tag=args.tag)
    elif args.command == "verify-release":
        verify_release(args.metadata, timeout_seconds=args.timeout_seconds)
    else:
        verify_exact_url(args.url, args.expected, timeout_seconds=args.timeout_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
