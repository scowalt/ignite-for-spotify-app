import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from deployment_process import OperationFailed
from migration_tool import MigrationTool


class MigrationToolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.docker = [sys.executable, str(Path(__file__).parent / 'fixtures/migration_tool.py'), str(self.root)]
        self.environment = {**os.environ, 'SHOULD_NOT_INHERIT': 'fixture-private-token'}

    def tool(self, **changes):
        return MigrationTool(self.docker, 'sha256:' + 'a' * 64, 'fixture', '/fixture/data', environment=self.environment, **changes)

    def test_inspection_mount_is_read_only_and_owned_container_is_removed(self):
        result = self.tool().invoke('inspect', {'database_path': '/data/ignite.db'})
        self.assertEqual(result, {'schema': 1, 'schema_sha256': 'b' * 64, 'history': None})
        self.assertFalse((self.root / 'container.json').exists())
        commands = [json.loads(line) for line in (self.root / 'commands.jsonl').read_text().splitlines()]
        create = next(row for row in commands if row[0] == 'create')
        self.assertIn('readonly', create[create.index('--mount') + 1])
        self.assertEqual(create[create.index('--network') + 1], 'none')
        self.assertEqual(create[create.index('--user') + 1], '999:999')

    def interrupted_writer(self):
        self.tool().invoke('inspect', {'database_path': '/data/ignite.db'})
        value = json.loads((self.root / 'created.json').read_text())
        value.update(action='apply', running=True, command=['/app/migrations/Ignite.Migrations.dll', 'apply', '/app/migration-catalogue.json'])
        value['mounts'][0]['RW'] = True
        return value

    def test_restarted_owner_stops_and_removes_an_interrupted_writer(self):
        (self.root / 'container.json').write_text(json.dumps(self.interrupted_writer()))
        self.tool().close()
        self.assertTrue((self.root / 'stopped').exists())
        self.assertFalse((self.root / 'container.json').exists())

    def test_ownership_or_mount_changes_never_stop_an_unknown_container(self):
        original = self.interrupted_writer()
        for field in ['owner', 'image_id', 'mounts']:
            with self.subTest(field=field):
                value = {**original, field: [] if field == 'mounts' else 'unknown'}
                (self.root / 'container.json').write_text(json.dumps(value))
                with self.assertRaises(OperationFailed):
                    self.tool().close()
                self.assertFalse((self.root / 'stopped').exists())
                self.assertEqual(json.loads((self.root / 'container.json').read_text()), value)

    def test_request_cannot_select_other_paths_or_commands_or_unbounded_input(self):
        for action, request in [('shell', {'database_path': '/data/ignite.db'}), ('inspect', {'database_path': '/etc/passwd'}), ('apply', {'database_path': '/data/ignite.db', 'extra': 'x' * (2 * 1024**2)})]:
            with self.subTest(action=action):
                with self.assertRaises(OperationFailed):
                    self.tool().invoke(action, request)
                self.assertFalse((self.root / 'commands.jsonl').exists())

    def test_timeout_stops_the_owned_writer_before_returning_failure(self):
        (self.root / 'mode').write_text('hang')
        with self.assertRaises(OperationFailed) as failure:
            self.tool(timeout=0.1).invoke('apply', {'database_path': '/data/ignite.db'})
        self.assertNotIn('fixture-private', str(failure.exception))
        self.assertTrue((self.root / 'stopped').exists())
        self.assertFalse((self.root / 'container.json').exists())


if __name__ == '__main__':
    unittest.main()
