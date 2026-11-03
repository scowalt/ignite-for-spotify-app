from contextlib import closing
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
import uuid

from deployment_process import OperationFailed, run
from migration_image import metadata_file
from migration_record import verify_source_descriptor
from migration_tool import MigrationTool


ROOT = Path(__file__).resolve().parents[1]
IMAGE = os.environ.get('IGNITE_MIGRATION_FIXTURE_IMAGE')
WRITER_IMAGE = os.environ.get('IGNITE_MIGRATION_WRITER_FIXTURE_IMAGE')


def hold_container_writer(image, operation, source, environment, phase):
    MigrationTool(['docker'], image, operation, source, environment=environment, timeout=120).invoke(
        'apply', {'database_path': '/data/ignite.db', 'fixture_phase': phase})


@unittest.skipUnless(IMAGE, 'Set IGNITE_MIGRATION_FIXTURE_IMAGE to the freshly built backend image.')
class MigrationStartupNativeTests(unittest.TestCase):
    def setUp(self):
        self.operation = 'fixture-' + uuid.uuid4().hex
        self.volume = 'ignite-migration-' + self.operation
        self.env = {key: os.environ[key] for key in ['PATH', 'HOME', 'DOCKER_HOST', 'DOCKER_CONFIG', 'XDG_RUNTIME_DIR'] if key in os.environ}
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.source = None
        self.tool = None
        self.created_volume = False
        self.addCleanup(self.cleanup)
        self.image = self.docker(['image', 'inspect', IMAGE, '--format', '{{.Id}}']).decode().strip()
        self.assertFalse(json.loads(self.docker(['image', 'inspect', self.image, '--format', '{{json .Config.Volumes}}'])))
        self.assertFalse(self.docker(['volume', 'ls', '--filter', 'name=^' + self.volume + '$', '--format', '{{.Name}}']).strip())
        self.docker(['volume', 'create', '--label', 'ignite.test-migration=' + self.operation, self.volume])
        self.created_volume = True
        value = json.loads(self.docker(['volume', 'inspect', self.volume, '--format', '{{json .}}']))
        self.assertEqual(value['Labels']['ignite.test-migration'], self.operation)
        self.source = value['Mountpoint']
        database = Path(self.temporary.name) / 'fixture.db'
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.executescript((ROOT / 'backend/tests/Ignite.Infrastructure.Tests/Fixtures/legacy-schema-v1.sql').read_text())
            connection.executescript((ROOT / 'backend/tests/Ignite.Infrastructure.Tests/Fixtures/legacy-rows-v1.sql').read_text())
        self.docker(['run', '--rm', '--interactive', '--pull', 'never', '--network', 'none', '--read-only', '--user', '0:0',
                     '--label', 'ignite.test-migration=' + self.operation,
                     '--mount', 'type=bind,src=' + self.source + ',dst=/data', '--entrypoint', '/bin/sh', self.image,
                     '-ec', 'cat > /data/ignite.db; chown 999:999 /data /data/ignite.db; chmod 700 /data; chmod 600 /data/ignite.db'], input=database.read_bytes())
        self.tool = MigrationTool(['docker'], self.image, self.operation, self.source, environment=self.env)
        self.descriptor = self.image_descriptor()

    def docker(self, args, *, input=None, timeout=60, limit=2 * 1024**2):
        return run(['docker', *args], env=self.env, input=input, timeout=timeout, limit=limit)

    def owned(self):
        return self.docker(['ps', '-a', '--no-trunc', '--filter', 'label=ignite.test-migration=' + self.operation, '--format', '{{.ID}}']).decode().splitlines()

    def cleanup(self):
        if self.tool is not None:
            self.tool.close()
        for identifier in self.owned():
            owner = self.docker(['inspect', '--format', '{{index .Config.Labels "ignite.test-migration"}}', identifier]).decode().strip()
            self.assertEqual(owner, self.operation)
            self.docker(['stop', '--time', '0', identifier])
            if identifier in self.owned():
                self.docker(['rm', identifier])
        if self.created_volume:
            owner = self.docker(['volume', 'inspect', '--format', '{{index .Labels "ignite.test-migration"}}', self.volume]).decode().strip()
            self.assertEqual(owner, self.operation)
            self.docker(['volume', 'rm', self.volume])

    def image_descriptor(self):
        identifier = self.docker(['create', '--pull', 'never', '--network', 'none', '--read-only',
                                  '--label', 'ignite.test-migration=' + self.operation, '--entrypoint', '/not-executed', self.image]).decode().strip()
        try:
            content = metadata_file(self.docker(['cp', identifier + ':/app/migration-catalogue.json', '-'], limit=1024**2 + 65536), 'migration-catalogue.json', 1024**2)
            return verify_source_descriptor(content, ROOT)
        finally:
            self.docker(['rm', identifier])

    def start_app(self):
        identifier = self.docker(['create', '--pull', 'never', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                                  '--security-opt', 'no-new-privileges', '--memory', '512m', '--memory-swap', '512m',
                                  '--cpus', '1', '--pids-limit', '128', '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=67108864,mode=1777',
                                  '--label', 'ignite.test-migration=' + self.operation,
                                  '--mount', 'type=bind,src=' + self.source + ',dst=/app/data',
                                  '--env', 'DOTNET_EnableDiagnostics=0', '--env', 'ASPNETCORE_ENVIRONMENT=Production',
                                  '--env', 'Database__RequireExisting=true', '--env', 'Sentry__Dsn=',
                                  '--env', 'ConnectionStrings__Database=Data Source=/app/data/ignite.db;Default Timeout=5',
                                  '--env', 'ConnectionStrings__Hangfire=/app/data/hangfire.db', self.image]).decode().strip()
        self.docker(['start', identifier])
        return identifier

    def app_state(self, identifier):
        return json.loads(self.docker(['inspect', '--format', '{"running":{{json .State.Running}},"exit":{{json .State.ExitCode}},"health":{{with index .State "Health"}}{{json .Status}}{{else}}null{{end}}}', identifier]))

    def test_unadopted_database_cannot_start_http_or_initialize_hangfire(self):
        before = self.tool.invoke('inspect', {'database_path': '/data/ignite.db'})
        self.assertIsNone(before['history'])
        self.assertEqual(before['schema_sha256'], self.descriptor['baseline_schema_sha256'])
        identifier = self.start_app()
        deadline = time.monotonic() + 30
        while self.app_state(identifier)['running'] and time.monotonic() < deadline:
            time.sleep(0.2)
        value = self.app_state(identifier)
        self.assertFalse(value['running'])
        self.assertNotEqual(value['exit'], 0)
        self.assertEqual(self.tool.invoke('inspect', {'database_path': '/data/ignite.db'}), before)
        self.docker(['run', '--rm', '--pull', 'never', '--network', 'none', '--read-only',
                     '--label', 'ignite.test-migration=' + self.operation,
                     '--mount', 'type=bind,src=' + self.source + ',dst=/data,readonly', '--entrypoint', '/bin/sh', self.image,
                     '-ec', 'test ! -e /data/hangfire.db'])

    def test_explicitly_adopted_database_starts_the_real_application_healthy(self):
        before = self.tool.invoke('inspect', {'database_path': '/data/ignite.db'})
        receipt = self.tool.invoke('adopt', {'database_path': '/data/ignite.db', 'before': before,
                                          'catalogue_sha256': self.descriptor['catalogue_sha256'], 'schema_sha256': self.descriptor['schema_sha256']})
        self.assertEqual(receipt['outcome'], 'adopted')
        self.assertEqual(len(receipt['inspection']['history']), 1)
        identifier = self.start_app()
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline:
            value = self.app_state(identifier)
            if not value['running'] or value['health'] == 'healthy':
                break
            time.sleep(1)
        self.assertTrue(value['running'])
        self.assertEqual(value['health'], 'healthy')
        self.assertEqual(self.docker(['exec', identifier, 'curl', '--silent', '--max-time', '10', '--output', '/dev/null', '--write-out', '%{http_code}', 'http://127.0.0.1:5050/health/ready']), b'200')

    def writer_fixture(self, timeout=120):
        image = self.docker(['image', 'inspect', WRITER_IMAGE, '--format', '{{.Id}}']).decode().strip()
        tool = MigrationTool(['docker'], image, self.operation + '-writer', self.source, environment=self.env, timeout=timeout)
        self.addCleanup(tool.close)
        before = self.tool.invoke('inspect', {'database_path': '/data/ignite.db'})
        adopted = self.tool.invoke('adopt', {'database_path': '/data/ignite.db', 'before': before,
                                          'catalogue_sha256': self.descriptor['catalogue_sha256'], 'schema_sha256': self.descriptor['schema_sha256']})
        return tool, image, adopted['inspection']

    def writer_ids(self):
        return self.docker(['ps', '-a', '--no-trunc', '--filter', 'label=ignite.deployer-migration=' + self.operation + '-writer', '--format', '{{.ID}}']).decode().splitlines()

    @unittest.skipUnless(WRITER_IMAGE, 'Set IGNITE_MIGRATION_WRITER_FIXTURE_IMAGE to the test-only writer image.')
    def test_native_timeout_stops_the_daemon_writer_before_settlement(self):
        writer, _, before = self.writer_fixture(timeout=10)
        with self.assertRaises(OperationFailed):
            writer.invoke('apply', {'database_path': '/data/ignite.db', 'fixture_phase': 'before'})
        self.assertEqual(self.writer_ids(), [])
        self.docker(['run', '--rm', '--pull', 'never', '--network', 'none', '--read-only',
                     '--label', 'ignite.test-migration=' + self.operation,
                     '--mount', 'type=bind,src=' + self.source + ',dst=/data,readonly', '--entrypoint', '/bin/sh', self.image,
                     '-ec', 'test -s /data/fixture-ready'])
        with self.assertRaises(OperationFailed):
            self.tool.invoke('inspect', {'database_path': '/data/ignite.db'})
        settled = self.tool.invoke('settle', {'database_path': '/data/ignite.db'})
        self.assertEqual(settled['inspection'], before)

    def kill_controller(self, phase):
        _, image, before = self.writer_fixture()
        process = multiprocessing.get_context('fork').Process(target=hold_container_writer,
            args=(image, self.operation + '-writer', self.source, self.env, phase))
        process.start()
        try:
            deadline = time.monotonic() + 20
            ready = False
            identifier = None
            while process.is_alive() and time.monotonic() < deadline:
                identifiers = self.writer_ids()
                if len(identifiers) == 1:
                    identifier = identifiers[0]
                    try:
                        self.docker(['exec', identifier, '/bin/sh', '-ec', 'test -s /data/fixture-ready'])
                        ready = True
                        break
                    except OperationFailed:
                        pass
                time.sleep(0.1)
            self.assertTrue(ready)
            process.kill()
            process.join(5)
            self.assertFalse(process.is_alive())
            self.assertEqual(self.docker(['inspect', '--format', '{{.State.Running}}', identifier]).strip(), b'true')
            recovered = MigrationTool(['docker'], image, self.operation + '-writer', self.source, environment=self.env)
            recovered.close()
            self.assertEqual(self.writer_ids(), [])
            settled = self.tool.invoke('settle', {'database_path': '/data/ignite.db'})
            return before, settled['inspection']
        finally:
            if process.is_alive():
                process.kill()
            process.join(5)
            process.close()

    @unittest.skipUnless(WRITER_IMAGE, 'Set IGNITE_MIGRATION_WRITER_FIXTURE_IMAGE to the test-only writer image.')
    def test_native_restart_reaps_an_orphaned_uncommitted_container_writer(self):
        before, after = self.kill_controller('before')
        self.assertEqual(before, after)

    @unittest.skipUnless(WRITER_IMAGE, 'Set IGNITE_MIGRATION_WRITER_FIXTURE_IMAGE to the test-only writer image.')
    def test_native_restart_preserves_a_commit_that_preceded_controller_death(self):
        before, after = self.kill_controller('after')
        self.assertNotEqual(before['schema_sha256'], after['schema_sha256'])
        self.assertEqual(after['history'][:-1], before['history'])
        self.assertEqual(after['history'][-1]['id'], '9999_fixture.sql')


if __name__ == '__main__':
    unittest.main()
