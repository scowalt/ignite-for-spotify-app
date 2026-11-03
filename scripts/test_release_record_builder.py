import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from release_record import CONTRACT_PATHS, MIGRATION_CONTRACT_PATHS
from test_migration_record import DESCRIPTOR

ROOT = Path(__file__).resolve().parents[1]


class ReleaseBuilderTests(unittest.TestCase):
    def test_migration_cli_copies_metadata_from_the_exact_immutable_backend_without_running_it(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / 'source'
            state = base / 'fixture'
            state.mkdir()
            for name in CONTRACT_PATHS + MIGRATION_CONTRACT_PATHS:
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('reviewed fixture')
            migrations = source / 'backend/src/Ignite.Infrastructure/Data/Migrations'
            migrations.mkdir()
            (migrations / '0001_initial.sql').write_text('CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT);\n')
            (migrations / '0002_note.sql').write_text('ALTER TABLE sample ADD COLUMN note TEXT;\n')
            (migrations / 'manifest.json').write_text(json.dumps({'schema': 1, 'migrations': [{key: row[key] for key in ['id', 'delivery']} for row in DESCRIPTOR['migrations']]}))
            (state / 'migration-catalogue.json').write_text(json.dumps(DESCRIPTOR))
            names = ['Hangfire.AspNetCore', 'Hangfire.Core', 'Hangfire.NetCore', 'Hangfire.Storage.SQLite', 'sqlite-net-pcl']
            (state / 'Ignite.Api.deps.json').write_text(json.dumps({'libraries': {name + '/1.0.0': {'type': 'package', 'sha512': 'sha512-' + base64.b64encode(b'a' * 64).decode()} for name in names}}))
            docker = base / 'docker'
            docker.write_text('#!/usr/bin/env python3\nimport os,runpy\nos.environ["FIXTURE_ROOT"]=' + repr(str(state)) + '\nrunpy.run_path(' + repr(str(ROOT / 'scripts/fixtures/migration_image.py')) + ', run_name="__main__")\n')
            docker.chmod(0o700)
            output = base / 'release.json'
            env = {**os.environ, 'PATH': str(base) + os.pathsep + os.environ['PATH'], 'FIXTURE_ROOT': str(state),
                   'GITHUB_REPOSITORY': 'scowalt/ignite-for-spotify-app', 'GITHUB_REF': 'refs/heads/main',
                   'GITHUB_EVENT_NAME': 'push', 'GITHUB_SHA': 'a' * 40, 'GITHUB_RUN_ID': '123',
                   'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_RUN_NUMBER': '42'}
            result = subprocess.run(['python3', str(ROOT / 'scripts/prepare-release-record.py'), '--root', str(source), '--output', str(output), '--migration-protocol'], env=env, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            record = json.loads(output.read_text())
            self.assertEqual(record['schema'], 2)
            self.assertEqual(record['migrations']['catalogue_sha256'], DESCRIPTOR['catalogue_sha256'])
            commands = [json.loads(line) for line in (state / 'commands.jsonl').read_text().splitlines()]
            self.assertFalse(any(row[0] in ['run', 'start', 'exec'] for row in commands))
            self.assertFalse((state / 'container').exists())

    def test_cli_reads_only_three_published_digests_and_emits_no_environment_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docker = root / 'docker'
            docker.write_text('#!/usr/bin/env python3\nimport json,sys\nname=sys.argv[4].split("/")[-1].split(":")[0]\nassert sys.argv[1:4]==["buildx","imagetools","inspect"]\nassert name in ["backend","backup","frontend"]\nprint(json.dumps({"digest":"sha256:"+{"backend":"c","backup":"d","frontend":"e"}[name]*64}))\n')
            docker.chmod(0o700)
            output = root / 'record/release.json'
            env = {**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH'],
                   'GITHUB_REPOSITORY': 'scowalt/ignite-for-spotify-app', 'GITHUB_REF': 'refs/heads/main',
                   'GITHUB_EVENT_NAME': 'push', 'GITHUB_SHA': 'a' * 40,
                   'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_RUN_NUMBER': '42',
                   'UNRELATED_SECRET': 'fixture-not-for-output'}
            result = subprocess.run(['python3', str(ROOT / 'scripts/prepare-release-record.py'), '--root', str(ROOT), '--output', str(output)], env=env, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(output.read_text())
            self.assertEqual(record['images']['backup'], 'ghcr.io/scowalt/ignite-for-spotify-app/backup@sha256:' + 'd' * 64)
            self.assertEqual(set(record['images']), {'backend', 'backup', 'frontend'})
            self.assertNotIn('fixture-not-for-output', output.read_text() + result.stdout + result.stderr)
            env['GITHUB_EVENT_NAME'] = 'pull_request'
            denied = subprocess.run(['python3', str(ROOT / 'scripts/prepare-release-record.py'), '--root', str(ROOT), '--output', str(root / 'denied.json')], env=env, capture_output=True, text=True, check=False)
            self.assertNotEqual(denied.returncode, 0)
            self.assertFalse((root / 'denied.json').exists())


if __name__ == '__main__':
    unittest.main()
