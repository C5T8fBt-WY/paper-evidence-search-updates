from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_update_site import ADDON_ID, UPDATE_URL, UpdateSiteError, build_site


class UpdateSiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary.name)
        self.version = "0.2.1"
        self.tag = f"firefox-v{self.version}"
        self.asset_name = f"paper-evidence-search-{self.version}.xpi"
        version_dir = self.repository / "incoming" / self.version
        version_dir.mkdir(parents=True)
        payload = b"signed-xpi"
        (version_dir / self.asset_name).write_bytes(payload)
        self.metadata_path = version_dir / "release.json"
        self.metadata_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "addon_id": ADDON_ID,
                    "version": self.version,
                    "update_url": UPDATE_URL,
                    "release_tag": self.tag,
                    "asset_name": self.asset_name,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "update_link": (
                        "https://github.com/C5T8fBt-WY/paper-evidence-search-updates/"
                        f"releases/download/{self.tag}/{self.asset_name}"
                    ),
                    "size": len(payload),
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_builds_firefox_update_manifest(self) -> None:
        output = self.repository / "site"
        build_site(self.repository, output, tag=self.tag)
        payload = json.loads((output / "updates.json").read_text(encoding="utf-8"))
        update = payload["addons"][ADDON_ID]["updates"][0]
        self.assertEqual(update["version"], self.version)
        self.assertRegex(update["update_hash"], r"^sha256:[0-9a-f]{64}$")

    def test_rejects_release_tag_older_than_latest_staged_version(self) -> None:
        version = "0.2.2"
        tag = f"firefox-v{version}"
        asset_name = f"paper-evidence-search-{version}.xpi"
        version_dir = self.repository / "incoming" / version
        version_dir.mkdir(parents=True)
        payload = b"newer-signed-xpi"
        (version_dir / asset_name).write_bytes(payload)
        metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        metadata.update(
            version=version,
            release_tag=tag,
            asset_name=asset_name,
            sha256=hashlib.sha256(payload).hexdigest(),
            update_link=(
                "https://github.com/C5T8fBt-WY/paper-evidence-search-updates/"
                f"releases/download/{tag}/{asset_name}"
            ),
            size=len(payload),
        )
        (version_dir / "release.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )

        with self.assertRaisesRegex(UpdateSiteError, "newest staged version"):
            build_site(self.repository, self.repository / "site", tag=self.tag)

    def test_rejects_tampered_xpi(self) -> None:
        asset = self.metadata_path.parent / self.asset_name
        asset.write_bytes(b"tampered")
        with self.assertRaisesRegex(UpdateSiteError, "Size mismatch"):
            build_site(self.repository, self.repository / "site", tag=self.tag)


if __name__ == "__main__":
    unittest.main()
