import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
import uuid

from deployment_process import run
from migration_image import metadata_file
from migration_record import verify_source_descriptor
from migration_tool import MigrationTool


ROOT = Path(__file__).resolve().parents[1]
IMAGE = os.environ.get('IGNITE_MIGRATION_FIXTURE_IMAGE')


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
        with sqlite3.connect(database) as connection:
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


if __name__ == '__main__':
    unittest.main()
