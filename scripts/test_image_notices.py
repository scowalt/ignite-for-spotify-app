import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "collect_image_notices", Path(__file__).with_name("collect-image-notices.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ImageNoticeTests(unittest.TestCase):
    def test_go_build_metadata_retains_replacement_identity(self):
        text = "binary: go1.27.3\n\tmod\texample.test/main\t(devel)\n\tdep\texample.test/library\tv1.0.0\th1:fixture\n\t=>\texample.test/fork\tv1.0.1\th1:fixture\n"
        modules = MODULE.parse_go_build(text)
        self.assertTrue(modules[0]["main"])
        self.assertEqual(
            modules[1]["replacement"],
            {"name": "example.test/fork", "version": "v1.0.1"},
        )
        self.assertEqual(
            MODULE.go_escape("example.test/Example"), "example.test/!example"
        )

    def test_json_stream_and_notice_names(self):
        self.assertEqual(
            MODULE.decode_stream(' {"Path":"one"}\n {"Path":"two"} '),
            [{"Path": "one"}, {"Path": "two"}],
        )
        for filename in ("LICENSE", "LICENSE.md", "COPYING.LESSER", "sub/NOTICE.txt"):
            self.assertTrue(MODULE.notice_name(filename))
        for filename in ("license_test.go", "token.key", "README.md"):
            self.assertFalse(MODULE.notice_name(filename))

    def test_notices_are_copied_verbatim_without_following_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            content = b"Copyright upstream\r\npermission text\r\n"
            (source / "LICENSE").write_bytes(content)
            (source / "NOTICE.txt").symlink_to(root / "private-file")
            (root / "private-file").write_text("not a notice")
            target = root / "output"
            target.mkdir()
            self.assertEqual(MODULE.copy_notices(source, target), ["LICENSE"])
            self.assertEqual((target / "LICENSE").read_bytes(), content)
            self.assertFalse((target / "NOTICE.txt").exists())

    def test_archive_paths_cannot_escape_notice_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "package.nupkg"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("../LICENSE", "outside")
                package.writestr("docs/LICENSE", "upstream license")
                package.writestr("lib/library.dll", "not a license")
            target = root / "output"
            notices = MODULE.copy_package_notices(archive, target)
            self.assertEqual(notices, ["docs/LICENSE"])
            self.assertFalse((root / "LICENSE").exists())

    def test_only_pinned_credential_free_github_source_is_accepted(self):
        good = {"url": "https://github.com/example/library.git", "commit": "a" * 40}
        self.assertEqual(MODULE.safe_github_source(good), ("example/library", "a" * 40))
        for bad in (
            {**good, "commit": "main"},
            {**good, "url": "https://user:fixture@github.com/example/library"},
            {**good, "url": "https://example.invalid/example/library"},
            {**good, "url": "https://github.com/example/library?token=fixture"},
        ):
            self.assertIsNone(MODULE.safe_github_source(bad))

    def test_dotnet_inventory_unions_independent_publish_graphs_without_losing_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graphs = []
            for version in ['1.0.0', '2.0.0']:
                package = root / 'packages/sample' / version
                package.mkdir(parents=True)
                (package / 'sample.nuspec').write_text('<package><metadata><license type="expression">MIT</license></metadata></package>')
                with zipfile.ZipFile(package / 'sample.nupkg', 'w') as archive:
                    archive.writestr('LICENSE', 'upstream permission')
                graph = root / (version + '.deps.json')
                graph.write_text(json.dumps({'libraries': {'Sample/' + version: {'type': 'package'}, 'Sample/1.0.0': {'type': 'package'}}}))
                graphs.append(str(graph))
            result = MODULE.collect_dotnet(SimpleNamespace(deps=graphs, packages=str(root / 'packages'), output=str(root / 'output')))
            self.assertEqual([(item['name'], item['version']) for item in result['components']], [('Sample', '1.0.0'), ('Sample', '2.0.0')])
            self.assertEqual(result['review_required'], [])

    def test_dotnet_inventory_covers_published_packages_and_records_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            deps = root / "app.deps.json"
            deps.write_text(
                json.dumps(
                    {
                        "libraries": {
                            "Sample/1.0.0": {"type": "package"},
                            "Application/1.0.0": {"type": "project"},
                        }
                    }
                )
            )
            package = root / "packages/sample/1.0.0"
            package.mkdir(parents=True)
            (package / "sample.nuspec").write_text(
                '<package><metadata><id>Sample</id><version>1.0.0</version><license type="expression">MIT</license><copyright>Upstream owner</copyright></metadata></package>'
            )
            with zipfile.ZipFile(package / "sample.nupkg", "w") as archive:
                archive.writestr("LICENSE", "upstream permission")
            args = SimpleNamespace(
                output=str(root / "output"),
                deps=str(deps),
                packages=str(root / "packages"),
            )
            with patch.object(
                MODULE,
                "fetch_notice",
                side_effect=AssertionError("No network expected"),
            ):
                result = MODULE.collect_dotnet(args)
            self.assertEqual(len(result["components"]), 1)
            self.assertEqual(result["components"][0]["copyright"], "Upstream owner")
            self.assertEqual(result["review_required"], [])
            with zipfile.ZipFile(package / "sample.nupkg", "w") as archive:
                archive.writestr("lib/library.dll", "binary fixture")
            result = MODULE.collect_dotnet(args)
            self.assertEqual(
                result["review_required"], ["Missing notice text: Sample@1.0.0"]
            )


if __name__ == "__main__":
    unittest.main()
