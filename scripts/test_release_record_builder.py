import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseBuilderTests(unittest.TestCase):
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
