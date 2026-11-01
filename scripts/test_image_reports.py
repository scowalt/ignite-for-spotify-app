import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "verify_image_reports", Path(__file__).with_name("verify-image-reports.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ImageReportTests(unittest.TestCase):
    def test_public_inventory_drops_raw_image_configuration_and_properties(self):
        source = {
            "specVersion": "1.6",
            "metadata": {
                "properties": [
                    {"name": "environment", "value": "synthetic-private-value"}
                ]
            },
            "components": [
                {
                    "type": "library",
                    "name": "example",
                    "version": "1.0",
                    "purl": "pkg:npm/example@1.0",
                    "properties": [
                        {"name": "path", "value": "synthetic-private-value"}
                    ],
                }
            ],
        }
        result = MODULE.public_inventory(source, "ignite-verify-backend:fixture")
        self.assertNotIn("synthetic-private-value", json.dumps(result))
        self.assertEqual(result["components"][0]["purl"], "pkg:npm/example@1.0")

    def test_notice_inventory_requires_actual_files_and_no_unresolved_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            data = {
                "components": [
                    {
                        "name": "example",
                        "notice_directory": "notices/example",
                        "notice_files": ["LICENSE"],
                    }
                ],
                "review_required": [],
            }
            manifest.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                MODULE.checked_notice_manifest(manifest)
            notice = root / "notices/example/LICENSE"
            notice.parent.mkdir(parents=True)
            notice.write_text("upstream terms")
            self.assertEqual(MODULE.checked_notice_manifest(manifest), data)
            data["review_required"] = ["unresolved"]
            manifest.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                MODULE.checked_notice_manifest(manifest)

    def test_notice_paths_cannot_escape_the_copied_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "components": [
                            {
                                "notice_directory": "../outside",
                                "notice_files": ["LICENSE"],
                            }
                        ],
                        "review_required": [],
                    }
                )
            )
            with self.assertRaises(ValueError):
                MODULE.checked_notice_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
