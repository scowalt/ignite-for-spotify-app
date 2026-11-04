import io
import json
import os
from pathlib import Path
import sys
import tempfile
import tarfile
import unittest

from deployment_process import OperationFailed
from migration_image import metadata_file, read_image_metadata


def archive(name='migration-catalogue.json', content=b'{}', kind=tarfile.REGTYPE):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as target:
        entry = tarfile.TarInfo(name)
        entry.type = kind
        entry.size = len(content) if kind == tarfile.REGTYPE else 0
        entry.linkname = '/private' if kind != tarfile.REGTYPE else ''
        target.addfile(entry, io.BytesIO(content) if entry.size else None)
    return output.getvalue()


class MigrationImageTests(unittest.TestCase):
    def test_one_bounded_regular_file_is_read_without_extraction(self):
        self.assertEqual(metadata_file(archive(), 'migration-catalogue.json', 1024), b'{}')

    def test_metadata_is_copied_from_an_unstarted_owned_container_and_then_cleaned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = Path(__file__).parent / 'fixtures/migration_image.py'
            reference = 'ghcr.io/scowalt/ignite-for-spotify-app/backend@sha256:' + 'e' * 64
            env = {**os.environ, 'FIXTURE_ROOT': str(root)}
            manifest, deps, engine = read_image_metadata(reference, 'a' * 40, 'fixture', docker=[sys.executable, str(fixture)], env=env)
            self.assertEqual((manifest, deps, engine), (b'{}', b'{}', b'{}'))
            self.assertFalse((root / 'container').exists())
            commands = [json.loads(line) for line in (root / 'commands.jsonl').read_text().splitlines()]
            self.assertFalse(any(row[0] in ['run', 'start', 'exec'] for row in commands))
            self.assertEqual(commands[-1], ['rm', 'c' * 64])
            self.assertIn(['cp', 'c' * 64 + ':/app/migrations/Ignite.Migrations.deps.json', '-'], commands)

    def test_failed_copy_is_cleaned_but_unknown_ownership_is_not_removed(self):
        for mode in ['bad-copy', 'ownership-drift']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture = Path(__file__).parent / 'fixtures/migration_image.py'
                reference = 'ghcr.io/scowalt/ignite-for-spotify-app/backend@sha256:' + 'e' * 64
                with self.assertRaises(OperationFailed) as failure:
                    read_image_metadata(reference, 'a' * 40, 'fixture', docker=[sys.executable, str(fixture)], env={**os.environ, 'FIXTURE_ROOT': str(root), 'FIXTURE_MODE': mode})
                self.assertNotIn('fixture-private', str(failure.exception))
                self.assertEqual((root / 'container').exists(), mode == 'ownership-drift')

    def test_wrong_source_stops_before_creating_any_container(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = Path(__file__).parent / 'fixtures/migration_image.py'
            with self.assertRaises(OperationFailed):
                read_image_metadata('sha256:' + 'd' * 64, 'b' * 40, 'fixture', docker=[sys.executable, str(fixture)], env={**os.environ, 'FIXTURE_ROOT': str(root)})
            commands = [json.loads(line) for line in (root / 'commands.jsonl').read_text().splitlines()]
            self.assertFalse(any(row[0] == 'create' for row in commands))

    def test_paths_links_and_oversized_payloads_are_rejected(self):
        cases = [archive('../migration-catalogue.json'), archive('/migration-catalogue.json'),
                 archive(kind=tarfile.SYMTYPE), archive(content=b'x' * 2048)]
        for payload in cases:
            with self.subTest(size=len(payload)), self.assertRaises(OperationFailed):
                metadata_file(payload, 'migration-catalogue.json', 1024)


if __name__ == '__main__':
    unittest.main()
